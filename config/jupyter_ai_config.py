"""Jupyter AI server-side configuration.

Reads LLM_PROVIDER / LLM_MODEL / API keys from the environment (set by
configure-llm.sh or the LLM_Setup notebook) and configures Jupyter AI's
chat sidebar to use the correct provider automatically.

This file is loaded by Jupyter AI's server extension on startup.
"""

import os

c = get_config()  # noqa: F821 — provided by Jupyter config loader

provider = os.environ.get("LLM_PROVIDER", "")
model = os.environ.get("LLM_MODEL", "")

# ── Map LLM_PROVIDER to Jupyter AI's language-model ID ────────────
# Jupyter AI model IDs follow the pattern "provider-chat:model-name".
# For anthropic/openai it uses built-in LangChain integrations.
# For OpenAI-compatible endpoints (fabric, nrp, custom, ollama) we
# route through the openai-chat provider with OPENAI_API_BASE set.

if provider == "anthropic" and model:
    c.AiExtension.default_language_model = f"anthropic-chat:{model}"
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if api_key:
        c.AiExtension.default_api_keys = {"ANTHROPIC_API_KEY": api_key}

elif provider == "openai" and model:
    c.AiExtension.default_language_model = f"openai-chat:{model}"
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if api_key:
        c.AiExtension.default_api_keys = {"OPENAI_API_KEY": api_key}

elif provider in ("fabric", "nrp", "custom", "ollama") and model:
    # All OpenAI-compatible endpoints go through openai-chat with a
    # custom base URL.  OPENAI_API_BASE and OPENAI_API_KEY should
    # already be in the environment (set by configure-llm.sh / .env).
    c.AiExtension.default_language_model = f"openai-chat:{model}"
    api_keys = {}
    openai_key = os.environ.get("OPENAI_API_KEY", "")
    openai_base = os.environ.get("OPENAI_API_BASE", "")
    if openai_key:
        api_keys["OPENAI_API_KEY"] = openai_key
    if openai_base:
        api_keys["OPENAI_API_BASE"] = openai_base
    if api_keys:
        c.AiExtension.default_api_keys = api_keys
