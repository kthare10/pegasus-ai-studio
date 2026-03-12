#!/usr/bin/env bash
# entrypoint.sh — Container entrypoint for Pegasus AI Workbench.
# Seeds AI tool configs, runs first-launch setup, then delegates
# to the scipy-notebook's standard Jupyter startup.

set -euo pipefail

PEGASUS_AI_DIR="${HOME}/.pegasus-ai"
INIT_MARKER="${PEGASUS_AI_DIR}/.initialized"
WORK_DIR="${HOME}/work"
AI_TOOLS_SRC="/opt/pegasus-ai/ai-tools"

# Source .env if present (e.g. bind-mounted or created by setup wizard)
if [ -f "${PEGASUS_AI_DIR}/.env" ]; then
    set -a
    # shellcheck source=/dev/null
    . "${PEGASUS_AI_DIR}/.env"
    set +a
fi

# ── First-launch setup ────────────────────────────────────────
if [ ! -f "${INIT_MARKER}" ]; then
    mkdir -p "${PEGASUS_AI_DIR}" "${WORK_DIR}"

    echo ""
    echo "══════════════════════════════════════════════════════════"
    echo "  Welcome to the Pegasus AI Workbench!"
    echo "══════════════════════════════════════════════════════════"
    echo ""

    # Claude Code context (cp -n: don't overwrite user edits)
    if [ -d "${AI_TOOLS_SRC}" ]; then
        cp -n "${AI_TOOLS_SRC}/claude-code/CLAUDE.md" "${WORK_DIR}/CLAUDE.md" 2>/dev/null || true
        # MCP server config (Pegasus docs via GitMCP)
        cp -n "${AI_TOOLS_SRC}/claude-code/mcp.json" "${WORK_DIR}/.mcp.json" 2>/dev/null || true
    fi

    # Register Claude Code plugins (fails gracefully without API key)
    register-plugins || true

    # Print setup hint if no provider is configured
    if [ -z "${LLM_PROVIDER:-}" ] && [ -z "${ANTHROPIC_API_KEY:-}" ]; then
        echo ""
        echo "  To configure your LLM provider:"
        echo "    - Open LLM_Setup.ipynb in JupyterLab (recommended)"
        echo "    - Or run 'pegasus-ai-setup' in a terminal"
        echo ""
    fi

    touch "${INIT_MARKER}"
fi

# ── Seed AI tool configs (every startup) ──────────────────────
# Always update non-user-edited files so existing volumes pick up
# changes after an image rebuild.
if [ -d "${AI_TOOLS_SRC}" ]; then
    mkdir -p "${WORK_DIR}"

    # Shared context → AGENTS.md (always update to latest from image)
    cp -f "${AI_TOOLS_SRC}/shared/PEGASUS_AI.md" "${WORK_DIR}/AGENTS.md" 2>/dev/null || true

    # Copy entire opencode/ directory contents → .opencode/
    # This includes agents/, skills/, and commands/ subdirectories.
    if [ -d "${AI_TOOLS_SRC}/opencode" ]; then
        mkdir -p "${WORK_DIR}/.opencode"

        # Agents → .opencode/agents/ (always update)
        if [ -d "${AI_TOOLS_SRC}/opencode/agents" ]; then
            mkdir -p "${WORK_DIR}/.opencode/agents"
            cp -f "${AI_TOOLS_SRC}"/opencode/agents/*.md "${WORK_DIR}/.opencode/agents/" 2>/dev/null || true
        fi

        # Skills → .opencode/skills/<name>/SKILL.md (always update)
        if [ -d "${AI_TOOLS_SRC}/opencode/skills" ]; then
            for skill_file in "${AI_TOOLS_SRC}"/opencode/skills/*.md; do
                [ -f "${skill_file}" ] || continue
                skill_name="$(basename "${skill_file}" .md)"
                mkdir -p "${WORK_DIR}/.opencode/skills/${skill_name}"
                cp -f "${skill_file}" "${WORK_DIR}/.opencode/skills/${skill_name}/SKILL.md"
            done
        fi

        # Commands → .opencode/commands/<name>.md (always update)
        if [ -d "${AI_TOOLS_SRC}/opencode/commands" ]; then
            mkdir -p "${WORK_DIR}/.opencode/commands"
            cp -f "${AI_TOOLS_SRC}"/opencode/commands/*.md "${WORK_DIR}/.opencode/commands/" 2>/dev/null || true
        fi
    fi

    # Clean up legacy paths
    rm -rf "${WORK_DIR}/.opencode/agent-prompts" 2>/dev/null || true
fi

# ── Copy LLM setup notebook to home directory (every startup) ──
NOTEBOOKS_SRC="/opt/pegasus-ai/notebooks"
if [ -d "${NOTEBOOKS_SRC}" ]; then
    cp -n "${NOTEBOOKS_SRC}/LLM_Setup.ipynb" "${HOME}/LLM_Setup.ipynb" 2>/dev/null || true
    # Always update the helper module (not user-edited, needs latest code)
    cp -f "${NOTEBOOKS_SRC}/llm_setup_helpers.py" "${HOME}/llm_setup_helpers.py" 2>/dev/null || true
fi

# ── Propagate LLM settings to tool configs ────────────────────
# shellcheck source=/dev/null
. /etc/profile.d/pegasus-ai-llm.sh || true

# ── Delegate to Jupyter startup ───────────────────────────────
# The scipy-notebook image uses start-notebook.py as its entrypoint.
# Pass through all arguments (e.g. --NotebookApp.token).
exec /usr/local/bin/start-notebook.py "$@"
