"""Multi-provider config generator for opencode.json.

Builds a complete opencode.json with all configured providers and their
discovered models, adapted from llm_setup_helpers.py and configure-llm.sh.
"""

import copy
import json
import os
import urllib.error
import urllib.request

# Provider presets — mirrors llm_setup_helpers.PROVIDERS
PROVIDERS = {
    "anthropic": {
        "name": "Anthropic",
        "npm": "@ai-sdk/anthropic",
        "base_url": None,  # No /models endpoint; use static list
        "default_model": "claude-sonnet-4-5-20250929",
        "api_key_env": "ANTHROPIC_API_KEY",
    },
    "openai": {
        "name": "OpenAI",
        "npm": "@ai-sdk/openai",
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o",
        "api_key_env": "OPENAI_API_KEY",
    },
    "fabric": {
        "name": "FABRIC AI",
        "npm": "@ai-sdk/openai-compatible",
        "base_url": "https://ai.fabric-testbed.net/v1",
        "default_model": "qwen3-coder-30b",
        "api_key_env": "FABRIC_AI_API_KEY",
    },
    "nrp": {
        "name": "NRP (Nautilus)",
        "npm": "@ai-sdk/openai-compatible",
        "base_url": "https://ellm.nrp-nautilus.io/v1",
        "default_model": "qwen3-coder-30b",
        "api_key_env": "NRP_API_KEY",
    },
    "custom": {
        "name": "Custom Endpoint",
        "npm": "@ai-sdk/openai-compatible",
        "base_url": None,  # Read from CUSTOM_BASE_URL env
        "default_model": "",
        "api_key_env": "CUSTOM_API_KEY",
    },
    "ollama": {
        "name": "Ollama",
        "npm": "@ai-sdk/openai-compatible",
        "base_url": None,  # Read from OLLAMA_HOST env
        "default_model": "qwen2.5-coder:7b",
        "api_key_env": None,
    },
}

# Preferred models for small/summary tasks
_PREFERRED_SMALL = ["qwen3-coder-8b", "qwen3-8b", "qwen3-coder-30b"]

# Providers that need the model proxy
PROXY_PROVIDERS = {"fabric", "nrp", "custom", "ollama"}


def _resolve_base_url(pid, env_vars):
    """Resolve the actual base URL for a provider."""
    preset = PROVIDERS[pid]
    if pid == "custom":
        return env_vars.get("CUSTOM_BASE_URL", env_vars.get("OPENAI_API_BASE", ""))
    if pid == "ollama":
        host = env_vars.get("OLLAMA_HOST", "http://localhost:11434")
        return f"{host}/v1"
    return preset["base_url"] or ""


def _resolve_api_key(pid, env_vars):
    """Resolve the API key for a provider from env vars."""
    preset = PROVIDERS[pid]
    if pid == "ollama":
        return "ollama"
    key_env = preset["api_key_env"]
    if key_env:
        return env_vars.get(key_env, "")
    return ""


def fetch_models(base_url, api_key):
    """Fetch available model IDs from an OpenAI-compatible /models endpoint.

    Returns (model_ids: list[str], error: str|None).
    """
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


def _pick_model(models, preferences, fallback):
    """Pick best model from available list using preference order."""
    for pref in preferences:
        for m in models:
            if pref in m.lower():
                return m
    return models[0] if models else fallback


def discover_all_models(env_vars):
    """Discover models for all configured providers.

    Returns {provider_id: [model_id, ...]}.
    """
    result = {}
    for pid, preset in PROVIDERS.items():
        api_key = _resolve_api_key(pid, env_vars)
        if not api_key and pid != "ollama":
            continue

        # Anthropic has no standard /models endpoint
        if pid == "anthropic":
            if env_vars.get("ANTHROPIC_API_KEY"):
                result[pid] = [preset["default_model"]]
            continue

        base_url = _resolve_base_url(pid, env_vars)
        if not base_url:
            continue

        models, _ = fetch_models(base_url, api_key)
        if models:
            result[pid] = models
        elif preset["default_model"]:
            result[pid] = [preset["default_model"]]

    return result


def build_opencode_config(env_vars, provider=None, model_override=None):
    """Build a complete opencode.json config dict.

    Args:
        env_vars: dict of environment variables (from .env file)
        provider: default provider ID (from LLM_PROVIDER)
        model_override: optional model to use instead of default

    Returns dict with extra keys _default, _allowed (stripped before writing).
    """
    if not provider:
        provider = env_vars.get("LLM_PROVIDER", "anthropic")

    # Discover models for all configured providers
    provider_models = discover_all_models(env_vars)

    # Build provider sections
    providers = {}
    for pid, models in provider_models.items():
        preset = PROVIDERS[pid]
        models_dict = {m: {"name": m} for m in models}

        base_url = _resolve_base_url(pid, env_vars)
        options = {}
        if pid == "anthropic":
            options["apiKey"] = "{env:ANTHROPIC_API_KEY}"
        elif pid == "openai":
            options["apiKey"] = "{env:OPENAI_API_KEY}"
        elif pid == "ollama":
            options["baseURL"] = base_url
            options["apiKey"] = "ollama"
        else:
            options["baseURL"] = base_url
            key_env = preset["api_key_env"]
            options["apiKey"] = f"{{env:{key_env}}}" if key_env else ""

        providers[pid] = {
            "npm": preset["npm"],
            "name": preset["name"],
            "options": options,
            "models": models_dict,
        }

    # Determine default model
    dp_models = provider_models.get(provider, [])
    default_model = model_override or env_vars.get("LLM_MODEL", "")
    if not default_model:
        preset = PROVIDERS.get(provider, {})
        default_model = preset.get("default_model", "claude-sonnet-4-5-20250929")
        if dp_models:
            default_model = dp_models[0]

    # Ensure default provider exists in config even if model discovery failed
    if provider not in providers:
        preset = PROVIDERS.get(provider, PROVIDERS["anthropic"])
        base_url = _resolve_base_url(provider, env_vars)
        options = {}
        if provider == "anthropic":
            options["apiKey"] = "{env:ANTHROPIC_API_KEY}"
        elif provider == "openai":
            options["apiKey"] = "{env:OPENAI_API_KEY}"
        elif provider == "ollama":
            options["baseURL"] = base_url
            options["apiKey"] = "ollama"
        else:
            if base_url:
                options["baseURL"] = base_url
            key_env = preset.get("api_key_env")
            if key_env:
                options["apiKey"] = f"{{env:{key_env}}}"

        providers[provider] = {
            "npm": preset["npm"],
            "name": preset["name"],
            "options": options,
            "models": {default_model: {"name": default_model}},
        }

    config = {
        "$schema": "https://opencode.ai/config.json",
        "provider": providers,
        "model": f"{provider}/{default_model}",
    }

    # Pick small model for non-native providers
    if provider in PROXY_PROVIDERS and dp_models:
        small = _pick_model(dp_models, _PREFERRED_SMALL, default_model)
        config["small_model"] = f"{provider}/{small}"

    # ── Instructions, agents, and commands ──────────────────────
    # Explicitly load AGENTS.md into context (auto-discovery works
    # but being explicit helps smaller models).
    config["instructions"] = ["AGENTS.md"]

    # Resolve workspace path for prompts
    workspace = os.path.join(os.environ.get("HOME", "/home/jovyan"), "work")

    # Custom agents — defined in config for reliable discovery.
    # File-based copies in .opencode/agents/ serve as backup.
    config["agent"] = {
        "build": {
            "prompt": _BUILD_AGENT_PROMPT_TEMPLATE.format(workspace=workspace),
        },
        "workflow-architect": {
            "description": "Expert Pegasus WMS workflow designer — DAGs, catalogs, job dependencies, data staging",
            "prompt": "{file:.opencode/agents/workflow-architect.md}",
        },
        "data-engineer": {
            "description": "Data acquisition, preprocessing, and pipeline integration for scientific workflows",
            "prompt": "{file:.opencode/agents/data-engineer.md}",
        },
        "pipeline-debugger": {
            "description": "Pegasus workflow debugging — analyze failures, read logs, fix broken pipelines",
            "prompt": "{file:.opencode/agents/pipeline-debugger.md}",
        },
    }

    # Slash commands that pre-fill context — these work even when the
    # model is too small to autonomously invoke the skill tool.
    # Deep-copy and resolve {workspace} in all templates.
    commands = copy.deepcopy(_COMMANDS_TEMPLATE)
    for cmd in commands.values():
        if "template" in cmd:
            cmd["template"] = cmd["template"].format(workspace=workspace)
    config["command"] = commands

    # ── MCP servers ────────────────────────────────────────────
    # Documentation via GitMCP (remote MCP servers)
    config["mcp"] = {
        "pegasus-docs": {
            "type": "remote",
            "url": "https://gitmcp.io/pegasus-isi/pegasus",
            "enabled": True,
        },
        "kiso-docs": {
            "type": "remote",
            "url": "https://gitmcp.io/pegasus-isi/kiso",
            "enabled": True,
        },
    }

    # Internal keys for model proxy (stripped before writing to file)
    allowed = dp_models if dp_models else [default_model]
    config["_default"] = default_model
    config["_allowed"] = allowed

    return config


# ── Build agent system prompt ──────────────────────────────────
# Concise so smaller LLMs (Qwen 7B-30B, Mistral, etc.) follow it.
# The {workspace} placeholder is filled in at config-generation time.
_BUILD_AGENT_PROMPT_TEMPLATE = """\
You are a Pegasus WMS workflow assistant in the Pegasus AI Workbench.
Your workspace directory is {workspace}.

WORKSPACE RULES (always follow):
1. Create EVERY workflow in its own subdirectory under {workspace}/.
   Example: mkdir -p {workspace}/my-workflow/bin
2. All files must go inside {workspace}/NAME-workflow/.
   Generate: workflow_generator.py, bin/STEP.py wrappers, README.md
3. NEVER create directories outside {workspace}/.

PEGASUS ESSENTIALS:
- from Pegasus.api import *
- 5 catalogs: Properties, SiteCatalog, TransformationCatalog, ReplicaCatalog, Workflow
- Wrapper scripts: argparse, subprocess.run(), sys.exit(result.returncode)
- stage_out=True only on final outputs
- Explicit file passing between jobs (never scan directories)

Read AGENTS.md for detailed patterns and examples.\
"""

# ── Slash commands ─────────────────────────────────────────────
# Pre-built prompts triggered by /command-name.  These bypass the
# need for the model to autonomously discover and invoke skills.
# The {workspace} placeholder is filled in at config-generation time.
_COMMANDS_TEMPLATE = {
    "new-workflow": {
        "description": "Create a new Pegasus workflow project",
        "template": (
            "Create a new Pegasus WMS workflow project based on this request:\n"
            "$ARGUMENTS\n\n"
            "STEP-BY-STEP INSTRUCTIONS (follow exactly):\n\n"
            "Step 1: Choose a short kebab-case name for the workflow "
            "(e.g. weather-forecast, csv-summary, earthquake-analysis).\n\n"
            "Step 2: Create the project directory under the workspace:\n"
            "  mkdir -p {workspace}/NAME-workflow/bin\n"
            "  cd {workspace}/NAME-workflow\n\n"
            "Step 3: Create these files inside that directory:\n"
            "  - workflow_generator.py (Pegasus DAG with all 5 catalogs: "
            "Properties, SiteCatalog, TransformationCatalog, ReplicaCatalog, Workflow)\n"
            "  - bin/STEP.py for each pipeline step (use argparse, propagate exit codes)\n"
            "  - README.md with usage instructions\n\n"
            "Step 4: Use 'from Pegasus.api import *' for the Pegasus Python API.\n"
            "Set stage_out=True only on final outputs. "
            "Pass files explicitly between jobs.\n\n"
            "Read AGENTS.md for detailed Pegasus patterns and examples."
        ),
    },
    "new-wrapper": {
        "description": "Generate a Pegasus wrapper script",
        "template": (
            "Generate a Pegasus WMS wrapper script.\n\n"
            "Rules:\n"
            "- Python 3 with #!/usr/bin/env python3\n"
            "- Use argparse for all inputs/outputs\n"
            "- Use subprocess.run() for external tools\n"
            "- Propagate exit codes (sys.exit(result.returncode))\n"
            "- Log to stderr\n"
            "- No directory scanning — explicit file paths only\n\n"
            "User request: $ARGUMENTS"
        ),
    },
    "new-dockerfile": {
        "description": "Generate a Dockerfile for a workflow",
        "template": (
            "Generate a Dockerfile for a Pegasus workflow.\n\n"
            "Rules:\n"
            "- One shared container for all workflow steps\n"
            "- Pin versions for reproducibility\n"
            "- Set PYTHONUNBUFFERED=1\n"
            "- apt-get for system deps, pip for Python\n\n"
            "User request: $ARGUMENTS"
        ),
    },
    "review-workflow": {
        "description": "Audit a workflow against Pegasus best practices",
        "template": (
            "Audit the Pegasus workflow in the current directory. Check:\n"
            "1. workflow_generator.py has all 5 catalogs\n"
            "2. Data staging uses Replica Catalog, stage_out only on final outputs\n"
            "3. Wrapper scripts use argparse, exit codes, error handling\n"
            "4. Containers registered in Transformation Catalog\n"
            "5. Dependencies correctly defined\n"
            "6. File passing is explicit (no directory scanning)\n"
            "7. Properties set (transfer threads, retries, cleanup)\n"
            "8. README.md exists\n\n"
            "Report PASS/WARN/FAIL for each category.\n"
            "$ARGUMENTS"
        ),
    },
    "debug-workflow": {
        "description": "Diagnose a Pegasus workflow failure",
        "template": (
            "Debug a Pegasus workflow failure.\n\n"
            "Steps:\n"
            "1. Run: pegasus-status <run-dir>\n"
            "2. Run: pegasus-analyzer <run-dir>\n"
            "3. Read .out and .err files for failed jobs\n"
            "4. Identify root cause and suggest fix\n\n"
            "User request: $ARGUMENTS"
        ),
    },
}
