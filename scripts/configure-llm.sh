#!/usr/bin/env bash
# configure-llm.sh — Sourced at login via /etc/profile.d/
# Reads LLM_PROVIDER, LLM_MODEL, and API key env vars, then writes
# tool-specific configs so all AI tools use the same provider/model.

PEGASUS_AI_DIR="${HOME}/.pegasus-ai"
ENV_FILE="${PEGASUS_AI_DIR}/.env"
WORK_DIR="${HOME}/work"

# Source the user's .env if it exists
if [ -f "${ENV_FILE}" ]; then
    set -a
    # shellcheck source=/dev/null
    . "${ENV_FILE}"
    set +a
fi

LLM_PROVIDER="${LLM_PROVIDER:-}"

# Nothing to do if no provider is set
[ -z "${LLM_PROVIDER}" ] && return 0 2>/dev/null || true

# Resolve default model per provider (overridable via LLM_MODEL)
case "${LLM_PROVIDER}" in
    anthropic) _DEFAULT_MODEL="claude-sonnet-4-5-20250929" ;;
    openai)    _DEFAULT_MODEL="gpt-4o" ;;
    fabric)    _DEFAULT_MODEL="qwen3-coder-30b" ;;
    nrp)       _DEFAULT_MODEL="qwen3-coder-30b" ;;
    custom)    _DEFAULT_MODEL="${OPENAI_MODEL:-gpt-4o}"
               # Support both old OPENAI_API_BASE and new CUSTOM_BASE_URL
               export OPENAI_API_BASE="${OPENAI_API_BASE:-${CUSTOM_BASE_URL:-}}"
               export OPENAI_API_KEY="${OPENAI_API_KEY:-${CUSTOM_API_KEY:-}}"
               ;;
    ollama)    _DEFAULT_MODEL="qwen2.5-coder:7b" ;;
    *)         _DEFAULT_MODEL="claude-sonnet-4-5-20250929" ;;
esac
LLM_MODEL="${LLM_MODEL:-${_DEFAULT_MODEL}}"
export LLM_MODEL

# ── OpenCode configuration ────────────────────────────────────
# Uses the same config_builder module as the OpenCode web extension
# so the full config (instructions, agent prompts, commands) is written.
configure_opencode() {
    [ ! -d "${WORK_DIR}" ] && return 0
    python3 -c "
import json, os, sys
workspace = os.environ.get('HOME', '/tmp') + '/work'
config_path = workspace + '/opencode.json'
try:
    from opencode_extension.config_builder import build_opencode_config
    env_vars = {}
    env_file = os.path.join(os.environ.get('HOME', '/tmp'), '.pegasus-ai', '.env')
    try:
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, _, v = line.partition('=')
                    env_vars[k.strip()] = v.strip()
    except FileNotFoundError:
        pass
    for k in ['LLM_PROVIDER','LLM_MODEL','ANTHROPIC_API_KEY','OPENAI_API_KEY',
              'FABRIC_AI_API_KEY','NRP_API_KEY','CUSTOM_BASE_URL','OLLAMA_HOST']:
        if k not in env_vars and os.environ.get(k):
            env_vars[k] = os.environ[k]
    provider = env_vars.get('LLM_PROVIDER', os.environ.get('LLM_PROVIDER', ''))
    if not provider:
        sys.exit(0)
    config = build_opencode_config(env_vars, provider=provider)
    write_cfg = {k: v for k, v in config.items() if not k.startswith('_')}
    with open(config_path, 'w') as f:
        json.dump(write_cfg, f, indent=2)
        f.write('\n')
except ImportError:
    pass
" 2>/dev/null || true
}

# ── pegasus-ai configuration (env vars consumed by config.py) ─
configure_pegasus_ai() {
    case "${LLM_PROVIDER}" in
        anthropic)
            export PEGASUS_AI_LLM_BASE_URL="https://api.anthropic.com/v1"
            export PEGASUS_AI_LLM_MODEL="${LLM_MODEL}"
            export PEGASUS_AI_LLM_API_KEY="${ANTHROPIC_API_KEY:-}"
            ;;
        openai)
            export PEGASUS_AI_LLM_BASE_URL="https://api.openai.com/v1"
            export PEGASUS_AI_LLM_MODEL="${LLM_MODEL}"
            export PEGASUS_AI_LLM_API_KEY="${OPENAI_API_KEY:-}"
            ;;
        fabric)
            export PEGASUS_AI_LLM_BASE_URL="https://ai.fabric-testbed.net/v1"
            export PEGASUS_AI_LLM_MODEL="${LLM_MODEL}"
            export PEGASUS_AI_LLM_API_KEY="${FABRIC_AI_API_KEY:-}"
            ;;
        nrp)
            export PEGASUS_AI_LLM_BASE_URL="https://ellm.nrp-nautilus.io/v1"
            export PEGASUS_AI_LLM_MODEL="${LLM_MODEL}"
            export PEGASUS_AI_LLM_API_KEY="${NRP_API_KEY:-}"
            ;;
        custom)
            export PEGASUS_AI_LLM_BASE_URL="${OPENAI_API_BASE:-}"
            export PEGASUS_AI_LLM_MODEL="${LLM_MODEL}"
            export PEGASUS_AI_LLM_API_KEY="${OPENAI_API_KEY:-}"
            ;;
        ollama)
            export PEGASUS_AI_LLM_BASE_URL="${OLLAMA_HOST:-http://localhost:11434}/v1"
            export PEGASUS_AI_LLM_MODEL="${LLM_MODEL}"
            export PEGASUS_AI_LLM_API_KEY="ollama"
            ;;
    esac
}

# Run all configurations
configure_opencode
configure_pegasus_ai
