"""Tornado request handlers for the Claude Code Extension.

Provides status checking and panel serving for the Claude Code launcher card.
"""

import json
import os
import shutil

from jupyter_server.base.handlers import JupyterHandler


def _load_env_file():
    """Read LLM configuration from ~/.pegasus-ai/.env, falling back to os.environ."""
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

    if "ANTHROPIC_API_KEY" not in env_vars and os.environ.get("ANTHROPIC_API_KEY"):
        env_vars["ANTHROPIC_API_KEY"] = os.environ["ANTHROPIC_API_KEY"]

    return env_vars


class StatusHandler(JupyterHandler):
    """GET /api/claude-code/status — Check if Claude Code is available."""

    def get(self):
        env_vars = _load_env_file()
        has_key = bool(env_vars.get("ANTHROPIC_API_KEY", ""))
        has_binary = shutil.which("claude") is not None

        self.finish(json.dumps({
            "has_api_key": has_key,
            "has_binary": has_binary,
            "status": "ready" if (has_key and has_binary) else "setup_required",
        }))


class ClaudeCodePanelHandler(JupyterHandler):
    """Serve the Claude Code panel HTML page."""

    def initialize(self, path):
        self._static_dir = path

    def get(self):
        index_path = os.path.join(self._static_dir, "index.html")
        self.set_header("Content-Type", "text/html; charset=UTF-8")
        with open(index_path) as f:
            self.finish(f.read())
