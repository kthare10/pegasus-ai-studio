# PegasusAI Studio

AI-powered scientific workflow development platform for [Pegasus WMS](https://pegasus.isi.edu/). Provides a web-based IDE with an AI tool marketplace, real-time workflow monitoring, SSE streaming chat with tool use, and WebSocket terminals — all in a single Docker container.

## Overview

PegasusAI Studio replaces the pegasus-ai-workbench with a full-featured web application. It bundles Pegasus WMS, HTCondor, JupyterLab, and multiple AI coding assistants into one environment.

```
┌─────────────────────────────────────────────────────┐
│  Browser (port 8888)                                │
│  ┌────────────┬────────────┬─────────┬───────────┐  │
│  │ Dashboard  │ Workbench  │  Chat   │ Settings  │  │
│  │ (workflows)│ (AI tools) │  (SSE)  │  (LLM)    │  │
│  └────────────┴────────────┴─────────┴───────────┘  │
└──────────────────────┬──────────────────────────────┘
                       │ Nginx reverse proxy (port 80)
        ┌──────────────┼──────────────┐
        │              │              │
   Next.js :3000  FastAPI :8080  JupyterLab :8889
   (frontend)     (studio-api)   (on-demand)
        │              │
        │         ┌────┴────┐
        │         │ SQLite  │
        │         │ Pegasus │
        │         │ HTCondor│
        │         └─────────┘
```

## Quick Start

> [!IMPORTANT]
> **Run on a native `amd64` (x86-64) host.** The image is built for
> `linux/amd64`. On Apple Silicon (M-series) it runs only under Rosetta/QEMU
> emulation, where building, the web UI, `pegasus-plan`, and *opening* notebooks
> work — but **live Jupyter kernels fail to connect** (the `kernel_info`
> handshake times out with a "Nudge" loop). This is an emulation artifact, not a
> config bug; the same image runs kernels fine on native amd64. Use a native
> amd64 Linux host (cloud VM, lab server, Chameleon/FABRIC) for full
> functionality. On Apple Silicon, the build additionally requires Rosetta in
> Colima (`colima start --vz-rosetta`).

### 1. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and set your LLM provider and API key:

```bash
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
```

Supported providers: `anthropic`, `openai`, `fabric`, `nrp`, `ollama`, `custom`.

### 2. Build and run with Docker

```bash
make build    # Build the Docker image
make run      # Run on port 8888
```

Open `http://localhost:8888` in your browser.

### 3. Stop

```bash
make stop
```

## Pages

| Route | Description |
|-------|-------------|
| `/dashboard` | Workflow list with real-time status, job tables, and pegasus-analyzer output |
| `/workbench` | AI tool marketplace (Claude Code, OpenCode, Codex CLI, etc.) with terminal tabs |
| `/chat` | SSE streaming chat with tool use (file ops, Pegasus commands, shell execution) |
| `/settings` | LLM provider configuration with API key validation and model selection |

## Development

### Prerequisites

- Python 3.11+
- Node.js 20+
- (Optional) Pegasus WMS 5.1+ and HTCondor — health checks degrade gracefully without them

### Backend (studio-api)

```bash
make install-api    # Create venv + install deps
make dev-api        # Start API server on port 8080
make test-api       # Run pytest
```

Or manually:

```bash
cd studio-api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install pytest httpx
python init_db.py               # Initialize SQLite schema
uvicorn main:app --reload --port 8080
```

API docs available at `http://localhost:8080/docs` (Swagger UI).

### Frontend (studio-web)

```bash
make install-web    # npm install
make dev-web        # Start Next.js dev server on port 3000
```

Or manually:

```bash
cd studio-web
npm install
npm run dev
```

Open `http://localhost:3000`. API calls are proxied to `http://localhost:8080` via Next.js rewrites.

### Running both in development

Run in two terminals:

```bash
# Terminal 1
make dev-api

# Terminal 2
make dev-web
```

## Architecture

### Backend (`studio-api/`)

FastAPI application with async SQLite, structured JSON logging (structlog), and WebSocket PTY terminals.

- **Routers**: health, settings, llm, knowledge, tools, workflows, chat, files, jupyter, terminal, ai_terminal
- **LLM layer**: Multi-provider support with async model discovery and config propagation to installed tools
- **Knowledge layer**: Adapter pattern translates shared Pegasus domain knowledge (skills, agents, templates) into each AI tool's native format
- **Services**: Tool installer, process manager, workflow scanner/monitor/submitter

See [`studio-api/README.md`](studio-api/README.md) for the full API reference.

### Frontend (`studio-web/`)

Next.js 15 (App Router) with React 19, TailwindCSS, Zustand stores, and TanStack Query.

- **Terminals**: xterm.js with WebSocket connections to backend PTY sessions
- **Chat**: SSE streaming with tool call/result display
- **Workflows**: Real-time status updates via Server-Sent Events

See [`studio-web/README.md`](studio-web/README.md) for frontend details.

### Docker container

Single container running three services via [s6-overlay](https://github.com/just-containers/s6-overlay):

| Service | Port | Description |
|---------|------|-------------|
| `studio-api` | 8080 | FastAPI backend (uvicorn) |
| `studio-web` | 3000 | Next.js standalone server |
| `nginx` | 80 | Reverse proxy (exposed as 8888 on host) |
| JupyterLab | 8889 | On-demand via `/api/jupyter/start` |

Base image: `quay.io/jupyter/scipy-notebook:python-3.11` with Pegasus WMS 5.1.2, HTCondor, and Node.js 20.

### Nginx routing

| Path | Backend |
|------|---------|
| `/` | Next.js frontend |
| `/api/*` | FastAPI (with SSE buffering disabled) |
| `/ws/*` | FastAPI WebSocket (PTY terminals) |
| `/jupyter/*` | JupyterLab (when running) |

## AI Tool Marketplace

The workbench page provides one-click install and launch for AI coding assistants:

| Tool | Type | Description |
|------|------|-------------|
| Claude Code | Terminal | Anthropic's CLI agent with Pegasus MCP plugins |
| OpenCode | Terminal | Open-source AI coding assistant |
| Codex CLI | Terminal | OpenAI's CLI agent |
| Antigravity | Terminal | Lightweight AI terminal assistant |
| PegasusAI Chat | Web | Built-in SSE streaming chat (no install needed) |

Each tool receives the shared Pegasus knowledge base (skills, agent personas, workflow templates) translated into its native format via knowledge adapters.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | `anthropic` | LLM provider (`anthropic`, `openai`, `fabric`, `nrp`, `custom`, `ollama`) |
| `LLM_MODEL` | (provider default) | Override the default model |
| `ANTHROPIC_API_KEY` | — | API key for Anthropic provider |
| `OPENAI_API_KEY` | — | API key for OpenAI provider |
| `FABRIC_AI_API_KEY` | — | API key for FABRIC AI gateway |
| `NRP_API_KEY` | — | API key for NRP Nautilus eLLM |
| `CUSTOM_BASE_URL` | — | Base URL for custom OpenAI-compatible endpoint |
| `CUSTOM_API_KEY` | — | API key for custom endpoint |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama server URL |

## Makefile Targets

| Target | Description |
|--------|-------------|
| `make build` | Build Docker image (`kthare10/pegasus-ai-studio:latest`) |
| `make run` | Run container on port 8888 with `.env` and `./work` volume |
| `make stop` | Stop running container |
| `make push` | Push image to Docker Hub |
| `make clean` | Remove Docker image |
| `make dev-api` | Run backend dev server (port 8080) |
| `make dev-web` | Run frontend dev server (port 3000) |
| `make install-api` | Create Python venv + install deps |
| `make install-web` | Install Node.js deps |
| `make test-api` | Run backend tests |
| `make test-web` | Run frontend tests |

## Workspace

The container mounts `./work` to `/home/jovyan/work`. This is where:

- Workflow files are stored and submitted from
- The SQLite database lives (`.studio/studio.db`)
- AI tools operate (Claude Code, OpenCode, etc.)
- JupyterLab opens as its working directory

Data persists across container restarts via the volume mount.

## License

Apache 2.0
