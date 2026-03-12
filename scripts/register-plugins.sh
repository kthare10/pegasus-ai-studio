#!/usr/bin/env bash
# register-plugins.sh — First-launch Claude Code plugin registration.
# Copies the marketplace from the image and registers plugins.
# Idempotent: skips if marker file exists.

set -euo pipefail

PEGASUS_AI_DIR="${HOME}/.pegasus-ai"
MARKER="${PEGASUS_AI_DIR}/.plugins-registered"

# Skip if already registered
if [ -f "${MARKER}" ]; then
    echo "[pegasus-ai] Plugins already registered, skipping."
    exit 0
fi

mkdir -p "${PEGASUS_AI_DIR}"

# Copy marketplace from image to user home
if [ -d "/opt/pegasus-ai/claude-plugin-marketplace" ]; then
    cp -r /opt/pegasus-ai/claude-plugin-marketplace "${PEGASUS_AI_DIR}/claude-plugin-marketplace"
else
    echo "[pegasus-ai] Warning: marketplace not found at /opt/pegasus-ai/claude-plugin-marketplace"
    exit 0
fi

# Register plugins with Claude Code (requires ANTHROPIC_API_KEY)
if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
    echo "[pegasus-ai] No ANTHROPIC_API_KEY set — skipping Claude Code plugin registration."
    echo "[pegasus-ai] Run 'pegasus-ai-setup' to configure your LLM provider, then re-run:"
    echo "  register-plugins"
    exit 0
fi

echo "[pegasus-ai] Registering Claude Code plugins..."

if command -v claude >/dev/null 2>&1; then
    claude plugin marketplace add "${PEGASUS_AI_DIR}/claude-plugin-marketplace" || true
    claude plugin install pegasus-ai@scitech || true
    claude plugin install pegasus-dev@scitech || true
    echo "[pegasus-ai] Claude Code plugins registered successfully."
else
    echo "[pegasus-ai] Warning: claude command not found — skipping plugin registration."
fi

# Mark as complete
touch "${MARKER}"
echo "[pegasus-ai] Plugin registration complete."
