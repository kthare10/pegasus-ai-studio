# Pegasus AI Workbench

A containerized development environment for building scientific workflows with Pegasus WMS, powered by AI coding agents.

**Bundled tools:**

| Tool | Purpose |
|------|---------|
| [JupyterLab](https://jupyter.org/) | Interactive notebooks and terminal |
| [Pegasus WMS](https://pegasus.isi.edu/) 5.1 | Workflow management system |
| [HTCondor](https://htcondor.org/) | Job scheduling |
| [Claude Code](https://claude.ai/code) | AI coding agent (Anthropic) |
| [OpenCode](https://opencode.ai/) | AI coding agent (multi-provider) |
| [Jupyter AI](https://github.com/jupyterlab/jupyter-ai) | In-notebook `%%ai` cell magic |
| [pegasus-ai](../pegasus-ai/) | Pegasus-specific AI assistant |

All AI tools come pre-configured with Pegasus workflow development skills, agents, and reference material.

## Quick Start

### 1. Configure your API key

```bash
cp .env.example .env
```

Edit `.env` and set your provider and API key:

```bash
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-api03-xxxxx
```

### 2. Build and run

```bash
make build
make run
```

Or with Docker Compose:

```bash
docker compose up
```

### 3. Open JupyterLab

Navigate to http://localhost:8888 in your browser.

## Configuration

### Supported Providers

| Provider | `LLM_PROVIDER` | Required env vars |
|----------|----------------|-------------------|
| Anthropic (Claude) | `anthropic` | `ANTHROPIC_API_KEY` |
| OpenAI (GPT) | `openai` | `OPENAI_API_KEY` |
| FABRIC AI | `fabric` | `FABRIC_AI_API_KEY` |
| NRP / Nautilus eLLM | `nrp` | `NRP_API_KEY` |
| Custom endpoint | `custom` | `OPENAI_API_BASE`, `OPENAI_API_KEY`, `OPENAI_MODEL` |
| Ollama (local) | `ollama` | `OLLAMA_HOST` (default: `http://localhost:11434`) |

### Setting the model

Each provider has a sensible default. Override with `LLM_MODEL`:

```bash
# In .env
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-xxxxx
LLM_MODEL=claude-sonnet-4-5-20250929   # optional, this is the default
```

Provider defaults:

| Provider | Default model |
|----------|--------------|
| `anthropic` | `claude-sonnet-4-5-20250929` |
| `openai` | `gpt-4o` |
| `fabric` | `qwen3-coder-30b` |
| `nrp` | `qwen3-coder-30b` |
| `custom` | Value of `OPENAI_MODEL` |
| `ollama` | `qwen2.5-coder:7b` |

### Interactive setup wizard

If you skip the `.env` file, configure inside the running container:

```bash
# Open a JupyterLab terminal, then:
pegasus-ai-setup
```

The wizard prompts for provider, API key, and model, then propagates settings to all tools.

### FABRIC AI

```bash
LLM_PROVIDER=fabric
FABRIC_AI_API_KEY=your-fabric-token
# LLM_MODEL=qwen3-coder-30b   # optional, this is the default
```

### NRP / Nautilus eLLM

```bash
LLM_PROVIDER=nrp
NRP_API_KEY=your-nrp-token
# LLM_MODEL=qwen3-coder-30b   # optional, this is the default
```

### Custom / institutional endpoints

For self-hosted LLMs (vLLM, TGI, LiteLLM proxy):

```bash
LLM_PROVIDER=custom
OPENAI_API_BASE=https://llm.university.edu/v1
OPENAI_API_KEY=inst-key-xxxxx
OPENAI_MODEL=meta-llama/Llama-3.3-70B
```

### Air-gapped / Ollama

Uncomment the Ollama service in `docker-compose.yml`, then:

```bash
LLM_PROVIDER=ollama
OLLAMA_HOST=http://ollama:11434
```

Pull a model after starting:

```bash
docker compose exec ollama ollama pull qwen2.5-coder:7b
```

### Model proxy for non-native providers

OpenCode's built-in agents use hardcoded model names (e.g. `gpt-5.2-chat-latest`) that don't exist on FABRIC AI, NRP, or other self-hosted endpoints. When using these providers, the workbench automatically starts a **model name rewriting proxy** that intercepts API requests and maps unknown model names to your configured default.

This is transparent — no user action is required. The proxy is started automatically when the OpenCode web UI launches with `fabric`, `nrp`, `custom`, or `ollama` as the provider. It is skipped for `anthropic` and `openai` since those providers natively support the model names OpenCode expects.

You can optionally set a separate small model for OpenCode's tool calls (cheaper/faster than the main coding model):

```bash
LLM_SMALL_MODEL=qwen3-coder-8b   # optional, defaults to LLM_MODEL
```

## Using the AI Tools

All tools are available from JupyterLab terminals.

### Claude Code

```bash
cd ~/work/my-workflow
claude
```

Claude Code has the `scitech` plugin marketplace pre-registered with 7 Pegasus skills:

```
/pegasus-scaffold     # Create a new workflow project
/pegasus-wrapper      # Generate a wrapper script
/pegasus-dockerfile   # Generate a Dockerfile
/pegasus-convert      # Convert Snakemake/Nextflow to Pegasus
/pegasus-review       # Audit workflow against best practices
/pegasus-debug        # Diagnose workflow failures
/pegasus-help         # Show available skills
```

### OpenCode

```bash
cd ~/work/my-workflow
opencode
```

OpenCode has 3 Pegasus-specific agents (switch with Tab):
- **workflow-architect** — DAG design, catalogs, data staging
- **pipeline-debugger** — Failure diagnosis, log reading
- **data-engineer** — Data acquisition and preprocessing

And 7 slash-command skills: `/scaffold`, `/wrapper`, `/dockerfile`, `/convert`, `/review`, `/debug`, `/help`

### Jupyter AI (notebooks)

In any notebook cell:

```python
%%ai anthropic:claude-sonnet-4-5-20250929
Generate a Pegasus workflow that downloads USGS earthquake data
for the last 30 days and runs a clustering analysis.
```

Or use the Jupyternaut chat sidebar for conversational help.

### pegasus-ai

```bash
pegasus-ai
```

The native Pegasus AI assistant with access to the full knowledge base.

## Building Workflows

### Typical workflow

1. **Scaffold**: Open a terminal, run `claude`, then `/pegasus-scaffold`
2. **Iterate**: Edit wrapper scripts, test locally with `run_manual.sh`
3. **Review**: Run `/pegasus-review` to catch common pitfalls
4. **Submit**: `pegasus-plan --submit -s condorpool workflow.yml`
5. **Monitor**: `pegasus-status <run-dir>`
6. **Debug**: If it fails, run `/pegasus-debug`

### Submitting workflows

```bash
# Generate and submit
python workflow_generator.py --submit [args]

# Or plan separately
python workflow_generator.py [args]
pegasus-plan --submit -s condorpool -o local workflow.yml

# Monitor
pegasus-status /path/to/run
pegasus-analyzer /path/to/run
```

## Build Reference

All build commands use the parent `tool/` directory as build context (so the Dockerfile can access `pegasus-ai/` and `claude-plugin-marketplace/`).

```bash
make build          # Full image (latest)
make build-lite     # Lite image (no CLI agents, just JupyterLab + Jupyter AI)
make build-access   # ACCESS variant (HTCondor Annex pre-configured)
make run            # Run full image on port 8888
make run-lite       # Run lite image
make test           # Smoke test (verify all tools installed)
make push           # Push to Docker Hub (kthare10 registry)
make clean          # Remove local images
```

### Image variants

| Variant | Tag | What's included |
|---------|-----|-----------------|
| **Full** | `latest` | JupyterLab + Pegasus + HTCondor + Claude Code + OpenCode + Jupyter AI |
| **Lite** | `lite` | JupyterLab + Pegasus + HTCondor + Jupyter AI (no CLI agents) |
| **ACCESS** | `access` | Full + ACCESS HTCondor Annex configs |

### Docker Compose

```bash
docker compose up              # Build + run
docker compose up -d           # Detached
docker compose down            # Stop
docker compose build --no-cache  # Force rebuild
```

## File Structure

```
pegasus-ai-workbench/
├── Dockerfile              # Full image
├── Dockerfile.lite         # Lite variant (no CLI agents)
├── docker-compose.yml      # Orchestration
├── Makefile                # Build targets
├── .env.example            # Environment variable template
├── .dockerignore
├── ai-tools/               # AI tool configurations (copied into image)
│   ├── shared/
│   │   └── PEGASUS_AI.md       # Master context → seeded as AGENTS.md
│   ├── opencode/
│   │   ├── opencode.json       # OpenCode provider config
│   │   ├── agents/             # 3 Pegasus-specific agent personas
│   │   └── skills/             # 7 slash-command skills
│   └── claude-code/
│       └── CLAUDE.md           # In-container Claude Code instructions
├── config/
│   ├── jupyter_ai_config.py    # Jupyter AI server defaults
│   └── opencode-extension/     # OpenCode web UI extension (API + panel)
└── scripts/
    ├── entrypoint.sh           # Container entrypoint
    ├── pegasus-ai-setup.sh     # Interactive LLM setup wizard
    ├── configure-llm.sh        # Login-time env→config propagation
    ├── register-plugins.sh     # First-launch Claude Code plugin setup
    └── model_proxy.py          # Model name rewriting proxy for OpenCode
```

## How Configuration Flows

```
.env file / docker env vars / pegasus-ai-setup wizard
                    │
                    ▼
    LLM_PROVIDER + LLM_MODEL + API key
                    │
                    ▼
        configure-llm.sh (on every login)
                    │
        ┌───────────┼───────────┐
        ▼           ▼           ▼
   opencode.json  PEGASUS_AI_LLM_*  (env vars)
   (rewritten)    (exported)
        │           │
        ▼           ▼
     OpenCode    pegasus-ai
        │
        ▼ (fabric/nrp/custom/ollama only)
   model_proxy.py on :9199
   Rewrites unknown model names → default model
   OpenCode web UI routes through proxy automatically

   Claude Code reads ANTHROPIC_API_KEY directly from env.
   Jupyter AI is configured via its settings panel or env vars.
```

API keys are **never** baked into the Docker image. They are injected at runtime via:
1. `.env` file (bind-mounted or created by wizard)
2. Environment variables (`docker run -e` or `docker compose`)
3. Kubernetes secrets (for JupyterHub deployments)
