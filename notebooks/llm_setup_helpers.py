"""LLM Setup Helpers — Backend for the LLM_Setup.ipynb notebook.

The notebook collects API keys for FABRIC AI and NRP providers.
Other providers can be configured directly in OpenCode's settings.

At save time the helper:
  1. Writes keys to ~/.pegasus-ai/.env
  2. Fetches available models from each configured endpoint
  3. Writes opencode.json with configured providers + their models
"""

import json
import os
import subprocess
from pathlib import Path

PEGASUS_AI_DIR = Path.home() / ".pegasus-ai"
ENV_FILE = PEGASUS_AI_DIR / ".env"
WORKSPACE = Path.home() / "work"
CONFIGURE_SCRIPT = "/etc/profile.d/pegasus-ai-llm.sh"

PROVIDERS = {
    "anthropic": {
        "name": "Anthropic (Claude)",
        "base_url": "https://api.anthropic.com/v1",
        "default_model": "claude-sonnet-4-5-20250929",
        "api_key_env": "ANTHROPIC_API_KEY",
        "needs_key": True,
    },
    "openai": {
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o",
        "api_key_env": "OPENAI_API_KEY",
        "needs_key": True,
    },
    "fabric": {
        "name": "FABRIC AI",
        "base_url": "https://ai.fabric-testbed.net/v1",
        "default_model": "qwen3-coder-30b",
        "api_key_env": "FABRIC_AI_API_KEY",
        "needs_key": True,
    },
    "nrp": {
        "name": "NRP (Nautilus)",
        "base_url": "https://ellm.nrp-nautilus.io/v1",
        "default_model": "qwen3-coder-30b",
        "api_key_env": "NRP_API_KEY",
        "needs_key": True,
    },
    "ollama": {
        "name": "Ollama (local)",
        "base_url": "http://localhost:11434/v1",
        "default_model": "qwen2.5-coder:7b",
        "api_key_env": None,
        "needs_key": False,
    },
    "custom": {
        "name": "Custom endpoint",
        "base_url": "",
        "default_model": "",
        "api_key_env": "CUSTOM_API_KEY",
        "needs_key": True,
    },
}

# Providers shown in the notebook UI (others can be configured in OpenCode)
NOTEBOOK_PROVIDERS = ["fabric", "nrp"]


# ── Loading ──────────────────────────────────────────────────────

def load_all_keys():
    """Read ~/.pegasus-ai/.env and return a dict of {provider_id: api_key}.

    Also returns default_provider and custom_base_url / ollama_host.
    """
    result = {
        "keys": {},           # provider_id → raw api key
        "default": "",        # default provider id
        "custom_base_url": "",
        "ollama_host": "",
    }
    env_vars = _read_env_file()
    if not env_vars:
        return result

    result["default"] = env_vars.get("LLM_PROVIDER", "")
    result["custom_base_url"] = env_vars.get("CUSTOM_BASE_URL", "")
    result["ollama_host"] = env_vars.get(
        "OLLAMA_HOST", "http://localhost:11434"
    )

    for pid, preset in PROVIDERS.items():
        key_env = preset["api_key_env"]
        if key_env and key_env in env_vars:
            result["keys"][pid] = env_vars[key_env]
        elif pid == "ollama":
            # Ollama is "configured" if the host is reachable
            result["keys"][pid] = ""

    return result


def _read_env_file():
    """Parse ~/.pegasus-ai/.env into a dict."""
    env_vars = {}
    if not ENV_FILE.exists():
        return env_vars
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            env_vars[key.strip()] = value.strip()
    return env_vars


def _mask_key(key):
    """Mask an API key, showing only first 4 and last 4 characters."""
    if not key or len(key) <= 8:
        return "****" if key else ""
    return key[:4] + "****" + key[-4:]


# ── Model discovery ──────────────────────────────────────────────

def fetch_models(base_url, api_key):
    """Fetch available model IDs from an OpenAI-compatible /models endpoint.

    Returns (model_ids: list[str], error: str|None).
    """
    import urllib.request
    import urllib.error

    if not base_url:
        return [], "No base URL configured."

    base = base_url.rstrip("/")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        req = urllib.request.Request(f"{base}/models", headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            model_ids = sorted(
                m.get("id", "") for m in data.get("data", []) if m.get("id")
            )
            if model_ids:
                return model_ids, None
            return [], "Endpoint returned no models."
    except urllib.error.HTTPError as e:
        return [], f"HTTP {e.code}: {e.reason}"
    except Exception as e:
        return [], f"Failed to fetch models: {e}"


def _discover_models_for_provider(pid, api_key):
    """Try to fetch models for a provider; fall back to default_model."""
    preset = PROVIDERS[pid]
    base_url = preset["base_url"]

    # Skip model fetch for Anthropic (their /models endpoint needs special header)
    if pid == "anthropic":
        return [preset["default_model"]]

    models, _ = fetch_models(base_url, api_key)
    if models:
        return models
    # Fallback
    if preset["default_model"]:
        return [preset["default_model"]]
    return []


# ── Saving ───────────────────────────────────────────────────────

def save_all(keys, default_provider, progress_cb=None):
    """Save API keys for configured providers and write tool configs.

    Args:
        keys: dict of {provider_id: api_key_string}
        default_provider: which provider to use as the default
        progress_cb: optional callable(message) for progress updates

    Returns (success: bool, message: str).
    """
    def _log(msg):
        if progress_cb:
            progress_cb(msg)

    PEGASUS_AI_DIR.mkdir(parents=True, exist_ok=True)

    # Filter to providers that actually have keys
    configured = {}
    for pid, key in keys.items():
        if key and key.strip():
            configured[pid] = key.strip()

    if not configured:
        return False, "No providers configured. Enter at least one API key."

    if default_provider not in configured:
        default_provider = next(iter(configured))

    # ── Write .env ────────────────────────────────────────────
    _log("Writing .env ...")
    lines = [
        "# Auto-generated by LLM_Setup notebook",
        f"LLM_PROVIDER={default_provider}",
        f"LLM_MODEL={PROVIDERS[default_provider]['default_model']}",
    ]
    for pid, key in configured.items():
        preset = PROVIDERS[pid]
        if preset["api_key_env"] and key:
            lines.append(f"{preset['api_key_env']}={key}")

    # Set OPENAI_API_BASE / OPENAI_API_KEY for the default provider
    # (needed by tools that read standard OpenAI env vars)
    dp = PROVIDERS[default_provider]
    if default_provider in ("fabric", "nrp"):
        lines.append(f"OPENAI_API_BASE={dp['base_url']}")
        lines.append(f"OPENAI_API_KEY={configured[default_provider]}")

    ENV_FILE.write_text("\n".join(lines) + "\n")
    ENV_FILE.chmod(0o600)

    # Export into current process
    for line in lines:
        if "=" in line and not line.startswith("#"):
            k, _, v = line.partition("=")
            os.environ[k] = v

    # ── Discover models for each configured provider ──────────
    _log("Discovering models ...")
    provider_models = {}
    for pid in configured:
        _log(f"  Fetching models for {PROVIDERS[pid]['name']} ...")
        provider_models[pid] = _discover_models_for_provider(
            pid, configured.get(pid, "")
        )

    # ── Write tool configs ────────────────────────────────────
    errors = []

    _log("Writing opencode.json ...")
    try:
        _write_opencode_config(configured, provider_models, default_provider)
    except Exception as e:
        errors.append(f"opencode.json: {e}")

    # Shell script for pegasus-ai env var propagation
    try:
        subprocess.run(
            ["bash", "-c", f". {CONFIGURE_SCRIPT}"],
            env=os.environ.copy(),
            capture_output=True, text=True, timeout=10,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    # ── Summary ───────────────────────────────────────────────
    names = [PROVIDERS[p]["name"] for p in configured]
    msg = f"Saved {len(configured)} provider(s): {', '.join(names)}"
    msg += f"\nDefault: {PROVIDERS[default_provider]['name']}"
    total_models = sum(len(v) for v in provider_models.values())
    msg += f"\nDiscovered {total_models} model(s) across all providers."
    if errors:
        msg += f"\nWarnings: {'; '.join(errors)}"
    return True, msg


# ── Tool config writers (multi-provider) ─────────────────────────

def _write_opencode_config(configured, provider_models, default_provider):
    """Write ~/work/opencode.json with all configured providers.

    Delegates to the opencode_extension.config_builder module so the
    config includes instructions, agent prompts, and slash commands.
    Falls back to a minimal config if the extension isn't installed.
    """
    if not WORKSPACE.is_dir():
        return

    # Build env_vars dict for config_builder
    env_vars = {}
    for pid, key in configured.items():
        preset = PROVIDERS[pid]
        if preset["api_key_env"] and key:
            env_vars[preset["api_key_env"]] = key
    env_vars["LLM_PROVIDER"] = default_provider
    dp = PROVIDERS[default_provider]
    env_vars["LLM_MODEL"] = dp["default_model"]

    try:
        from opencode_extension.config_builder import build_opencode_config
        config = build_opencode_config(env_vars, provider=default_provider)
        write_cfg = {k: v for k, v in config.items() if not k.startswith("_")}
    except ImportError:
        # Fallback: minimal config without instructions/commands
        write_cfg = {"$schema": "https://opencode.ai/config.json"}
        providers = {}
        for pid in configured:
            preset = PROVIDERS[pid]
            models_dict = {m: {"name": m} for m in provider_models.get(pid, [])}
            if not models_dict and preset["default_model"]:
                models_dict = {preset["default_model"]: {"name": preset["default_model"]}}
            options = {}
            if pid in ("anthropic", "openai"):
                options["apiKey"] = f"{{env:{preset['api_key_env']}}}"
            else:
                options["baseURL"] = preset["base_url"]
                if preset["api_key_env"]:
                    options["apiKey"] = f"{{env:{preset['api_key_env']}}}"
            npm = {"anthropic": "@ai-sdk/anthropic", "openai": "@ai-sdk/openai"
                   }.get(pid, "@ai-sdk/openai-compatible")
            providers[pid] = {"npm": npm, "name": preset["name"],
                              "options": options, "models": models_dict}
        write_cfg["provider"] = providers
        default_model = dp["default_model"]
        dp_models = provider_models.get(default_provider, [])
        if dp_models:
            default_model = dp_models[0]
        write_cfg["model"] = f"{default_provider}/{default_model}"

    with open(WORKSPACE / "opencode.json", "w") as f:
        json.dump(write_cfg, f, indent=2)
        f.write("\n")


# ── Connection test ──────────────────────────────────────────────

def test_connection(base_url, api_key):
    """Test connectivity to an LLM endpoint via /models.

    Returns (success: bool, message: str).
    """
    import urllib.request
    import urllib.error

    if not base_url:
        return False, "No base URL configured."

    base = base_url.rstrip("/")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        req = urllib.request.Request(f"{base}/models", headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            model_ids = [m.get("id", "") for m in data.get("data", [])]
            if model_ids:
                available = ", ".join(model_ids[:5])
                suffix = "..." if len(model_ids) > 5 else ""
                return True, f"Connected! Models: {available}{suffix}"
            return True, "Connected! (no model list returned)"
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}: {e.reason}"
    except Exception as e:
        return False, f"Connection failed: {e}"
