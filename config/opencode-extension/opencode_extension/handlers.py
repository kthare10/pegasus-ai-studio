"""Tornado request handlers for the OpenCode Web Extension.

Manages the OpenCode web subprocess lifecycle and serves the panel UI.
Adapted from loomai-dev/backend/app/routes/ai_terminal.py.
"""

import asyncio
import json
import os
import shutil
import signal
import subprocess
import sys

from jupyter_server.base.handlers import JupyterHandler

from .config_builder import (
    PROVIDERS,
    PROXY_PROVIDERS,
    _resolve_api_key,
    _resolve_base_url,
    build_opencode_config,
    fetch_models,
)

# Fixed ports
_OPENCODE_WEB_PORT = 9198
_MODEL_PROXY_PORT = 9199

# Global subprocess handles
_opencode_web_proc = None
_opencode_web_proxy = None

# AI tools source directory (baked into the container image)
_AI_TOOLS_SRC = "/opt/pegasus-ai/ai-tools"


def _load_env_file():
    """Read LLM configuration from ~/.pegasus-ai/.env, falling back to os.environ.

    The .env file is the primary source (created by LLM_Setup.ipynb or
    pegasus-ai-setup wizard).  When it doesn't exist (fresh volume), we
    fall back to environment variables injected via docker-compose env_file.
    """
    env_path = os.path.join(os.environ.get("HOME", "/tmp"), ".pegasus-ai", ".env")
    env_vars = {}
    try:
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, _, value = line.partition("=")
                    env_vars[key.strip()] = value.strip()
    except FileNotFoundError:
        pass

    # Fallback: pull key LLM settings from os.environ if not in .env file
    _ENV_KEYS = [
        "LLM_PROVIDER", "LLM_MODEL",
        "ANTHROPIC_API_KEY", "OPENAI_API_KEY",
        "FABRIC_AI_API_KEY", "NRP_API_KEY",
        "CUSTOM_BASE_URL", "OLLAMA_HOST",
    ]
    for key in _ENV_KEYS:
        if key not in env_vars and os.environ.get(key):
            env_vars[key] = os.environ[key]

    return env_vars


def _ensure_git_repo(workspace):
    """Ensure workspace is a git repo so OpenCode detects it as a project.

    OpenCode uses git to find the project root.  Without a .git directory
    it falls back to the "global" project with directory "/" which breaks
    file listing and session directory tracking.
    """
    git_dir = os.path.join(workspace, ".git")
    if os.path.isdir(git_dir):
        return
    try:
        subprocess.run(
            ["git", "init", "-b", "main"],
            cwd=workspace,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
        # Initial commit so HEAD is valid
        subprocess.run(
            ["git", "add", "-A"],
            cwd=workspace,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        subprocess.run(
            ["git", "commit", "-m", "Initial workspace", "--allow-empty"],
            cwd=workspace,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env={**os.environ, "GIT_AUTHOR_NAME": "Pegasus AI",
                 "GIT_AUTHOR_EMAIL": "ai@pegasus",
                 "GIT_COMMITTER_NAME": "Pegasus AI",
                 "GIT_COMMITTER_EMAIL": "ai@pegasus"},
        )
    except Exception:
        pass


def _seed_opencode_workspace(workspace):
    """Seed OpenCode skills, agents, and shared context into workspace.

    Agents and skills are always updated from the image (not user-edited).
    AGENTS.md is always updated (shared context, not user-edited).
    """
    oc_dir = os.path.join(workspace, ".opencode")
    os.makedirs(oc_dir, exist_ok=True)

    # Shared context → AGENTS.md (always update to latest from image)
    src_agents = os.path.join(_AI_TOOLS_SRC, "shared", "PEGASUS_AI.md")
    dst_agents = os.path.join(workspace, "AGENTS.md")
    if os.path.isfile(src_agents):
        shutil.copy2(src_agents, dst_agents)

    # Clean up legacy agent-prompts dir (old wrong path)
    legacy_dir = os.path.join(oc_dir, "agent-prompts")
    if os.path.isdir(legacy_dir):
        shutil.rmtree(legacy_dir, ignore_errors=True)

    # Agent prompts → .opencode/agents/ (OpenCode discovers agents here)
    # Always overwrite to pick up image updates.
    agents_src = os.path.join(_AI_TOOLS_SRC, "opencode", "agents")
    if os.path.isdir(agents_src):
        agents_dir = os.path.join(oc_dir, "agents")
        os.makedirs(agents_dir, exist_ok=True)
        for fname in os.listdir(agents_src):
            if fname.endswith(".md"):
                shutil.copy2(
                    os.path.join(agents_src, fname),
                    os.path.join(agents_dir, fname),
                )

    # Skills → .opencode/skills/<name>/SKILL.md
    # Always overwrite to pick up image updates.
    skills_src = os.path.join(_AI_TOOLS_SRC, "opencode", "skills")
    if os.path.isdir(skills_src):
        for fname in os.listdir(skills_src):
            if not fname.endswith(".md"):
                continue
            skill_name = fname[:-3]
            skill_dir = os.path.join(oc_dir, "skills", skill_name)
            os.makedirs(skill_dir, exist_ok=True)
            shutil.copy2(
                os.path.join(skills_src, fname),
                os.path.join(skill_dir, "SKILL.md"),
            )

    # Commands → .opencode/commands/<name>.md
    # File-based commands show in the / palette.
    commands_src = os.path.join(_AI_TOOLS_SRC, "opencode", "commands")
    if os.path.isdir(commands_src):
        commands_dir = os.path.join(oc_dir, "commands")
        os.makedirs(commands_dir, exist_ok=True)
        for fname in os.listdir(commands_src):
            if fname.endswith(".md"):
                shutil.copy2(
                    os.path.join(commands_src, fname),
                    os.path.join(commands_dir, fname),
                )


def _kill_proc(proc):
    """Kill a subprocess and its process group."""
    if proc and proc.poll() is None:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            proc.wait(timeout=3)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


class StartHandler(JupyterHandler):
    """POST /api/opencode-web/start — Start OpenCode web subprocess."""

    def check_xsrf_cookie(self):
        pass  # Called from same-origin JS panel; no XSRF token available

    async def post(self):
        global _opencode_web_proc, _opencode_web_proxy

        model = self.get_argument("model", "")

        # Already running?
        if _opencode_web_proc and _opencode_web_proc.poll() is None:
            self.finish(json.dumps({
                "port": _OPENCODE_WEB_PORT,
                "status": "running",
            }))
            return

        env_vars = _load_env_file()
        provider = env_vars.get("LLM_PROVIDER", "")

        if not provider:
            self.set_status(400)
            self.finish(json.dumps({
                "error": "No LLM provider configured. Run LLM_Setup.ipynb first.",
                "status": "error",
            }))
            return

        workspace = os.path.join(os.environ.get("HOME", "/tmp"), "work")
        os.makedirs(workspace, exist_ok=True)

        # Ensure workspace is a git repo (required for OpenCode project detection)
        _ensure_git_repo(workspace)

        # Seed workspace (skills, agents, AGENTS.md) on first run
        _seed_opencode_workspace(workspace)

        # Build opencode.json dynamically
        oc_config = build_opencode_config(env_vars, provider=provider,
                                          model_override=model or None)

        # Strip internal keys before writing
        write_cfg = {k: v for k, v in oc_config.items() if not k.startswith("_")}
        config_path = os.path.join(workspace, "opencode.json")
        with open(config_path, "w") as f:
            json.dump(write_cfg, f, indent=2)
            f.write("\n")

        # Build environment for the subprocess
        tool_env = dict(os.environ)
        # Inject API keys from .env so OpenCode can resolve {env:...} refs
        for key, value in env_vars.items():
            tool_env[key] = value

        # Start model proxy for non-native providers
        default_model = oc_config.get("_default", "")
        allowed_models = oc_config.get("_allowed", [])

        if provider in PROXY_PROVIDERS:
            base_url = _resolve_base_url(provider, env_vars)
            api_key = _resolve_api_key(provider, env_vars)

            if base_url and default_model:
                proxy_script = (shutil.which("model_proxy.py")
                                or "/usr/local/bin/model_proxy.py")
                allowed_csv = (",".join(allowed_models)
                               if allowed_models else default_model)
                proxy_cmd = [
                    sys.executable, proxy_script,
                    str(_MODEL_PROXY_PORT),
                    base_url,
                    default_model,
                    allowed_csv,
                ]
                # Forward the real API key to the proxy
                proxy_env = dict(tool_env)
                if api_key:
                    proxy_env["OPENAI_API_KEY"] = api_key

                try:
                    _opencode_web_proxy = subprocess.Popen(
                        proxy_cmd, env=proxy_env,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        preexec_fn=os.setsid,
                    )
                except Exception:
                    _opencode_web_proxy = None

                if _opencode_web_proxy:
                    # Point OpenCode at the proxy (no /v1 suffix — the
                    # proxy TARGET_URL already includes /v1)
                    tool_env["OPENAI_BASE_URL"] = (
                        f"http://127.0.0.1:{_MODEL_PROXY_PORT}"
                    )
                    # Resolve the actual API key for the proxy to forward
                    key_map = {
                        "fabric": "FABRIC_AI_API_KEY",
                        "nrp": "NRP_API_KEY",
                        "custom": "OPENAI_API_KEY",
                        "ollama": None,
                    }
                    key_name = key_map.get(provider)
                    if key_name and env_vars.get(key_name):
                        tool_env["OPENAI_API_KEY"] = env_vars[key_name]

        # Spawn OpenCode web
        opencode_bin = shutil.which("opencode") or "opencode"
        cmd = [
            opencode_bin, "web",
            "--port", str(_OPENCODE_WEB_PORT),
            "--hostname", "0.0.0.0",
        ]

        try:
            _opencode_web_proc = subprocess.Popen(
                cmd, cwd=workspace, env=tool_env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                preexec_fn=os.setsid,
            )
        except Exception as e:
            self.set_status(500)
            self.finish(json.dumps({
                "error": f"Failed to start OpenCode: {e}",
                "status": "error",
            }))
            return

        # Wait for OpenCode to bind its port
        await asyncio.sleep(2)

        self.finish(json.dumps({
            "port": _OPENCODE_WEB_PORT,
            "status": "running",
        }))


class StopHandler(JupyterHandler):
    """POST /api/opencode-web/stop — Stop OpenCode web subprocess."""

    def check_xsrf_cookie(self):
        pass  # Called from same-origin JS panel; no XSRF token available

    async def post(self):
        global _opencode_web_proc, _opencode_web_proxy

        _kill_proc(_opencode_web_proc)
        _kill_proc(_opencode_web_proxy)
        _opencode_web_proc = None
        _opencode_web_proxy = None

        self.finish(json.dumps({"status": "stopped"}))


class StatusHandler(JupyterHandler):
    """GET /api/opencode-web/status — Check if OpenCode is running."""

    def get(self):
        running = (_opencode_web_proc is not None
                   and _opencode_web_proc.poll() is None)
        self.finish(json.dumps({
            "port": _OPENCODE_WEB_PORT if running else None,
            "status": "running" if running else "stopped",
        }))


class ModelsHandler(JupyterHandler):
    """GET /api/opencode-web/models — Fetch available models."""

    def get(self):
        env_vars = _load_env_file()
        provider = env_vars.get("LLM_PROVIDER", "")

        if not provider:
            self.finish(json.dumps({
                "models": [],
                "default": "",
                "provider": "",
            }))
            return

        # Get models for the default provider
        preset = PROVIDERS.get(provider)
        if not preset:
            self.finish(json.dumps({
                "models": [],
                "default": "",
                "provider": provider,
            }))
            return

        api_key = _resolve_api_key(provider, env_vars)
        base_url = _resolve_base_url(provider, env_vars)

        # Anthropic: no /models endpoint, use static list
        if provider == "anthropic":
            models = [preset["default_model"]]
        else:
            models, _ = fetch_models(base_url, api_key)
            if not models and preset["default_model"]:
                models = [preset["default_model"]]

        default_model = env_vars.get("LLM_MODEL", preset["default_model"])

        self.finish(json.dumps({
            "models": models,
            "default": default_model,
            "provider": provider,
        }))


class OpenCodePanelHandler(JupyterHandler):
    """Serve the OpenCode panel HTML page."""

    def initialize(self, path):
        self._static_dir = path

    def get(self):
        index_path = os.path.join(self._static_dir, "index.html")
        self.set_header("Content-Type", "text/html; charset=UTF-8")
        with open(index_path) as f:
            self.finish(f.read())
