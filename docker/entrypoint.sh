#!/usr/bin/env bash
# PegasusAI Studio container entrypoint.
#
# First-launch: initialize DB, seed config, prepare workspace.
# Then delegates to s6-overlay for process supervision.
# NOTE: This script runs as root. s6-overlay /init must start as root.

set -euo pipefail

PEGASUS_HOME="/home/pegasus"
WORK="${PEGASUS_HOME}/work"
STUDIO_DIR="${WORK}/.studio"
MARKER="${STUDIO_DIR}/.initialized"

# Ensure workspace exists and is owned by pegasus
mkdir -p "${WORK}" "${STUDIO_DIR}"
chown -R 1000:100 "${PEGASUS_HOME}"

# Resolve python path
PYTHON="$(which python3 2>/dev/null || which python 2>/dev/null || echo python3)"

# --- First-launch setup (run as pegasus) ---
if [ ! -f "${MARKER}" ]; then
    echo "[studio] First launch — initializing..."

    # Initialize database schema
    cd /opt/studio-api
    su -s /bin/bash pegasus -c "cd /opt/studio-api && ${PYTHON} init_db.py"

    # NOTE: LLM config is intentionally NOT seeded. The DB starts empty and the
    # user configures their provider/key via the Settings page. (Auto-seeding
    # from env vars previously persisted stale credentials, e.g. a leftover
    # FABRIC_AI_API_KEY, that the user never entered.)

    # Seed knowledge store into workspace
    if [ -d "/opt/pegasus-ai/knowledge" ]; then
        if [ -f "/opt/pegasus-ai/knowledge/references/PEGASUS_AI.md" ]; then
            cp /opt/pegasus-ai/knowledge/references/PEGASUS_AI.md "${WORK}/AGENTS.md"
            chown 1000:100 "${WORK}/AGENTS.md"
        fi
    fi

    touch "${MARKER}"
    chown 1000:100 "${MARKER}"
    echo "[studio] Initialization complete."
fi

# --- Every startup ---
# Ensure npm-global prefix dir exists and is writable by pegasus
mkdir -p "${PEGASUS_HOME}/.npm-global/bin"
chown -R 1000:100 "${PEGASUS_HOME}/.npm-global"

# Ensure HTCondor runtime dirs exist
mkdir -p /tmp/condor/{log,lock,run,spool,execute,cred}
chmod 755 /tmp/condor/execute

# Fix ownership of tool config dirs that npm postinstall may have created as root
for d in .codex .claude .antigravity .opencode; do
    [ -d "${PEGASUS_HOME}/${d}" ] && chown -R 1000:100 "${PEGASUS_HOME}/${d}"
done

# Propagate LLM config to installed tools (run as pegasus)
su -s /bin/bash pegasus -c "cd /opt/studio-api && ${PYTHON} propagate_llm.py" 2>/dev/null || true

# Hand off to s6-overlay for process supervision (must run as root)
exec /init
