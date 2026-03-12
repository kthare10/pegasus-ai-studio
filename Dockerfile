# Pegasus AI Workbench — Full image
# Bundles JupyterLab, Pegasus WMS, HTCondor, AI coding agents
# (Claude Code, OpenCode), Jupyter AI, and the scitech
# plugin marketplace.
#
# Build context: parent tool/ directory (so we can COPY pegasus-ai/ and
# claude-plugin-marketplace/ without duplicating files).
#
# Usage:
#   docker build -f pegasus-ai-workbench/Dockerfile -t pegasus-ai-workbench .

ARG VARIANT=latest

# ── Stage 1: Base + system packages ──────────────────────────
FROM quay.io/jupyter/scipy-notebook:python-3.11 AS base

USER root

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        git \
        vim \
        htop \
        tmux \
        jq \
        gnupg \
        software-properties-common \
    && rm -rf /var/lib/apt/lists/*

# ── Stage 2: Pegasus WMS + HTCondor ──────────────────────────
# Pegasus WMS
RUN pip install --no-cache-dir pegasus-wms==5.1.2

# HTCondor client (official APT repo for 25.x on Noble)
RUN curl -fsSL https://htcss-downloads.chtc.wisc.edu/repo/keys/HTCondor-25.x-Key \
        -o /etc/apt/keyrings/htcondor.asc \
    && curl -fsSL https://htcss-downloads.chtc.wisc.edu/repo/ubuntu/htcondor-25.x-noble.list \
        -o /etc/apt/sources.list.d/htcondor.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends condor \
    && rm -rf /var/lib/apt/lists/*

# ── Stage 3: AI coding agents ────────────────────────────────
# Node.js-based agents (Claude Code, OpenCode)
RUN npm install -g @anthropic-ai/claude-code opencode-ai

# ── Stage 4: Python AI packages + pegasus-ai ─────────────────
RUN pip install --no-cache-dir \
        jupyter-ai \
        jupyter-server-proxy \
        langchain-anthropic \
        langchain-openai \
    && jupyter server extension list 2>&1 | grep -q jupyter_ai || \
       jupyter server extension enable jupyter_ai --sys-prefix

# Install pegasus-ai package from local source
COPY pegasus-ai/ /tmp/pegasus-ai/
RUN pip install --no-cache-dir /tmp/pegasus-ai/ \
    && rm -rf /tmp/pegasus-ai/

# ── Stage 5: Config, scripts, marketplace ─────────────────────
# Copy the plugin marketplace into the image
COPY claude-plugin-marketplace/ /opt/pegasus-ai/claude-plugin-marketplace/

# Copy AI tools config (skills, agents, shared context)
COPY pegasus-ai-workbench/ai-tools/ /opt/pegasus-ai/ai-tools/

# Copy LLM setup notebook and helpers
COPY pegasus-ai-workbench/notebooks/ /opt/pegasus-ai/notebooks/

# Copy Jupyter AI config
COPY pegasus-ai-workbench/config/jupyter_ai_config.py /etc/jupyter/jupyter_ai_config.py

# Install OpenCode web extension (API handlers + panel UI + proxy)
COPY pegasus-ai-workbench/config/opencode-extension/ /tmp/opencode-extension/
RUN pip install --no-cache-dir /tmp/opencode-extension/ \
    && jupyter server extension enable opencode_extension --sys-prefix \
    && rm -rf /tmp/opencode-extension/

# Install PegasusAI chat extension (SSE streaming chat + tool calling)
COPY pegasus-ai-workbench/config/pegasus-ai-extension/ /tmp/pegasus-ai-extension/
RUN pip install --no-cache-dir /tmp/pegasus-ai-extension/ \
    && jupyter server extension enable pegasus_ai_extension --sys-prefix \
    && rm -rf /tmp/pegasus-ai-extension/

# Install Claude Code launcher extension (launcher card + status panel)
COPY pegasus-ai-workbench/config/claude-code-extension/ /tmp/claude-code-extension/
RUN pip install --no-cache-dir /tmp/claude-code-extension/ \
    && jupyter server extension enable claude_code_extension --sys-prefix \
    && rm -rf /tmp/claude-code-extension/

# Copy and install scripts
COPY pegasus-ai-workbench/scripts/entrypoint.sh /usr/local/bin/entrypoint.sh
COPY pegasus-ai-workbench/scripts/pegasus-ai-setup.sh /usr/local/bin/pegasus-ai-setup
COPY pegasus-ai-workbench/scripts/configure-llm.sh /etc/profile.d/pegasus-ai-llm.sh
COPY pegasus-ai-workbench/scripts/register-plugins.sh /usr/local/bin/register-plugins
COPY pegasus-ai-workbench/scripts/model_proxy.py /usr/local/bin/model_proxy.py

RUN chmod +x \
        /usr/local/bin/entrypoint.sh \
        /usr/local/bin/pegasus-ai-setup \
        /etc/profile.d/pegasus-ai-llm.sh \
        /usr/local/bin/register-plugins \
        /usr/local/bin/model_proxy.py

# ── ACCESS variant extras ─────────────────────────────────────
ARG VARIANT
RUN if [ "${VARIANT}" = "access" ]; then \
        echo "[pegasus-ai] ACCESS variant: HTCondor Annex pre-configured"; \
    fi

# ── Switch to notebook user ──────────────────────────────────
USER ${NB_UID}
WORKDIR /home/${NB_USER}

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["--ServerApp.token=''"]
