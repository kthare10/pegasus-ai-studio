#!/usr/bin/env bash
# pegasus-ai-setup — Interactive LLM provider configuration wizard.
# Writes provider, model, and API key to $HOME/.pegasus-ai/.env and
# propagates settings to all AI tools via configure-llm.sh.

set -euo pipefail

PEGASUS_AI_DIR="${HOME}/.pegasus-ai"
ENV_FILE="${PEGASUS_AI_DIR}/.env"

mkdir -p "${PEGASUS_AI_DIR}"

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║           Pegasus AI Workbench — LLM Setup              ║"
echo "╠══════════════════════════════════════════════════════════╣"
echo "║  Configure which LLM provider the AI tools will use.    ║"
echo "║  API keys are stored locally and never leave this host. ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""
echo "Select your LLM provider:"
echo ""
echo "  1) Anthropic (Claude)      — requires ANTHROPIC_API_KEY"
echo "  2) OpenAI (GPT)            — requires OPENAI_API_KEY"
echo "  3) Custom endpoint         — any OpenAI-compatible API"
echo "  4) Ollama (local)          — runs models locally"
echo "  5) FABRIC AI               — requires FABRIC_AI_API_KEY"
echo "  6) NRP (Nautilus)          — requires NRP_API_KEY"
echo "  7) Skip for now"
echo ""

read -rp "Choice [1-7]: " choice

case "${choice}" in
    1)
        LLM_PROVIDER="anthropic"
        DEFAULT_MODEL="claude-sonnet-4-5-20250929"
        read -rp "Anthropic API key: " -s api_key
        echo ""
        read -rp "Model [${DEFAULT_MODEL}]: " model_input
        LLM_MODEL="${model_input:-${DEFAULT_MODEL}}"
        cat > "${ENV_FILE}" <<EOF
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=${api_key}
LLM_MODEL=${LLM_MODEL}
EOF
        ;;
    2)
        LLM_PROVIDER="openai"
        DEFAULT_MODEL="gpt-4o"
        read -rp "OpenAI API key: " -s api_key
        echo ""
        read -rp "Model [${DEFAULT_MODEL}]: " model_input
        LLM_MODEL="${model_input:-${DEFAULT_MODEL}}"
        cat > "${ENV_FILE}" <<EOF
LLM_PROVIDER=openai
OPENAI_API_KEY=${api_key}
LLM_MODEL=${LLM_MODEL}
EOF
        ;;
    3)
        LLM_PROVIDER="custom"
        DEFAULT_MODEL="gpt-4o"
        read -rp "Endpoint base URL (e.g. https://llm.university.edu/v1): " base_url
        read -rp "API key: " -s api_key
        echo ""
        read -rp "Model name (e.g. meta-llama/Llama-3.3-70B): " model_input
        LLM_MODEL="${model_input:-${DEFAULT_MODEL}}"
        cat > "${ENV_FILE}" <<EOF
LLM_PROVIDER=custom
OPENAI_API_BASE=${base_url}
OPENAI_API_KEY=${api_key}
OPENAI_MODEL=${LLM_MODEL}
LLM_MODEL=${LLM_MODEL}
EOF
        ;;
    4)
        LLM_PROVIDER="ollama"
        DEFAULT_MODEL="qwen2.5-coder:7b"
        read -rp "Ollama host [http://localhost:11434]: " ollama_host
        ollama_host="${ollama_host:-http://localhost:11434}"
        read -rp "Model [${DEFAULT_MODEL}]: " model_input
        LLM_MODEL="${model_input:-${DEFAULT_MODEL}}"
        cat > "${ENV_FILE}" <<EOF
LLM_PROVIDER=ollama
OLLAMA_HOST=${ollama_host}
LLM_MODEL=${LLM_MODEL}
EOF
        ;;
    5)
        LLM_PROVIDER="fabric"
        DEFAULT_MODEL="qwen3-coder-30b"
        read -rp "FABRIC AI API key: " -s api_key
        echo ""
        read -rp "Model [${DEFAULT_MODEL}]: " model_input
        LLM_MODEL="${model_input:-${DEFAULT_MODEL}}"
        cat > "${ENV_FILE}" <<EOF
LLM_PROVIDER=fabric
FABRIC_AI_API_KEY=${api_key}
OPENAI_API_BASE=https://ai.fabric-testbed.net/v1
OPENAI_API_KEY=${api_key}
LLM_MODEL=${LLM_MODEL}
EOF
        ;;
    6)
        LLM_PROVIDER="nrp"
        DEFAULT_MODEL="qwen3-coder-30b"
        read -rp "NRP API key: " -s api_key
        echo ""
        read -rp "Model [${DEFAULT_MODEL}]: " model_input
        LLM_MODEL="${model_input:-${DEFAULT_MODEL}}"
        cat > "${ENV_FILE}" <<EOF
LLM_PROVIDER=nrp
NRP_API_KEY=${api_key}
OPENAI_API_BASE=https://ellm.nrp-nautilus.io/v1
OPENAI_API_KEY=${api_key}
LLM_MODEL=${LLM_MODEL}
EOF
        ;;
    7)
        echo ""
        echo "Skipped. Run 'pegasus-ai-setup' again when ready."
        exit 0
        ;;
    *)
        echo "Invalid choice. Run 'pegasus-ai-setup' again."
        exit 1
        ;;
esac

# Secure the env file
chmod 600 "${ENV_FILE}"

echo ""
echo "Configuration saved to ${ENV_FILE}"
echo "  Provider: ${LLM_PROVIDER}"
echo "  Model:    ${LLM_MODEL}"

# Propagate settings to all tools
echo ""
echo "Propagating settings to AI tools..."
export LLM_PROVIDER LLM_MODEL
# shellcheck source=/dev/null
. /etc/profile.d/pegasus-ai-llm.sh

# Update pegasus-ai config.yaml
python3 -c "
import os, sys
try:
    from pegasus_ai.config import Config, CONFIG_DIR, CONFIG_FILE
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    cfg = Config.load()
    cfg.save()
    print('  pegasus-ai config updated.')
except ImportError:
    print('  pegasus-ai not installed — skipping config update.')
" || true

# Attempt plugin registration if not done yet
if [ ! -f "${PEGASUS_AI_DIR}/.plugins-registered" ]; then
    echo ""
    echo "Registering Claude Code plugins..."
    register-plugins || true
fi

echo ""
echo "Setup complete! Your AI tools are configured."
echo ""
echo "  Provider: ${LLM_PROVIDER}"
echo "  Model:    ${LLM_MODEL}"
echo ""
echo "Open a terminal and try: claude or opencode"
