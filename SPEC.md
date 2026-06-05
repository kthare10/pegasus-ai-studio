# PegasusAI Studio — Design Specification

> AI-powered scientific workflow development platform for Pegasus WMS,
> replacing the JupyterHub-only ACCESS Pegasus portal experience.

## 1. Problem Statement

The current ACCESS Pegasus portal (`pegasus.access-ci.org`) provides users with
a JupyterHub-spawned container (pegasus-ai-workbench) that bundles JupyterLab,
Pegasus WMS, HTCondor, and several AI coding tools. While functional, it has
limitations:

- **JupyterLab-centric**: The entire experience is inside JupyterLab — AI tools
  are accessed through launcher cards, terminal sessions, or extension panels.
  There is no unified workflow dashboard or tool marketplace.
- **Fixed tool set**: AI tools (Claude Code, OpenCode, Jupyter AI) are
  pre-installed in the image. Users cannot choose, add, or remove tools.
- **No workflow visibility**: Users must use `pegasus-status` in the terminal to
  monitor workflows. There is no dashboard showing running/completed/failed
  workflows with real-time updates.
- **Siloed knowledge**: Each AI tool has its own copy of skills, agents, and
  context documents. Adding a new tool requires manually wiring up its
  configuration.

## 2. Vision

**PegasusAI Studio** replaces the JupyterLab-only experience with a purpose-built
web application that combines:

1. **AI Tool Marketplace** — Users dynamically install/enable AI coding tools
   (Claude Code, Codex CLI, OpenCode, Antigravity, and future tools)
2. **Workflow Dashboard** — Real-time monitoring of running/completed/failed
   workflows with job-level detail and diagnostics
3. **Shared Knowledge Layer** — All AI tools share the same Pegasus domain
   knowledge (skills, RAG, agents, templates) regardless of vendor
4. **JupyterLab Integration** — Launch JupyterLab on demand for notebook-based
   work, with jupyter-ai pre-configured using the same LLM provider

## 3. Approach

### Reference Architecture: LoomAI

PegasusAI Studio follows the same single-container architecture proven in
[LoomAI](https://github.com/fabric-testbed/loomai) (`~/claude-cf/loomai-dev`):

- **FastAPI backend** serving REST API + WebSocket terminals + SSE streams
- **Next.js frontend** providing the dashboard, AI tools, and settings UI
- **Nginx reverse proxy** routing `/` → frontend, `/api/` → backend, `/jupyter/` → JupyterLab
- **JupyterLab launched on demand** via `POST /api/jupyter/start`, embedded as iframe
- **AI tools managed via WebSocket PTY** (terminal tools) or subprocess + iframe (web tools)
- **JSON file + SQLite** for settings and state persistence

### V1: Container Swap (this spec)

Replace the `pegasus-ai-workbench` Docker image with a `pegasus-ai-studio` image.
The existing JupyterHub/OOD infrastructure on ACCESS stays unchanged — we swap in
a better single-user container.

**What stays the same:**
- JupyterHub spawns a per-user container (DockerSpawner / KubeSpawner)
- Open OnDemand can launch it as an Interactive App
- `~/work/` is the persistent user workspace (bind-mounted volume)
- Pegasus WMS + HTCondor are pre-installed
- LLM configuration propagation via `configure-llm.sh` (legacy compat)

**What changes:**
- The container runs a Studio web app (Next.js + FastAPI) instead of just JupyterLab
- Users get a dashboard, AI tool marketplace, and workbench
- AI tools are installed on-demand rather than pre-baked
- JupyterLab is launched on demand (not always running)
- A shared knowledge layer adapts skills/agents for each tool automatically

### V2: Multi-User Platform (future)

Full standalone platform with PostgreSQL, Redis, CILogon auth, and Kubernetes
deployment. V2 is out of scope for this spec but the V1 architecture is designed
to evolve into it.

---

## 4. V1 Architecture

### 4.1 Container Layout

```
pegasus-ai-studio container
├─────────────────────────────────────────────────────────────┐
│                                                             │
│  Nginx (reverse proxy, :8888)                               │
│  ├── /              → studio-web  (Next.js, :3000)          │
│  ├── /api/          → studio-api  (FastAPI, :8080)          │
│  ├── /ws/           → WebSocket upgrade (terminals, events) │
│  └── /jupyter/      → JupyterLab  (:8889, when running)    │
│                                                             │
│  studio-api (FastAPI, :8080)                                │
│  ├── AI tool registry + process management                  │
│  ├── WebSocket PTY terminals (bash + AI tools)              │
│  ├── Workspace file operations                              │
│  ├── Knowledge layer (skills/agents/templates)              │
│  ├── LLM provider configuration + propagation               │
│  ├── Workflow monitoring (stampede DB + events)              │
│  ├── JupyterLab lifecycle (start/stop/status)               │
│  └── Built-in PegasusAI chat (SSE streaming + tool use)     │
│                                                             │
│  studio-web (Next.js, :3000)                                │
│  ├── Dashboard (workflow overview + stats)                   │
│  ├── AI Workbench (editor + terminal + AI tool panel)       │
│  ├── Tool Marketplace (install/manage AI tools)             │
│  ├── Workflow detail (monitoring, jobs, diagnostics)         │
│  ├── Notebooks (JupyterLab iframe, launched on demand)      │
│  └── Settings (LLM provider, preferences)                   │
│                                                             │
│  JupyterLab (:8889, launched on demand)                     │
│  ├── jupyter-ai extension (Jupyternaut chat)                │
│  └── Standard notebook/file/terminal interface              │
│                                                             │
│  Pre-installed system software                              │
│  ├── Pegasus WMS 5.1 + HTCondor 25.x                       │
│  ├── Node.js 20.x (for AI tool installation)                │
│  └── Python 3.11 + pip + uv                                 │
│                                                             │
│  Persistent workspace: ~/work/ (bind-mounted)               │
│  ├── User workflow projects                                 │
│  ├── .studio/          (studio state: SQLite, tool configs) │
│  ├── .claude/          (Claude Code config, if installed)   │
│  ├── .opencode/        (OpenCode config, if installed)      │
│  └── .pegasus-ai/      (LLM config, .env)                  │
│                                                             │
│  Knowledge store: /opt/pegasus-ai/knowledge/ (read-only)    │
│  ├── skills/           (canonical skill definitions)        │
│  ├── agents/           (agent persona prompts)              │
│  ├── templates/        (workflow file templates)            │
│  ├── examples/         (curated workflow generators)        │
│  ├── references/       (PEGASUS.md, PEGASUS_AI.md)          │
│  └── mcp/              (MCP server configurations)          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 Service Responsibilities

#### studio-web (Next.js, :3000)

Server-side rendered React application. All user-facing pages. Proxies API
calls to studio-api. Handles WebSocket connections for real-time updates.

**Tech**: Next.js 15 (App Router), React 19, TypeScript, TailwindCSS, shadcn/ui,
xterm.js (terminal emulator), Monaco Editor (code editing), TanStack Query
(server state management), Zustand (client state management).

**State management**: Unlike LoomAI (which uses a single 239KB `App.tsx` with
raw `useState` for everything), Studio uses domain-specific Zustand stores and
TanStack Query for server state:

- **Zustand stores** (`lib/stores/`): `useToolStore` (installed tools, active
  tool), `useWorkspaceStore` (open files, active file, terminal tabs),
  `useLayoutStore` (panel sizes, sidebar collapsed)
- **TanStack Query** (`lib/queries/`): All API data — workflows, tool status,
  knowledge, LLM config. Provides automatic caching, background refetch,
  optimistic updates, and request deduplication without hand-rolling any of it.
  SSE events invalidate relevant query keys for real-time updates.

#### studio-api (FastAPI, :8080)

Lightweight API backend running inside the container. Manages AI tools, serves
knowledge, monitors workflows, launches JupyterLab, and handles terminal
sessions. Follows the same patterns as LoomAI's backend.

**Tech**: Python 3.11, FastAPI, Uvicorn, SQLite (aiosqlite), httpx, websockets,
aiofiles, structlog (structured logging).

**Key design**: This is a single-user environment — the container runs as one
user, so no multi-tenancy. Auth is handled by JupyterHub/OOD before the
container is spawned.

**Code organization**: Each router module stays under ~500 lines. Business logic
lives in service/manager classes under `services/`, not in route handlers.
Unlike LoomAI's 3,000+ line route files (`ai_chat.py`, `slices.py`), Studio
separates concerns:

```
routers/tools.py      → thin HTTP handlers (validation, response formatting)
services/installer.py → actual npm install logic, disk checks, adapter calls
services/process_mgr.py → subprocess lifecycle, PTY management, health checks
```

**Structured logging**: All backend logging uses `structlog` with JSON output.
Every log line includes `event`, `tool_id`, `duration_ms`, and request context.
This makes debugging container issues tractable — `docker logs` output is
parseable by any log aggregator.

```python
# studio_api/logging_config.py
import structlog

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
)

# Usage in route handlers:
log = structlog.get_logger()
log.info("tool_installed", tool_id="claude-code", duration_ms=4200)
log.warning("jupyter_start_failed", error=str(e), port=8889)
```

#### JupyterLab (on-demand, :8889)

Standard JupyterLab with jupyter-ai extension. **Not always running** — launched
via `POST /api/jupyter/start` when the user navigates to the Notebooks view.
Shares the same `~/work/` workspace so files are visible in both Studio and
JupyterLab.

This follows the LoomAI pattern where JupyterLab is a managed subprocess:

```python
# studio_api/routers/jupyter.py (mirrors loomai-dev/backend/app/routes/jupyter.py)

_jupyter_proc = None
_JUPYTER_PORT = 8889

@router.post("/api/jupyter/start")
async def start_jupyter():
    """Launch JupyterLab subprocess if not already running."""
    global _jupyter_proc
    if _jupyter_proc and _jupyter_proc.poll() is None:
        return {"status": "running", "port": _JUPYTER_PORT}

    # Configure jupyter-ai with current LLM provider
    _configure_jupyter_ai()

    _jupyter_proc = subprocess.Popen([
        "jupyter", "lab",
        "--no-browser",
        "--ip=0.0.0.0",
        f"--port={_JUPYTER_PORT}",
        "--ServerApp.base_url=/jupyter/",
        "--ServerApp.token=",
    ], cwd=WORKSPACE_ROOT)

    return {"status": "starting", "port": _JUPYTER_PORT}

@router.post("/api/jupyter/stop")
async def stop_jupyter():
    """Stop JupyterLab subprocess."""
    global _jupyter_proc
    if _jupyter_proc and _jupyter_proc.poll() is None:
        _jupyter_proc.terminate()
        _jupyter_proc.wait(timeout=10)
    _jupyter_proc = None
    return {"status": "stopped"}

@router.get("/api/jupyter/status")
async def jupyter_status():
    """Check if JupyterLab is running."""
    running = _jupyter_proc is not None and _jupyter_proc.poll() is None
    return {"status": "running" if running else "stopped", "port": _JUPYTER_PORT}
```

### 4.3 Nginx Reverse Proxy

Single entry point on port 8888 (what JupyterHub/OOD expects):

```nginx
upstream studio_web { server 127.0.0.1:3000; }
upstream studio_api { server 127.0.0.1:8080; }
upstream jupyter    { server 127.0.0.1:8889; }

server {
    listen 8888;

    # Studio web app (default)
    location / {
        proxy_pass http://studio_web;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    # API gateway
    location /api/ {
        proxy_pass http://studio_api/api/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 3600s;  # Long-lived SSE/WebSocket
    }

    # WebSocket terminal sessions
    location /ws/ {
        proxy_pass http://studio_api/ws/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 3600s;
    }

    # JupyterLab (on demand — returns 502 if not started)
    location /jupyter/ {
        proxy_pass http://jupyter/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

---

## 5. AI Tool Marketplace

### 5.1 Tool Registry

The tool registry defines which AI coding tools are available for installation.
It ships as a static JSON file in the container image, updatable by rebuilding.

```json
{
  "tools": [
    {
      "id": "claude-code",
      "name": "Claude Code",
      "vendor": "Anthropic",
      "description": "AI coding assistant with plugin skills, MCP servers, and agentic tool use",
      "version_command": "claude --version",
      "install_method": "npm",
      "install_command": "npm install -g @anthropic-ai/claude-code",
      "binary": "claude",
      "type": "terminal",
      "supports_mcp": true,
      "supports_web": false,
      "required_env": ["ANTHROPIC_API_KEY"],
      "knowledge_adapter": "claude_code",
      "icon": "claude.svg",
      "homepage": "https://docs.anthropic.com/en/docs/claude-code"
    },
    {
      "id": "codex-cli",
      "name": "Codex CLI",
      "vendor": "OpenAI",
      "description": "OpenAI's coding agent for terminal-based development",
      "version_command": "codex --version",
      "install_method": "npm",
      "install_command": "npm install -g @openai/codex",
      "binary": "codex",
      "type": "terminal",
      "supports_mcp": false,
      "supports_web": false,
      "required_env": ["OPENAI_API_KEY"],
      "knowledge_adapter": "codex_cli",
      "icon": "codex.svg",
      "homepage": "https://github.com/openai/codex"
    },
    {
      "id": "opencode",
      "name": "OpenCode",
      "vendor": "opencode-ai",
      "description": "Open-source AI coding assistant with web UI, agents, and skills",
      "version_command": "opencode version",
      "install_method": "npm",
      "install_command": "npm install -g opencode-ai",
      "binary": "opencode",
      "type": "web",
      "web_command": "opencode web --port {port} --hostname 0.0.0.0",
      "supports_mcp": true,
      "supports_web": true,
      "required_env": [],
      "knowledge_adapter": "opencode",
      "icon": "opencode.svg",
      "homepage": "https://opencode.ai"
    },
    {
      "id": "antigravity",
      "name": "Antigravity",
      "vendor": "Antigravity",
      "description": "AI coding tool for terminal-based development",
      "version_command": "antigravity --version",
      "install_method": "npm",
      "install_command": "npm install -g @anthropic-ai/antigravity",
      "binary": "antigravity",
      "type": "terminal",
      "supports_mcp": false,
      "supports_web": false,
      "required_env": ["ANTHROPIC_API_KEY"],
      "knowledge_adapter": "antigravity",
      "icon": "antigravity.svg",
      "homepage": "https://github.com/anthropics/antigravity"
    },
    {
      "id": "pegasus-ai-chat",
      "name": "PegasusAI Chat",
      "vendor": "Built-in",
      "description": "Built-in Pegasus workflow assistant with streaming chat and tool use",
      "version_command": null,
      "install_method": "builtin",
      "install_command": null,
      "binary": null,
      "type": "web",
      "supports_mcp": true,
      "supports_web": true,
      "required_env": [],
      "knowledge_adapter": "web_chat",
      "icon": "pegasus-ai.svg",
      "homepage": null
    }
  ]
}
```

### 5.2 Tool Lifecycle

```
[Not Installed] --install--> [Installed] --start--> [Running] --stop--> [Installed]
                                  |                                         |
                                  +--uninstall--> [Not Installed] <---------+
```

**Install**: Runs `install_command`, then the knowledge adapter seeds the workspace
with tool-specific configuration (CLAUDE.md, .mcp.json, .opencode/, etc.).

**Start**: For `terminal` tools, creates a PTY session accessible via WebSocket
(same pattern as LoomAI's `ai_terminal.py`). For `web` tools, spawns the web
server subprocess and proxies its UI.

**Uninstall**: Removes tool-specific config from workspace. Does not remove the
npm global binary (shared across container restarts via cached node_modules).

### 5.3 Tool Process Management

Follows the LoomAI `ai_terminal.py` pattern for managing AI tool subprocesses:

```python
# studio_api/routers/ai_terminal.py (mirrors loomai-dev pattern)

import asyncio
import os
import pty
import struct
import fcntl
import termios

@router.websocket("/ws/terminal/{tool_id}")
async def ai_tool_terminal(websocket: WebSocket, tool_id: str):
    """WebSocket PTY for an AI coding tool."""
    await websocket.accept()

    tool = get_tool(tool_id)
    if not tool or tool.status != "installed":
        await websocket.close(code=4004, reason="Tool not installed")
        return

    # Create PTY
    master_fd, slave_fd = pty.openpty()

    # Set environment (LLM provider, API keys)
    env = _build_tool_env(tool_id)

    # Spawn tool process
    proc = subprocess.Popen(
        [tool.binary],
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        cwd=WORKSPACE_ROOT,
        env=env,
        preexec_fn=os.setsid,
    )
    os.close(slave_fd)

    try:
        # Bidirectional relay: WebSocket ↔ PTY
        await asyncio.gather(
            _ws_to_pty(websocket, master_fd),
            _pty_to_ws(master_fd, websocket),
        )
    finally:
        os.close(master_fd)
        proc.terminate()
```

### 5.4 Tool Installation Flow

```
User clicks "Install" on Claude Code
    │
    ▼
POST /api/tools/claude-code/install
    │
    ├── Check if binary exists (npm list -g)
    │   └── If not: npm install -g @anthropic-ai/claude-code
    │
    ├── Run knowledge adapter: ClaudeCodeAdapter.install()
    │   ├── Copy CLAUDE.md from /opt/pegasus-ai/knowledge/references/
    │   ├── Write .mcp.json from /opt/pegasus-ai/knowledge/mcp/
    │   ├── Copy plugin marketplace to ~/.claude/
    │   ├── Register pegasus-ai + pegasus-dev plugins
    │   └── Propagate current LLM config (API key → env)
    │
    ├── Update SQLite: tool_installations.status = 'installed'
    │
    └── Return { status: "installed" }
```

---

## 6. Shared Knowledge Layer

### 6.1 Design Principle

Each AI tool has different conventions for consuming domain knowledge:

| Tool | Skills format | Context file | MCP support | Agent personas |
|------|--------------|--------------|-------------|----------------|
| Claude Code | `skills/{name}/SKILL.md` in plugin dir | `CLAUDE.md` in workspace | Native (`.mcp.json`) | Via CLAUDE.md instructions |
| OpenCode | `.opencode/skills/{name}/SKILL.md` | `AGENTS.md` or `opencode.json` | Via `opencode.json` | `.opencode/agents/{name}.md` |
| Codex CLI | Instructions file (AGENTS.md) | `AGENTS.md` or `codex.md` | Not supported | Via instructions file |
| Antigravity | Instructions file | `.antigravity/context.md` | Not supported | Via context file |
| PegasusAI Chat | Server-side (FastAPI loads directly) | `PEGASUS_AI.md` loaded in memory | Server-side tool calls | Agent picker in chat UI |

The **Knowledge Adapter** pattern translates a single canonical skill/agent
definition into each tool's native format.

### 6.2 Canonical Knowledge Store

Ships read-only in the container image at `/opt/pegasus-ai/knowledge/`:

```
/opt/pegasus-ai/knowledge/
├── skills/
│   ├── scaffold/
│   │   ├── canonical.md         # Tool-agnostic skill prompt
│   │   └── metadata.json        # { name, description, slash_command: "/pegasus-scaffold" }
│   ├── wrapper/
│   ├── dockerfile/
│   ├── convert/
│   ├── review/
│   ├── debug/
│   ├── help/
│   └── kiso/
│
├── agents/
│   ├── workflow-architect.md
│   ├── data-engineer.md
│   └── pipeline-debugger.md
│
├── templates/                    # From claude-plugin-marketplace/assets/templates/
│   ├── workflow_generator_template.py
│   ├── wrapper_template.py
│   ├── wrapper_template.sh
│   ├── Dockerfile_template
│   ├── README_template.md
│   └── run_manual_template.sh
│
├── examples/                     # From claude-plugin-marketplace/assets/examples/
│   ├── workflow_generator_airquality.py
│   ├── workflow_generator_earthquake.py
│   ├── workflow_generator_gwas_qc.py
│   ├── workflow_generator_mag.py
│   ├── workflow_generator_medical_imaging_fl.py
│   ├── workflow_generator_obs_harvest.py
│   ├── workflow_generator_proteinfold.py
│   ├── workflow_generator_rnaseq.py
│   ├── workflow_generator_s2_segmentation.py
│   ├── workflow_generator_soilmoisture.py
│   ├── workflow_generator_sra_search.py
│   ├── workflow_generator_tnseq.py
│   └── fl_round.py
│
├── references/
│   ├── PEGASUS_AI.md             # Master context (from ai-tools/shared/)
│   └── PEGASUS.md                # Pegasus WMS reference
│
└── mcp/
    └── servers.json              # MCP server registry
```

### 6.3 Knowledge Adapter Interface

```python
# studio_api/knowledge/adapters.py

class KnowledgeAdapter(ABC):
    """Translates canonical knowledge into a tool's native format."""

    @abstractmethod
    def install(self, workspace: str, llm_config: dict) -> None:
        """Full install: context + skills + agents + MCP."""

    @abstractmethod
    def update_llm_config(self, workspace: str, llm_config: dict) -> None:
        """Update LLM provider/model/key for this tool."""

    @abstractmethod
    def uninstall(self, workspace: str) -> None:
        """Remove tool-specific config from workspace."""
```

**Adapter implementations:**

| Adapter | Context output | Skills output | MCP output |
|---------|---------------|---------------|------------|
| `ClaudeCodeAdapter` | `{ws}/CLAUDE.md` | `~/.claude/plugins/scitech/skills/` | `{ws}/.mcp.json` |
| `OpenCodeAdapter` | `{ws}/AGENTS.md` + `opencode.json` | `{ws}/.opencode/skills/` | `opencode.json` mcp key |
| `CodexCLIAdapter` | `{ws}/AGENTS.md` | Inlined in AGENTS.md | N/A (not supported) |
| `AntigravityAdapter` | `{ws}/.antigravity/context.md` | Inlined in context | N/A (not supported) |
| `WebChatAdapter` | Loaded in-memory | Loaded on-demand | Server-side tool calls |

### 6.4 LLM Configuration Propagation

Extends the existing `configure-llm.sh` pattern as a Python module:

```python
# studio_api/llm/propagator.py

PROVIDER_DEFAULTS = {
    "anthropic": {"base_url": "https://api.anthropic.com/v1",
                  "model": "claude-sonnet-4-5-20250929"},
    "openai":    {"base_url": "https://api.openai.com/v1",
                  "model": "gpt-4o"},
    "fabric":    {"base_url": "https://ai.fabric-testbed.net/v1",
                  "model": "qwen3-coder-30b"},
    "nrp":       {"base_url": "https://ellm.nrp-nautilus.io/v1",
                  "model": "qwen3-coder-30b"},
    "custom":    {},  # User-provided base_url + api_key
    "ollama":    {"base_url": "http://localhost:11434/v1",
                  "model": "qwen2.5-coder:7b"},
}

class LLMPropagator:
    """Propagates LLM config to all installed AI tools."""

    def propagate(self, workspace: str, config: LLMConfig) -> None:
        """Write provider config to each installed tool via its adapter."""
        for tool in get_installed_tools(workspace):
            adapter = get_adapter(tool.knowledge_adapter)
            adapter.update_llm_config(workspace, config.dict())
```

When a user changes their LLM provider in Settings, the propagator updates all
installed tools simultaneously. If JupyterLab is running, it also reconfigures
`jupyter-ai` with the new provider (same as LoomAI's `_configure_jupyter_ai`).

### 6.5 Model Proxy

For providers that aren't natively supported by all tools (FABRIC AI, NRP,
custom OpenAI-compatible endpoints), studio-api runs a lightweight model proxy
(from the existing `model_proxy.py` in pegasus-ai-workbench) that bridges
requests to the correct upstream endpoint. This allows tools like Claude Code
and OpenCode to use any configured provider transparently.

---

## 7. Workflow Dashboard

### 7.1 Data Sources

The dashboard aggregates workflow state from multiple sources:

| Source | Data | Access method |
|--------|------|---------------|
| Pegasus stampede SQLite DB | Workflow/job state, statistics | Direct file read (`{run_dir}/workflow.db`) |
| `pegasus-status` CLI | Summary status string | subprocess |
| `pegasus-analyzer` CLI | Failure analysis | subprocess |
| `workflow-events.jsonl` | Real-time events (if workflow-monitor daemon is running) | File tail + SSE |
| HTCondor (`condor_q`, `condor_status`) | Pool status, job queue | subprocess / Python bindings |

### 7.2 Workflow Discovery

Studio-api scans for Pegasus run directories on startup and periodically:

```python
# studio_api/workflows/scanner.py

def discover_runs(workspace: str) -> list[WorkflowRun]:
    """Find all Pegasus run directories in the workspace."""
    runs = []
    # Check standard Pegasus output locations
    for braindump in glob(f"{workspace}/**/braindump.yml", recursive=True):
        run_dir = os.path.dirname(braindump)
        bd = yaml.safe_load(open(braindump))
        runs.append(WorkflowRun(
            name=bd.get("pegasus_wf_name", "unknown"),
            run_dir=run_dir,
            submit_dir=bd.get("submit_dir"),
            status=get_status(run_dir),
        ))
    return runs
```

### 7.3 Real-Time Monitoring

For active workflows, studio-api tails the stampede DB and optionally starts a
workflow-monitor daemon in `--server` mode:

```
User opens /workflows/{run_id}
    │
    ▼
GET /api/workflows/{run_id}/events (SSE connection)
    │
    ├── Start workflow-monitor --server {run_dir} (if not already running)
    │   └── Produces workflow-events.jsonl
    │
    ├── Tail workflow-events.jsonl
    │   ├── Parse each JSONL line
    │   └── Send as SSE event to browser
    │
    └── Also poll stampede DB for job-level state
        └── Send job_state events
```

### 7.4 Dashboard Views

**Workflow List** (`/dashboard`):
- Table: Name, Status (running/succeeded/failed/planning), Progress (jobs
  completed/total), Execution Site, Wall Time, Created At
- Status badges with color coding
- Quick actions: Open in Workbench, View Details, Cancel

**Workflow Detail** (`/workflows/[run_id]`):
- Header: Name, status, progress bar
- Tabs:
  - **Jobs**: Table of all jobs with status, runtime, host, exit code
  - **DAG**: Visual DAG rendering (job dependency graph)
  - **Diagnostics**: Hold reasons, failure analysis, stall detection
  - **Logs**: Job stdout/stderr viewer
  - **Resources**: Pool status (slots, CPUs, RAM, GPUs)

---

## 8. AI Workbench

### 8.1 Layout

```
+--sidebar--+--file-tree--+--main-panel---------+--ai-panel--------+
| Dashboard  | project/    | [Tabs: files, terms] | [Tool: Claude] ▼ |
| Workbench  |  bin/       |                     |                  |
| Marketplace|   step1.py  | ┌──────────────────┐ | ┌──────────────┐ |
| Notebooks  |  Docker/    | │ Code Editor      │ | │ Chat history │ |
| Workflows  |   Dockerfile│ │ (active file)    │ | │              │ |
| Settings   |  workflow_  | │                  │ | │ > /scaffold  │ |
|            |   generator | │                  │ | │   earthquake │ |
|            |   .py       | │                  │ | │              │ |
|            |  README.md  | │                  │ | │ [Response... │ |
|            |             | └──────────────────┘ | │  files made] │ |
+            +             + ┌──────────────────┐ | │              │ |
|            |             | │ Terminal (xterm)  │ | └──────────────┘ |
|            |             | │ $ pegasus-plan .. │ | [Input box]      |
|            |             | └──────────────────┘ | [Send]           |
+------------+-------------+---------------------+------------------+
```

### 8.2 AI Tool Panel

The right panel hosts the active AI tool. Users select which tool to use from
a dropdown:

- **PegasusAI Chat** (built-in): SSE streaming chat with tool use, served
  directly by studio-api. Always available, no installation needed.
- **Claude Code**: Terminal session (xterm.js) running `claude` in the workspace.
  Requires installation.
- **OpenCode**: Iframe embedding OpenCode's web UI. Requires installation.
- **Codex CLI**: Terminal session running `codex`. Requires installation.
- **Antigravity**: Terminal session. Requires installation.

For terminal-based tools, the panel shows an xterm.js terminal connected via
WebSocket to a PTY running the tool's binary in the workspace directory (same
pattern as LoomAI's `TerminalCompanionView`).

For web-based tools, the panel shows an iframe pointing to the tool's web UI
(proxied through studio-api).

### 8.3 File Editor

Monaco Editor with:
- Python, YAML, Dockerfile, shell, Markdown syntax highlighting
- File tabs (open multiple files)
- Auto-save
- Read-only mode for files in `/opt/pegasus-ai/knowledge/`

### 8.4 Terminal

xterm.js terminal connected via WebSocket to a bash PTY in the workspace. Users
can run `pegasus-plan`, `pegasus-status`, `docker build`, etc. Multiple terminal
tabs supported.

---

## 9. Frontend Routes

```
/                           → Redirect to /dashboard (if env is ready) or /setup
/setup                      → First-run LLM provider configuration wizard
/dashboard                  → Workflow dashboard (list + stats)
/workbench                  → AI workbench (editor + terminal + AI tool)
/marketplace                → AI tool marketplace (install/manage tools)
/notebooks                  → JupyterLab (launch on demand, iframe to /jupyter/)
/workflows                  → Workflow list (detailed table)
/workflows/[run_id]         → Workflow detail (jobs, DAG, diagnostics, logs)
/settings                   → LLM config, preferences
/settings/llm               → LLM provider configuration
```

---

## 10. API Routes (studio-api)

### Tools

```
GET    /api/tools                       List available tools + install status
GET    /api/tools/{id}                  Tool detail
POST   /api/tools/{id}/install          Install tool + seed knowledge
POST   /api/tools/{id}/uninstall        Remove tool config
POST   /api/tools/{id}/start            Start tool process (returns connection info)
POST   /api/tools/{id}/stop             Stop tool process
GET    /api/tools/{id}/status           Process status (running/stopped/error)
GET    /api/tools/{id}/proxy/{path}     Reverse proxy to web tool UI
```

### Workspace / Files

```
GET    /api/files                       List files (query: path)
GET    /api/files/read                  Read file content (query: path)
POST   /api/files/write                 Write file content
DELETE /api/files                       Delete file (query: path)
POST   /api/files/mkdir                 Create directory
```

### Terminal Sessions

```
WS     /ws/terminal                     WebSocket PTY session (bash)
WS     /ws/terminal/{tool_id}           WebSocket PTY for a specific AI tool
```

### Knowledge

```
GET    /api/knowledge/skills            List skills with metadata
GET    /api/knowledge/skills/{name}     Skill content
GET    /api/knowledge/agents            List agent personas
GET    /api/knowledge/templates         List workflow templates
GET    /api/knowledge/examples          List example workflows
```

### LLM Configuration

```
GET    /api/llm/config                  Current LLM config
PUT    /api/llm/config                  Update LLM provider/model/key
GET    /api/llm/providers               Available providers
POST   /api/llm/validate                Test API key connectivity
```

### JupyterLab

```
POST   /api/jupyter/start               Launch JupyterLab subprocess
POST   /api/jupyter/stop                Stop JupyterLab subprocess
GET    /api/jupyter/status              Check if JupyterLab is running
```

### Workflows

```
GET    /api/workflows                   List discovered workflow runs
GET    /api/workflows/{run_id}          Workflow detail (from stampede DB)
GET    /api/workflows/{run_id}/jobs     Job-level status
GET    /api/workflows/{run_id}/events   SSE stream of monitoring events
POST   /api/workflows/{run_id}/analyze  Run pegasus-analyzer
DELETE /api/workflows/{run_id}          Cancel / pegasus-remove
POST   /api/workflows/submit            Plan + submit a workflow
```

### Chat (Built-in PegasusAI)

```
POST   /api/chat/stream                 SSE streaming chat (with tool use)
POST   /api/chat/stop                   Abort current response
GET    /api/chat/agents                 List agent personas
GET    /api/chat/history                Chat history for current session
```

### Settings

```
GET    /api/settings                    All user settings
PUT    /api/settings                    Update settings
GET    /api/health                      Container health check
```

---

## 11. Database Schema (SQLite)

Single-user environment — SQLite in `~/work/.studio/studio.db`:

```sql
-- Installed AI tools
CREATE TABLE tool_installations (
    tool_id         TEXT PRIMARY KEY,       -- "claude-code", "opencode", etc.
    status          TEXT NOT NULL DEFAULT 'installed',  -- installed, running, error
    config          TEXT DEFAULT '{}',      -- JSON: tool-specific config overrides
    process_pid     INTEGER,               -- PID if running
    web_port        INTEGER,               -- Port if web UI active
    installed_at    TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

-- LLM configuration
CREATE TABLE llm_config (
    id              INTEGER PRIMARY KEY CHECK (id = 1),  -- singleton
    provider        TEXT NOT NULL,          -- anthropic, openai, fabric, etc.
    model           TEXT,
    api_key         TEXT,                   -- stored plaintext (single-user container)
    base_url        TEXT,
    extra_config    TEXT DEFAULT '{}',      -- JSON
    updated_at      TEXT NOT NULL
);

-- Discovered workflow runs
CREATE TABLE workflow_runs (
    run_id          TEXT PRIMARY KEY,       -- braindump wf_uuid or run dir basename
    name            TEXT NOT NULL,
    run_dir         TEXT NOT NULL UNIQUE,
    status          TEXT NOT NULL,          -- planning, running, succeeded, failed
    total_jobs      INTEGER DEFAULT 0,
    completed_jobs  INTEGER DEFAULT 0,
    failed_jobs     INTEGER DEFAULT 0,
    exec_site       TEXT,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

-- Chat history (built-in PegasusAI chat)
CREATE TABLE chat_messages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    role            TEXT NOT NULL,          -- user, assistant, system, tool
    content         TEXT NOT NULL,
    agent_id        TEXT,                   -- workflow-architect, data-engineer, etc.
    tool_calls      TEXT,                   -- JSON: tool call details
    created_at      TEXT NOT NULL
);
```

---

## 12. Container Build

### 12.1 Dockerfile Strategy

Follows LoomAI's pattern: multi-stage build with Node.js frontend compilation
and Python backend in a single production image.

```dockerfile
# Stage 1: Build Next.js frontend (standalone output — no node_modules in prod)
FROM node:20-alpine AS studio-web-builder
WORKDIR /app
COPY studio-web/package*.json ./
RUN npm ci
COPY studio-web/ ./
# next.config.ts must set: output: "standalone"
RUN npm run build

# Stage 2: Main container (Python base with Pegasus + HTCondor)
FROM quay.io/jupyter/scipy-notebook:python-3.11

USER root

# --- s6-overlay for process supervision ---
ARG S6_OVERLAY_VERSION=3.2.0.2
ADD https://github.com/just-containers/s6-overlay/releases/download/v${S6_OVERLAY_VERSION}/s6-overlay-noarch.tar.xz /tmp
ADD https://github.com/just-containers/s6-overlay/releases/download/v${S6_OVERLAY_VERSION}/s6-overlay-x86_64.tar.xz /tmp
RUN tar -C / -Jxpf /tmp/s6-overlay-noarch.tar.xz \
    && tar -C / -Jxpf /tmp/s6-overlay-x86_64.tar.xz \
    && rm /tmp/s6-overlay-*.tar.xz

# --- System dependencies ---
RUN apt-get update && apt-get install -y --no-install-recommends \
    nginx curl git vim htop tmux jq gnupg software-properties-common \
    && rm -rf /var/lib/apt/lists/*

# --- Pegasus WMS + HTCondor (same as pegasus-ai-workbench) ---
RUN pip install --no-cache-dir pegasus-wms==5.1.2
# HTCondor from official repos (same as pegasus-ai-workbench/Dockerfile)
RUN curl -fsSL https://htcss-downloads.chtc.wisc.edu/repo/keys/HTCondor-25.x-Key \
        -o /etc/apt/keyrings/htcondor.asc \
    && curl -fsSL https://htcss-downloads.chtc.wisc.edu/repo/ubuntu/htcondor-25.x-noble.list \
        -o /etc/apt/sources.list.d/htcondor.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends condor \
    && rm -rf /var/lib/apt/lists/*

# --- Studio API (FastAPI backend) ---
COPY studio-api/ /opt/studio/api/
RUN pip install --no-cache-dir -r /opt/studio/api/requirements.txt

# --- JupyterLab + jupyter-ai (launched on demand) ---
RUN pip install --no-cache-dir \
    jupyter-ai langchain-anthropic langchain-openai jupyter-server-proxy

# --- Studio Web (Next.js standalone — ~15MB vs ~200MB+ with node_modules) ---
COPY --from=studio-web-builder /app/.next/standalone /opt/studio/web/
COPY --from=studio-web-builder /app/.next/static /opt/studio/web/.next/static
COPY --from=studio-web-builder /app/public /opt/studio/web/public

# --- Knowledge store (from plugin marketplace + workbench ai-tools) ---
COPY knowledge/ /opt/pegasus-ai/knowledge/

# --- Nginx config ---
COPY nginx/nginx.conf /etc/nginx/nginx.conf

# --- s6 service definitions ---
COPY s6/nginx     /etc/s6-overlay/s6-rc.d/nginx/
COPY s6/studio-api /etc/s6-overlay/s6-rc.d/studio-api/
COPY s6/studio-web /etc/s6-overlay/s6-rc.d/studio-web/
COPY s6/init      /etc/s6-overlay/s6-rc.d/init/

# --- Scripts ---
COPY scripts/entrypoint.sh /usr/local/bin/studio-entrypoint.sh
COPY scripts/configure-llm.sh /etc/profile.d/pegasus-ai-llm.sh
RUN chmod +x /usr/local/bin/studio-entrypoint.sh /etc/profile.d/pegasus-ai-llm.sh

USER $NB_UID
EXPOSE 8888

ENTRYPOINT ["/init"]
```

**Next.js standalone output**: The `output: "standalone"` setting in
`next.config.ts` produces a self-contained Node.js server (~15MB) that includes
only the dependencies actually used. This avoids copying the full
`node_modules/` (~200MB+) into the production image — a significant improvement
over LoomAI's approach.

### 12.2 Entrypoint

The entrypoint uses **s6-overlay** for process supervision instead of bare
`wait -n`. If nginx or uvicorn crashes, s6 restarts it automatically. This is
a significant reliability improvement over LoomAI's approach where any process
exit kills the container.

```bash
#!/bin/bash
# scripts/entrypoint.sh — Called by s6 init stage as a one-shot.
# Runs first-launch setup, then s6 starts the long-running services.

set -euo pipefail

STUDIO_DIR="$HOME/work/.studio"
INIT_MARKER="$STUDIO_DIR/.initialized"

# Source LLM env if present
if [ -f "$HOME/.pegasus-ai/.env" ]; then
    set -a; . "$HOME/.pegasus-ai/.env"; set +a
fi

# First-run initialization
if [ ! -f "$INIT_MARKER" ]; then
    mkdir -p "$STUDIO_DIR"

    echo ""
    echo "══════════════════════════════════════════════════════════"
    echo "  Welcome to PegasusAI Studio!"
    echo "══════════════════════════════════════════════════════════"
    echo ""

    # Initialize SQLite database
    python3 /opt/studio/api/init_db.py

    # Seed default LLM config from environment
    python3 /opt/studio/api/seed_config.py

    touch "$INIT_MARKER"
fi

# Propagate LLM config to any installed tools
source /etc/profile.d/pegasus-ai-llm.sh || true
python3 /opt/studio/api/propagate_llm.py || true
```

**s6 service definitions** (each is a directory under `/etc/s6-overlay/s6-rc.d/`):

```bash
# s6/nginx/run
#!/command/execlineb -P
nginx -g "daemon off;"

# s6/studio-api/run
#!/command/execlineb -P
cd /opt/studio/api
uvicorn main:app --host 0.0.0.0 --port 8080

# s6/studio-web/run
#!/command/execlineb -P
cd /opt/studio/web
node server.js

# s6/init/up — one-shot that runs entrypoint.sh before services start
```

JupyterLab is **not** an s6 service — it's launched on demand via
`POST /api/jupyter/start` and managed as a subprocess by studio-api.

### 12.3 Build Targets

```makefile
# Makefile

build:
	docker build -t kthare10/pegasus-ai-studio:latest .

build-access:
	docker build -t kthare10/pegasus-ai-studio:access \
		--build-arg ENABLE_ANNEX=true .

run:
	docker run --rm -it \
		-p 8888:8888 \
		-v $(PWD)/work:/home/jovyan/work \
		--env-file .env \
		kthare10/pegasus-ai-studio:latest

push:
	docker push kthare10/pegasus-ai-studio:latest
	docker push kthare10/pegasus-ai-studio:access

test:
	docker run --rm kthare10/pegasus-ai-studio:latest \
		bash -c "pegasus-version && python3 -c 'import Pegasus' && \
		         curl -sf http://localhost:8080/api/health"
```

---

## 13. Open OnDemand Integration

For OOD deployment, PegasusAI Studio runs as an Interactive App:

```yaml
# ood/manifest.yml
---
name: PegasusAI Studio
category: Interactive Apps
subcategory: AI Workflow Development
description: >
  AI-powered scientific workflow development with Pegasus WMS.
  Includes workflow dashboard, AI tool marketplace, code editor,
  and JupyterLab notebooks.
icon: fa://flask
```

```yaml
# ood/form.yml.erb
---
attributes:
  num_hours:
    widget: number_field
    label: "Number of hours"
    value: 4
    min: 1
    max: 24
  num_cores:
    widget: number_field
    label: "CPU cores"
    value: 4
    min: 1
    max: 16
  memory_gb:
    widget: number_field
    label: "Memory (GB)"
    value: 16
    min: 4
    max: 64
  llm_provider:
    widget: select
    label: "LLM Provider"
    options:
      - ["Anthropic (Claude)", "anthropic"]
      - ["OpenAI (GPT/Codex)", "openai"]
      - ["FABRIC AI Gateway", "fabric"]
      - ["NRP (Nautilus eLLM)", "nrp"]
      - ["None (configure later)", "none"]
  llm_api_key:
    widget: text_field
    label: "API Key (optional — can be set later in Settings)"
    value: ""
```

```erb
<%# ood/template/script.sh.erb %>
#!/bin/bash

export LLM_PROVIDER="<%= llm_provider %>"
export LLM_API_KEY="<%= llm_api_key %>"
export STUDIO_PORT="${port}"

singularity run \
  --bind $HOME/work:/home/jovyan/work \
  --env LLM_PROVIDER="${LLM_PROVIDER}" \
  --env LLM_API_KEY="${LLM_API_KEY}" \
  docker://kthare10/pegasus-ai-studio:access
```

---

## 14. Project Directory Structure

```
pegasus-ai-studio/
├── SPEC.md                         # This file
├── Dockerfile                      # Multi-stage container build
├── Makefile                        # Build/run/push targets
├── docker-compose.yml              # Production: single container
├── docker-compose.dev.yml          # Development: separate frontend + backend
├── .env.example                    # Environment variables
│
├── studio-api/                     # FastAPI backend
│   ├── main.py                     # App factory + lifespan + router registration
│   ├── requirements.txt
│   ├── init_db.py                  # SQLite schema creation
│   ├── seed_config.py              # First-run LLM config from env
│   ├── propagate_llm.py            # CLI: propagate LLM to all tools
│   │
│   ├── routers/
│   │   ├── tools.py                # /api/tools/* — install, start, stop, proxy
│   │   ├── files.py                # /api/files/* — workspace file operations
│   │   ├── knowledge.py            # /api/knowledge/* — skills, agents, templates
│   │   ├── llm.py                  # /api/llm/* — provider config
│   │   ├── jupyter.py              # /api/jupyter/* — start, stop, status
│   │   ├── workflows.py            # /api/workflows/* — monitoring, submit
│   │   ├── chat.py                 # /api/chat/* — built-in PegasusAI chat
│   │   ├── ai_terminal.py          # /ws/terminal/* — WebSocket PTY for AI tools
│   │   ├── terminal.py             # /ws/terminal — WebSocket PTY (bash)
│   │   └── settings.py             # /api/settings
│   │
│   ├── services/                   # Business logic (keeps routers thin)
│   │   ├── installer.py            # npm install, disk checks, adapter calls
│   │   ├── process_mgr.py          # Subprocess lifecycle, PTY management
│   │   ├── workflow_scanner.py     # Discover Pegasus run directories
│   │   ├── workflow_monitor.py     # Tail events, query stampede DB
│   │   └── workflow_submitter.py   # pegasus-plan --submit wrapper
│   │
│   ├── knowledge/
│   │   ├── adapters.py             # KnowledgeAdapter ABC + implementations
│   │   ├── claude_code.py          # ClaudeCodeAdapter
│   │   ├── opencode.py             # OpenCodeAdapter
│   │   ├── codex_cli.py            # CodexCLIAdapter
│   │   ├── antigravity.py          # AntigravityAdapter
│   │   └── web_chat.py             # WebChatAdapter (built-in)
│   │
│   ├── llm/
│   │   ├── propagator.py           # LLMPropagator (update all tools)
│   │   └── model_proxy.py          # Model proxy for non-native providers
│   │
│   ├── logging_config.py           # structlog JSON configuration
│   │
│   └── tests/                      # Backend tests (pytest)
│       ├── conftest.py             # Fixtures (test DB, mock workspace)
│       ├── test_tools.py           # Tool install/start/stop
│       ├── test_knowledge.py       # Adapter tests
│       ├── test_llm.py             # Propagator tests
│       └── test_workflows.py       # Scanner, monitor tests
│
├── studio-web/                     # Next.js frontend
│   ├── package.json
│   ├── next.config.ts
│   ├── tailwind.config.ts
│   │
│   ├── app/
│   │   ├── layout.tsx              # Root layout (sidebar nav)
│   │   ├── page.tsx                # Redirect to /dashboard
│   │   ├── setup/
│   │   │   └── page.tsx            # First-run wizard
│   │   ├── dashboard/
│   │   │   └── page.tsx            # Workflow dashboard
│   │   ├── workbench/
│   │   │   └── page.tsx            # AI workbench (editor + terminal + AI)
│   │   ├── marketplace/
│   │   │   └── page.tsx            # AI tool marketplace
│   │   ├── notebooks/
│   │   │   └── page.tsx            # JupyterLab (launch + iframe)
│   │   ├── workflows/
│   │   │   ├── page.tsx            # Workflow list
│   │   │   └── [runId]/
│   │   │       └── page.tsx        # Workflow detail
│   │   └── settings/
│   │       ├── page.tsx            # Settings overview
│   │       └── llm/
│   │           └── page.tsx        # LLM provider config
│   │
│   ├── components/
│   │   ├── ui/                     # shadcn/ui components
│   │   ├── sidebar.tsx             # Navigation sidebar
│   │   ├── file-tree.tsx           # Workspace file explorer
│   │   ├── code-editor.tsx         # Monaco editor wrapper
│   │   ├── terminal.tsx            # xterm.js terminal wrapper
│   │   ├── ai-panel.tsx            # AI tool panel (chat/terminal/iframe)
│   │   ├── jupyter-view.tsx        # JupyterLab launcher + iframe
│   │   ├── tool-card.tsx           # Marketplace tool card
│   │   ├── workflow-table.tsx      # Workflow list table
│   │   ├── workflow-dag.tsx        # DAG visualization
│   │   ├── job-table.tsx           # Job status table
│   │   └── pool-status.tsx         # HTCondor pool status
│   │
│   ├── lib/
│   │   ├── api.ts                  # API client (TanStack Query provider)
│   │   ├── queries/                # TanStack Query hooks per domain
│   │   │   ├── tools.ts            # useTools, useToolStatus, useInstallTool
│   │   │   ├── workflows.ts        # useWorkflows, useWorkflowDetail
│   │   │   ├── knowledge.ts        # useSkills, useAgents, useTemplates
│   │   │   └── llm.ts              # useLLMConfig, useProviders
│   │   ├── stores/                 # Zustand stores (client-only state)
│   │   │   ├── tool-store.ts       # Active tool, panel state
│   │   │   ├── workspace-store.ts  # Open files, active editor tab
│   │   │   └── layout-store.ts     # Panel sizes, sidebar collapsed
│   │   ├── ws.ts                   # WebSocket client
│   │   └── sse.ts                  # SSE event source wrapper
│   │
│   └── __tests__/                  # Vitest + React Testing Library
│       ├── setup.ts                # Test setup (MSW mock server)
│       ├── components/
│       │   ├── tool-card.test.tsx   # Marketplace card states
│       │   ├── ai-panel.test.tsx    # Tool switching, SSE connection
│       │   └── jupyter-view.test.tsx # Launch flow, iframe loading
│       └── lib/
│           ├── queries.test.ts      # TanStack Query hook tests
│           └── stores.test.ts       # Zustand store tests
│
├── knowledge/                      # Canonical knowledge store (→ /opt/pegasus-ai/knowledge/)
│   ├── skills/                     # (from plugin marketplace)
│   ├── agents/                     # (from workbench ai-tools)
│   ├── templates/                  # (from plugin marketplace)
│   ├── examples/                   # (from plugin marketplace)
│   ├── references/                 # PEGASUS_AI.md, PEGASUS.md
│   └── mcp/
│       └── servers.json
│
├── nginx/
│   └── nginx.conf                  # Reverse proxy config
│
├── s6/                             # s6-overlay service definitions
│   ├── init/                       # One-shot: runs entrypoint.sh
│   ├── nginx/                      # Long-run: nginx -g "daemon off;"
│   ├── studio-api/                 # Long-run: uvicorn
│   └── studio-web/                 # Long-run: node server.js
│
├── scripts/
│   ├── entrypoint.sh               # First-run init (called by s6 init stage)
│   └── configure-llm.sh            # LLM propagation (legacy compat)
│
└── ood/                            # Open OnDemand Interactive App
    ├── manifest.yml
    ├── form.yml.erb
    ├── submit.yml.erb
    └── template/
        └── script.sh.erb
```

---

## 15. Migration from Workbench

Existing workbench users have persistent `~/work/` volumes with workbench-era
configs. Studio detects and migrates these on first startup:

| Workbench artifact | Studio migration |
|-------------------|-----------------|
| `~/.pegasus-ai/.env` | Read by studio-api to seed `llm_config` table |
| `~/work/CLAUDE.md` | Preserved (updated by ClaudeCodeAdapter on tool install) |
| `~/work/AGENTS.md` | Preserved (updated by OpenCodeAdapter on tool install) |
| `~/work/.opencode/` | Preserved (updated by OpenCodeAdapter on tool install) |
| `~/work/.mcp.json` | Preserved (updated by ClaudeCodeAdapter on tool install) |
| `~/.pegasus-ai/.initialized` | Ignored — Studio uses its own marker at `~/work/.studio/.initialized` |

Studio's `init_db.py` checks for `~/.pegasus-ai/.env` and pre-populates the
`llm_config` table from it, so existing users don't need to reconfigure their
LLM provider.

---

## 16. V2 Evolution Path

V1 is designed so that the following V2 additions require minimal rewrites:

| V1 (single container) | V2 (multi-service platform) |
|------------------------|----------------------------|
| SQLite in `~/work/.studio/` | PostgreSQL (shared) |
| No auth (JupyterHub handles it) | CILogon OIDC in studio-api |
| Single workspace = `~/work/` | Multi-user workspaces on shared storage |
| Tools installed in-container | Tools in per-user sidecar containers |
| workflow-monitor subprocess | workflow-monitor as shared daemon |
| Docker image spawned by JupyterHub | Kubernetes with Helm chart |

The API routes, frontend pages, knowledge adapters, and tool registry remain
the same — only the backing infrastructure changes.

---

## 17. Authentication Note (V1)

In V1, the container itself has no authentication — it runs as a single user
inside JupyterHub or OOD, which handle auth externally. The Studio UI is
accessible to whoever JupyterHub/OOD authenticated before spawning the container.

For the `/setup` first-run wizard, the user provides:
- LLM provider + API key (stored in SQLite, not encrypted — single-user container)
- Optionally: ACCESS allocation ID for workflow submission

This matches the current workbench behavior where `pegasus-ai-setup` is an
interactive wizard that writes to `~/.pegasus-ai/.env`.

---

## 18. Improvements over LoomAI

Studio uses LoomAI as a reference architecture but improves on several areas:

| LoomAI | PegasusAI Studio | Why |
|--------|-----------------|-----|
| Single 239KB `App.tsx` with all state | Zustand stores + TanStack Query per domain | Maintainable, testable, no monolith root component |
| Hand-rolled request dedup in `api/client.ts` | TanStack Query (caching, background refetch, optimistic updates) | Industry standard, less code, better UX |
| Raw `useState` + `useCallback` everywhere | Zustand for client state, TanStack Query for server state | Clear separation, no prop drilling |
| 3,000+ line route files (`ai_chat.py`, `slices.py`) | Router files < 500 lines, logic in `services/` | Readable, testable, reviewable |
| `wait -n` process supervision | s6-overlay with auto-restart | Crashed nginx/uvicorn recovers automatically |
| Full `node_modules/` in prod image (~200MB) | Next.js standalone output (~15MB) | Smaller image, faster pulls |
| No frontend tests | Vitest + React Testing Library + MSW from day one | Catch regressions in tool install, SSE, LLM config flows |
| `print()` / basic logging | structlog JSON output | Parseable by log aggregators, structured debugging |
| CodeMirror 6 (lightweight editor) | Monaco Editor (VS Code engine) | IntelliSense, better Python/YAML support for workflow development |

---

## 19. Technology Summary

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| Frontend | Next.js 15 (standalone), React 19, TypeScript | SSR, App Router, ~15MB prod output |
| Server state | TanStack Query v5 | Caching, dedup, background refetch, optimistic updates |
| Client state | Zustand | Lightweight, no boilerplate, domain-specific stores |
| UI | TailwindCSS, shadcn/ui | Composable, accessible, no vendor lock-in |
| Code editor | Monaco Editor | VS Code engine, rich Python/YAML/Dockerfile support |
| Terminal | xterm.js + WebSocket PTY | Industry standard for browser terminals |
| Backend | FastAPI, Python 3.11, Uvicorn | Async, same stack as LoomAI |
| Logging | structlog (JSON) | Structured, parseable, container-friendly |
| Database | SQLite (V1), PostgreSQL (V2) | Single-user simplicity, easy upgrade path |
| Reverse proxy | Nginx | Path-based routing, WebSocket support |
| Process supervisor | s6-overlay | Auto-restart crashed services, proper signal handling |
| Container base | quay.io/jupyter/scipy-notebook:python-3.11 | Same as current workbench |
| AI tool install | npm (global) | Claude Code, OpenCode, Codex are npm packages |
| JupyterLab | Subprocess, launched on demand | Same pattern as LoomAI |
| Frontend tests | Vitest, React Testing Library, MSW | Fast, component + integration coverage |
| Backend tests | pytest, httpx (async) | FastAPI native test client |

---

## 20. Implementation Phases

### Phase 1: Runnable Backend Skeleton

**Goal**: A FastAPI server that starts, connects to SQLite, and serves health checks.

| Deliverable | Description |
|-------------|-------------|
| `requirements.txt` | FastAPI, uvicorn, aiosqlite, httpx, structlog, pydantic, etc. |
| `logging_config.py` | structlog JSON processor chain, called once at startup |
| `db.py` | `Database` class (aiosqlite): 4 tables — `tool_installations`, `llm_config`, `workflow_runs`, `chat_messages` |
| `models.py` | Pydantic v2 enums (`ToolStatus`, `WorkflowStatus`, `LLMProvider`) + request/response models |
| `main.py` | FastAPI app factory, `@asynccontextmanager` lifespan (connect DB → yield → cleanup), CORS middleware |
| `routers/health.py` | `GET /api/health` (ok + version), `GET /api/health/detailed` (DB + pegasus-version + condor_version) |
| `routers/settings.py` | `GET/PUT /api/settings` — LLM config + installed tools summary |
| `init_db.py` | CLI script: `asyncio.run(db.connect())` to create schema |
| `seed_config.py` | CLI script: reads `~/.pegasus-ai/.env`, inserts into `llm_config` |
| `tests/` | Fixtures (`tmp_db`, `TestClient`), health endpoint tests |

**Verification**: `uvicorn main:app --port 8080` → `curl localhost:8080/api/health` returns `{"status":"ok","version":"0.1.0"}`.

### Phase 2: LLM Configuration + Knowledge Layer

**Goal**: Users can configure their LLM provider and the API propagates settings to all installed tools.

| Deliverable | Description |
|-------------|-------------|
| `llm/providers.py` | `PROVIDERS` dict (6 providers), `fetch_models()` via async httpx, `PROVIDER_DEFAULTS` |
| `llm/propagator.py` | `LLMPropagator.propagate()` — iterates installed tools, calls each adapter's `update_llm_config()` |
| `routers/llm.py` | `GET/PUT /api/llm/config`, `GET /api/llm/providers`, `POST /api/llm/validate` |
| `knowledge/adapters.py` | `KnowledgeAdapter` ABC with `install()`, `update_llm_config()`, `uninstall()` |
| `knowledge/claude_code.py` | Copy CLAUDE.md, write .mcp.json, register plugins |
| `knowledge/opencode.py` | Write opencode.json, seed .opencode/agents/ and .opencode/skills/ |
| `knowledge/codex_cli.py` | Write AGENTS.md |
| `knowledge/antigravity.py` | Write .antigravity/context.md |
| `knowledge/web_chat.py` | No-op (built-in chat loads knowledge server-side) |
| `routers/knowledge.py` | Skills, agents, templates, examples endpoints |

**Verification**: `PUT /api/llm/config` with provider/key → `GET /api/llm/config` returns it → `GET /api/knowledge/skills` lists skills.

### Phase 3: AI Tool Marketplace + Terminals

**Goal**: Users can install, start, and connect to AI coding tools.

| Deliverable | Description |
|-------------|-------------|
| `services/installer.py` | `ToolInstaller.install()` — check binary, npm install, call adapter, update DB |
| `services/process_mgr.py` | `ProcessManager` — PTY and web subprocess lifecycle, dynamic port allocation |
| `routers/tools.py` | `GET/POST /api/tools` — list, install, uninstall, start, stop, status |
| `routers/files.py` | `GET/POST/DELETE /api/files` — workspace file operations with path sandboxing |
| `routers/jupyter.py` | `POST /api/jupyter/start\|stop`, `GET /api/jupyter/status` |
| `routers/terminal.py` | `WS /ws/terminal` — bash PTY via WebSocket |
| `routers/ai_terminal.py` | `WS /ws/terminal/{tool_id}` — AI tool PTY via WebSocket |

**Verification**: `POST /api/tools/claude-code/install` → `GET /api/tools` shows installed → `POST /api/tools/claude-code/start` → WebSocket connects at `/ws/terminal/claude-code`.

### Phase 4: Workflow Monitoring

**Goal**: Real-time discovery and monitoring of Pegasus workflows.

| Deliverable | Description |
|-------------|-------------|
| `services/workflow_scanner.py` | Discover Pegasus run dirs via `braindump.yml`, parse metadata |
| `services/workflow_monitor.py` | Query stampede SQLite DB for job stats, tail event JSONL files |
| `services/workflow_submitter.py` | `pegasus-plan --submit` wrapper, `pegasus-remove` for cancellation |
| `routers/workflows.py` | List, detail, jobs, SSE events, analyze, cancel, submit |

**Verification**: Create a mock `braindump.yml` → `GET /api/workflows` discovers it → `GET /api/workflows/{id}/jobs` returns job data.

### Phase 5: Built-in Chat

**Goal**: SSE-streaming chat with tool use, supporting both Anthropic and OpenAI-compatible providers.

| Deliverable | Description |
|-------------|-------------|
| `routers/chat.py` | `POST /api/chat/stream` (SSE), `POST /api/chat/stop`, `GET /api/chat/agents`, `GET /api/chat/history` |
| Tool calling loop | Up to 50 rounds of tool use (write_file, read_file, run_command, etc.) |
| Slash commands | `/scaffold`, `/debug`, `/review`, `/wrapper`, `/dockerfile`, `/convert` inject skill prompts |
| Chat persistence | Messages saved to `chat_messages` table |

**Verification**: Configure LLM via `/api/llm/config` → `POST /api/chat/stream` with messages → SSE events stream back.

### Phase 6: Frontend (Next.js) — Future

| Deliverable | Description |
|-------------|-------------|
| Dashboard page | Workflow list with real-time status |
| AI Workbench page | Tool marketplace cards, xterm.js terminals as tabs |
| Settings page | LLM provider config, model selection |
| Chat panel | SSE-streaming chat with tool results display |
| Zustand stores | `useToolStore`, `useWorkflowStore`, `useLLMStore`, `useWorkspaceStore` |
| TanStack Query | Server state for tools, workflows, settings |

### Phase 7: Container + Deployment — Future

| Deliverable | Description |
|-------------|-------------|
| `Dockerfile` | Multi-stage: base → Pegasus/HTCondor → studio-api → frontend → nginx + s6-overlay |
| `nginx.conf` | Path routing: `/` → frontend, `/api/` → backend, `/ws/` → WebSocket, `/jupyter/` → JupyterLab |
| `s6-overlay` services | Auto-restart uvicorn, Next.js, nginx |
| Entrypoint | `init_db.py` + `seed_config.py` + service start |
