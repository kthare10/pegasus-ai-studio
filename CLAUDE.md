# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

**Pegasus AI Workbench** is a containerized development environment for building scientific workflows with Pegasus WMS. It bundles JupyterLab, Pegasus WMS 5.1, HTCondor, and AI coding agents (Claude Code, OpenCode, Jupyter AI) into a single Docker image. All AI tools are pre-configured with Pegasus-specific skills, agents, and reference material.

The image is built from `quay.io/jupyter/scipy-notebook:python-3.11` and published to Docker Hub under the `kthare10` registry.

## Build Commands

**Important**: The Makefile expects to run from the parent `tool/` directory as build context (so the Dockerfile can access sibling directories `pegasus-ai/` and `claude-plugin-marketplace/`).

```sh
make build          # Full image (latest) — Claude Code + OpenCode + Jupyter AI
make build-lite     # Lite image — JupyterLab + Jupyter AI only, no CLI agents
make build-access   # ACCESS variant — Full + HTCondor Annex pre-configured
make run            # Run full image on port 8888 with .env and ./work mount
make run-lite       # Run lite image
make test           # Smoke test: verify all tools installed in the image
make push           # Tag and push latest + lite to kthare10/ on Docker Hub
make clean          # Remove local images

docker compose up        # Build + run via Compose
docker compose up -d     # Detached
docker compose down      # Stop
```

## Architecture

### Configuration Flow

LLM provider settings flow from a single source to all AI tools:

1. **Input**: `.env` file, Docker env vars, or `pegasus-ai-setup` interactive wizard
2. **Propagation**: `scripts/configure-llm.sh` (sourced via `/etc/profile.d/` on every login) reads `LLM_PROVIDER` + `LLM_MODEL` + API keys and rewrites tool-specific configs:
   - `work/opencode.json` — OpenCode provider/model config (dynamically discovers available models)
   - `PEGASUS_AI_LLM_*` env vars — pegasus-ai native assistant
   - Claude Code reads `ANTHROPIC_API_KEY` directly from env

Supported providers: `anthropic`, `openai`, `fabric` (FABRIC AI gateway), `nrp` (Nautilus eLLM), `custom` (any OpenAI-compatible endpoint), `ollama` (local).

### Container Startup (`scripts/entrypoint.sh`)

On first launch (tracked by `~/.pegasus-ai/.initialized` marker):
1. Seeds AI tool configs from `/opt/pegasus-ai/ai-tools/` into `~/work/`
2. Copies shared context `PEGASUS_AI.md` as `~/work/AGENTS.md`
3. Runs `register-plugins` to set up the Claude Code `scitech` plugin marketplace
4. Copies `LLM_Setup.ipynb` to home directory

On every startup: copies `ai-tools/opencode/` contents into `~/work/.opencode/` (agents, skills, commands), sources `configure-llm.sh` to propagate LLM settings, then delegates to Jupyter's `start-notebook.py`.

### AI Tool Config Sources (`ai-tools/`)

```
ai-tools/
├── shared/PEGASUS_AI.md      → ~/work/AGENTS.md (master Pegasus context for all tools)
├── opencode/
│   ├── agents/*.md            → ~/work/.opencode/agents/
│   ├── skills/*.md            → ~/work/.opencode/skills/<name>/SKILL.md
│   └── commands/*.md          → ~/work/.opencode/commands/
└── claude-code/CLAUDE.md      → ~/work/CLAUDE.md (in-container Claude Code instructions)
```

### Plugin Registration (`scripts/register-plugins.sh`)

First-launch idempotent script (marker: `~/.pegasus-ai/.plugins-registered`). Copies the `claude-plugin-marketplace/` from `/opt/pegasus-ai/` into the user home, then runs `claude plugin marketplace add` and installs the `pegasus-ai` and `pegasus-dev` plugins from the `scitech` marketplace. Requires `ANTHROPIC_API_KEY`.

### OpenCode Web Extension (`config/opencode-extension/`)

A JupyterLab server extension that manages the OpenCode web subprocess lifecycle. Provides API endpoints (`/api/opencode-web/start|stop|status|models`) and serves a self-contained HTML panel with sidebar controls + embedded iframe. Handles multi-provider config generation, model discovery, and model proxy management.

## Key Files

| File | Purpose |
|------|---------|
| `Dockerfile` | Full image build (multi-stage: base → Pegasus/HTCondor → AI agents → configs) |
| `Dockerfile.lite` | Lite variant (no CLI AI agents) |
| `scripts/configure-llm.sh` | Central LLM config propagation logic |
| `scripts/entrypoint.sh` | Container entrypoint (first-launch seeding + Jupyter delegation) |
| `scripts/pegasus-ai-setup.sh` | Interactive provider/key/model setup wizard |
| `config/jupyter_ai_config.py` | Jupyter AI server defaults |
| `work/` | Bind-mounted persistent user work directory (seeded with tool configs) |
| `notebooks/LLM_Setup.ipynb` | Notebook-based LLM configuration UI |

## Environment Variables

Required: `LLM_PROVIDER` + provider-specific API key (e.g., `ANTHROPIC_API_KEY`). Optional: `LLM_MODEL` (overrides provider default). See `.env.example` for all options. API keys are never baked into the image.
