# PegasusAI Studio

AI-powered scientific workflow development platform for [Pegasus WMS](https://pegasus.isi.edu/). A web-based IDE that bundles Pegasus WMS, HTCondor, Apptainer, JupyterLab, an AI tool marketplace, real-time workflow monitoring, and SSE streaming chat into a single Docker container — with an optional CILogon authentication front end.

## Overview

PegasusAI Studio packages everything needed to author, plan, submit, and monitor Pegasus workflows into one image. It runs a personal HTCondor pool, the Pegasus planner, and Apptainer for containerized jobs, fronted by a Next.js web UI and a FastAPI backend.

```
                              Browser
                                 │
   ┌─────────────────────────────┴──────────────────────────────┐
   │  Plain mode (docker-compose.yml / make run): browser → :8888│
   │  Auth mode  (docker-compose.auth.yml): browser → :8443 TLS  │
   │     nginx proxy ── auth_request ──▶ vouch-proxy ──▶ CILogon  │
   └─────────────────────────────┬──────────────────────────────┘
                                 │
                 in-container nginx  (:80, exposed :8888)
       ┌───────────────┬──────────────────┬────────────────────┐
   Next.js :3000   FastAPI :8080     JupyterLab :8889    (path routing)
   (studio-web)    (studio-api)      (always-on)
                        │
              ┌─────────┴──────────────────────────────┐
              │ SQLite (.studio/studio.db)              │
              │ HTCondor personal pool · Pegasus 5.1.2  │
              │ Apptainer (Singularity) · workflow-monitor
              └─────────────────────────────────────────┘
```

All services run under [s6-overlay](https://github.com/just-containers/s6-overlay) in one container. Built for **`linux/amd64`**.

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

Supported providers: `anthropic`, `openai`, `fabric`, `nrp`, `ollama`, `custom`. Custom/FABRIC/NRP endpoints may be plain Chat-Completions **or** OpenAI Responses API — the studio chat auto-detects and adapts.

### 2. Build and run

Plain (unauthenticated) — Makefile or Compose:

```bash
make build && make run          # → http://localhost:8888
# or
docker compose up -d            # → http://localhost:8888
```

With CILogon authentication (sidecar: nginx + vouch-proxy in front):

```bash
# one-time: register a CILogon client, fill auth/vouch/config.yaml, gen certs
docker compose -f docker-compose.auth.yml up -d   # → https://localhost:8443
```

See [`auth/README.md`](auth/README.md) for the CILogon setup.

### 3. Stop

```bash
make stop                                  # plain (Makefile)
docker compose down                        # plain (Compose)
docker compose -f docker-compose.auth.yml down   # auth stack
```

## Pages

The web UI (left nav):

| Nav item | Description |
|----------|-------------|
| **Workflows** | Project list + runs with real-time status/jobs (from workflow-monitor JSONL), `pegasus-analyzer` output, and **Generate / Plan / Submit** with auto-discovered parameters |
| **Workbench** | AI tool marketplace (Claude Code, OpenCode, Codex CLI, …) with terminal tabs |
| **Notebooks** | Opens the always-on **JupyterLab** in a new browser tab |
| **Settings** | LLM provider configuration, API key validation, model selection |
| **PegasusAI Chat** | Slide-in SSE streaming chat with tool use (file ops, Pegasus commands, shell) |
| **Terminal** | Slide-in WebSocket PTY terminal |

### Workflow actions

Generate / Plan / Submit introspect each project's `workflow_generator.py` `argparse` at runtime, so the UI renders the right parameter form **per workflow** (no hardcoding):

- **Generate** → runs `workflow_generator.py` with the form's args
- **Plan** → `pegasus-plan -s <site> -o <output-site>`
- **Submit** → `pegasus-plan --submit`, then auto-starts `workflow-monitor --serve` so the run continuously emits `workflow-events.jsonl`, which drives the run/job views.

Jobs run in **Apptainer/Singularity** containers (e.g. `docker://python:3.11-slim`) on the personal HTCondor pool.

## Run modes & Compose files

| File | What runs | URL |
|------|-----------|-----|
| `docker-compose.yml` | Studio only (no auth) — `make run` equivalent | `http://localhost:8888` |
| `docker-compose.auth.yml` | Studio + **nginx auth proxy** + **vouch-proxy** (CILogon OIDC). Studio is not published; only the proxy is. | `https://localhost:8443` |

The auth stack maps cleanly to GKE later (ingress-nginx external-auth + a vouch Deployment) — see [`auth/README.md`](auth/README.md).

## Development

### Prerequisites
- Python 3.11+ · Node.js 20+
- (Optional) Pegasus WMS 5.1+ and HTCondor — health checks degrade gracefully without them

### Backend (studio-api)
```bash
make install-api    # venv + deps
make dev-api        # API on :8080  (docs at /docs)
make test-api       # pytest
```

### Frontend (studio-web)
```bash
make install-web    # npm install
make dev-web        # Next.js dev server on :3000 (proxies /api to :8080)
```

Run both in two terminals (`make dev-api`, `make dev-web`).

## Architecture

### Backend (`studio-api/`)
FastAPI + async SQLite, structlog JSON logging, WebSocket PTY terminals.

- **Routers**: health, settings, llm, knowledge, tools, workflows, chat, files, jupyter, terminal, ai_terminal
- **LLM layer**: multi-provider; async model discovery; config propagation to installed tools; chat supports Chat-Completions **and** the OpenAI Responses API (auto-fallback)
- **Knowledge layer**: adapters translate shared Pegasus domain knowledge (skills, agents, templates) into each AI tool's native format
- **Workflow services**: `workflow_scanner` (discovery + status from JSONL), `workflow_monitor` (jobs/stats from JSONL), `workflow_submitter` (plan/submit + monitor launch), `generator_introspect` (parameter discovery)

### Frontend (`studio-web/`)
Next.js 15 (App Router), React 19, TailwindCSS, Zustand, TanStack Query. xterm.js terminals over WebSocket; SSE chat; live workflow status.

### Docker container
Single image, services supervised by **s6-overlay**:

| Service | Port | Description |
|---------|------|-------------|
| `nginx` | 80 | In-container reverse proxy (host `:8888` in plain mode) |
| `studio-api` | 8080 | FastAPI backend (uvicorn) |
| `studio-web` | 3000 | Next.js standalone server |
| `jupyter` | 8889 | **JupyterLab — always-on** (started with the container) |
| `condor` | — | HTCondor personal pool (master/schedd/startd/collector/negotiator) |

**Base image:** `ubuntu:24.04` with a single system **Python 3.12** (no conda), **Pegasus WMS 5.1.2** + **HTCondor** (DEB), **Apptainer 1.5**, **Node.js 20**, and JupyterLab. `pegasus-plan` is pinned to the system Python via `PEGASUS_PYTHON`.

> JupyterLab runs **classic (non-RTC) document mode**: `jupyter-collaboration` and `jupyter-ai` are intentionally not installed — their collaboration/awareness extensions 403-loop behind the proxy and break notebook loading. The studio's own PegasusAI Chat provides LLM access.

### Nginx routing

| Path | Backend |
|------|---------|
| `/` | Next.js frontend |
| `/api/*` | FastAPI (SSE buffering off) |
| `/ws/*` | FastAPI WebSocket (PTY terminals) |
| `/jupyter/*` | JupyterLab (WebSocket upgrade enabled for kernels/terminals) |

## AI Tool Marketplace

One-click install/launch on the Workbench page:

| Tool | Type | Description |
|------|------|-------------|
| Claude Code | Terminal | Anthropic's CLI agent with Pegasus MCP plugins |
| OpenCode | Terminal | Open-source AI coding assistant |
| Codex CLI | Terminal | OpenAI's CLI agent (Responses API) |
| Antigravity | Terminal | Lightweight AI terminal assistant |
| PegasusAI Chat | Web | Built-in SSE streaming chat (no install) |

Each tool receives the shared Pegasus knowledge base (skills, agent personas, templates) translated into its native format via knowledge adapters.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | `anthropic` | `anthropic`, `openai`, `fabric`, `nrp`, `custom`, `ollama` |
| `LLM_MODEL` | (provider default) | Override the default model |
| `ANTHROPIC_API_KEY` | — | Anthropic key |
| `OPENAI_API_KEY` | — | OpenAI key |
| `FABRIC_AI_API_KEY` | — | FABRIC AI gateway key |
| `NRP_API_KEY` | — | NRP Nautilus eLLM key |
| `CUSTOM_BASE_URL` / `CUSTOM_API_KEY` | — | Custom OpenAI-compatible endpoint |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama server URL |

LLM config can also be set/updated at runtime via the Settings page (persisted in the SQLite DB). Nothing is seeded automatically.

## Makefile Targets

| Target | Description |
|--------|-------------|
| `make build` | Build the image (`kthare10/pegasus-ai-studio:latest`, `linux/amd64`) |
| `make run` / `make stop` | Run / stop the plain container on `:8888` |
| `make push` / `make clean` | Push to Docker Hub / remove the image |
| `make dev-api` / `make dev-web` | Dev servers (`:8080` / `:3000`) |
| `make install-api` / `make install-web` | Install backend / frontend deps |
| `make test-api` / `make test-web` | Run tests |

## Workspace

The container mounts `./work` → `/home/pegasus/work`, which holds:

- Workflow projects (generated, planned, submitted from here)
- The SQLite database (`.studio/studio.db`)
- AI tool working files
- JupyterLab's working directory

Data persists across restarts via the volume mount. `work/` is git-ignored and never pushed.

## Security & secrets

Git-ignored, never committed: `.env`, `auth/vouch/config.yaml` (CILogon client secret), `auth/ssl/*.pem` (TLS keys), `work/`, and local Claude settings. Templates (`.env.example`, `auth/vouch/config.yaml.example`) and the cert-gen script are tracked.

## License

[Apache License 2.0](LICENSE).
