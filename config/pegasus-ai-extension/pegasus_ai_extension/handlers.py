"""Tornado request handlers for the PegasusAI chat extension.

Provides SSE-streaming chat with tool-calling loop, agent management,
model discovery, and panel serving.  Supports both Anthropic Messages API
and OpenAI-compatible chat completions API.
"""

import json
import os
import re
import uuid

import httpx

from jupyter_server.base.handlers import JupyterHandler

from .tools import (
    TOOL_DEFINITIONS,
    TOOL_DEFINITIONS_ANTHROPIC,
    execute_tool,
)

# AI tools source directory (baked into the container image)
_AI_TOOLS_SRC = "/opt/pegasus-ai/ai-tools"

# Provider presets (mirrors config_builder.PROVIDERS)
_PROVIDERS = {
    "anthropic": {
        "name": "Anthropic",
        "base_url": "https://api.anthropic.com",
        "default_model": "claude-sonnet-4-5-20250929",
        "api_key_env": "ANTHROPIC_API_KEY",
    },
    "openai": {
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o",
        "api_key_env": "OPENAI_API_KEY",
    },
    "fabric": {
        "name": "FABRIC AI",
        "base_url": "https://ai.fabric-testbed.net/v1",
        "default_model": "qwen3-coder-30b",
        "api_key_env": "FABRIC_AI_API_KEY",
    },
    "nrp": {
        "name": "NRP (Nautilus)",
        "base_url": "https://ellm.nrp-nautilus.io/v1",
        "default_model": "qwen3-coder-30b",
        "api_key_env": "NRP_API_KEY",
    },
    "custom": {
        "name": "Custom Endpoint",
        "base_url": None,
        "default_model": "",
        "api_key_env": "CUSTOM_API_KEY",
    },
    "ollama": {
        "name": "Ollama",
        "base_url": None,
        "default_model": "qwen2.5-coder:7b",
        "api_key_env": None,
    },
}

# Active streaming clients tracked by request_id for cancellation
_active_clients = {}

# Cached agents (loaded once)
_agents_cache = None

# Cached skill prompts
_skills_cache = {}

# Max tool-calling rounds
_MAX_TOOL_ROUNDS = 50


# ── Env / config helpers ───────────────────────────────────────────

def _load_env_file():
    """Read LLM configuration from ~/.pegasus-ai/.env, falling back to os.environ."""
    env_path = os.path.join(os.environ.get("HOME", "/tmp"), ".pegasus-ai", ".env")
    env_vars = {}
    try:
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, _, value = line.partition("=")
                    env_vars[key.strip()] = value.strip()
    except FileNotFoundError:
        pass

    _ENV_KEYS = [
        "LLM_PROVIDER", "LLM_MODEL",
        "ANTHROPIC_API_KEY", "OPENAI_API_KEY",
        "FABRIC_AI_API_KEY", "NRP_API_KEY",
        "CUSTOM_BASE_URL", "CUSTOM_API_KEY",
        "OLLAMA_HOST",
    ]
    for key in _ENV_KEYS:
        if key not in env_vars and os.environ.get(key):
            env_vars[key] = os.environ[key]

    return env_vars


def _resolve_provider_config(env_vars):
    """Resolve provider, base_url, api_key, and model from env vars.

    Returns (provider, base_url, api_key, model) or raises ValueError.
    """
    provider = env_vars.get("LLM_PROVIDER", "")
    if not provider:
        raise ValueError("No LLM provider configured. Run LLM_Setup.ipynb first.")

    preset = _PROVIDERS.get(provider)
    if not preset:
        raise ValueError(f"Unknown provider: {provider}")

    # Resolve base URL
    if provider == "custom":
        base_url = env_vars.get("CUSTOM_BASE_URL", env_vars.get("OPENAI_API_BASE", ""))
    elif provider == "ollama":
        host = env_vars.get("OLLAMA_HOST", "http://host.docker.internal:11434")
        base_url = f"{host}/v1"
    else:
        base_url = preset["base_url"]

    # Resolve API key
    if provider == "ollama":
        api_key = "ollama"
    elif preset["api_key_env"]:
        api_key = env_vars.get(preset["api_key_env"], "")
    else:
        api_key = ""

    # Resolve model
    model = env_vars.get("LLM_MODEL", preset["default_model"])

    return provider, base_url, api_key, model


def _load_agents():
    """Load agent definitions from /opt/pegasus-ai/ai-tools/opencode/agents/*.md.

    Parses YAML frontmatter (name, description) and caches results.
    """
    global _agents_cache
    if _agents_cache is not None:
        return _agents_cache

    agents = {
        "general": {
            "name": "General",
            "description": "General-purpose Pegasus WMS workflow assistant",
            "prompt": "",
        }
    }

    agents_dir = os.path.join(_AI_TOOLS_SRC, "opencode", "agents")
    if os.path.isdir(agents_dir):
        for fname in sorted(os.listdir(agents_dir)):
            if not fname.endswith(".md"):
                continue
            agent_id = fname[:-3]  # e.g. "workflow-architect"
            fpath = os.path.join(agents_dir, fname)
            try:
                with open(fpath) as f:
                    content = f.read()
                # Parse YAML frontmatter
                name = agent_id.replace("-", " ").title()
                description = ""
                prompt = content
                fm_match = re.match(
                    r"^---\s*\n(.*?)\n---\s*\n(.*)$", content, re.DOTALL
                )
                if fm_match:
                    frontmatter = fm_match.group(1)
                    prompt = fm_match.group(2).strip()
                    for line in frontmatter.split("\n"):
                        if line.startswith("name:"):
                            name = line.split(":", 1)[1].strip()
                        elif line.startswith("description:"):
                            description = line.split(":", 1)[1].strip()
                agents[agent_id] = {
                    "name": name,
                    "description": description,
                    "prompt": prompt,
                }
            except Exception:
                pass

    _agents_cache = agents
    return agents


def _load_skill_prompt(skill_name):
    """Load a skill prompt from /opt/pegasus-ai/ai-tools/opencode/skills/<name>.md."""
    if skill_name in _skills_cache:
        return _skills_cache[skill_name]

    skill_path = os.path.join(_AI_TOOLS_SRC, "opencode", "skills", f"{skill_name}.md")
    if not os.path.isfile(skill_path):
        return None

    try:
        with open(skill_path) as f:
            content = f.read()
        # Strip YAML frontmatter
        fm_match = re.match(r"^---\s*\n.*?\n---\s*\n(.*)$", content, re.DOTALL)
        if fm_match:
            content = fm_match.group(1).strip()
        _skills_cache[skill_name] = content
        return content
    except Exception:
        return None


def _load_system_prompt(agent_id=None):
    """Build the system prompt from PEGASUS_AI.md + tool instructions + agent persona."""
    parts = []

    # Load shared context (PEGASUS_AI.md)
    shared_path = os.path.join(_AI_TOOLS_SRC, "shared", "PEGASUS_AI.md")
    if os.path.isfile(shared_path):
        try:
            with open(shared_path) as f:
                parts.append(f.read())
        except Exception:
            pass

    # Tool-use instructions
    parts.append(
        "\n\n## Tool Use Instructions\n\n"
        "You have access to tools for file operations, shell commands, and Pegasus WMS "
        "workflow management. Use them to help the user create, run, and debug workflows.\n\n"
        "WORKSPACE RULES:\n"
        "- All files MUST be created under ~/work/ (the ONLY persistent, visible directory)\n"
        "- NEVER create files in /tmp/ — they are invisible to the user\n"
        "- ALWAYS ask the user for the workflow name before creating files\n"
        "- Use kebab-case directory names (e.g., csv-summary-workflow/)\n\n"
        "When the user asks to create a workflow, use the tools to:\n"
        "1. create_directory for the project structure\n"
        "2. write_file for each source file\n"
        "3. Explain what was created\n\n"
        "When debugging, use run_command, check_workflow_status, and analyze_workflow "
        "to gather information before suggesting fixes."
    )

    # Agent persona
    if agent_id and agent_id != "general":
        agents = _load_agents()
        agent = agents.get(agent_id)
        if agent and agent.get("prompt"):
            parts.append(f"\n\n## Agent Persona\n\n{agent['prompt']}")

    return "\n".join(parts)


def _process_slash_command(message):
    """Check if message starts with a slash command and inject skill prompt.

    Returns (processed_message, skill_name_or_None).
    """
    if not message.startswith("/"):
        return message, None

    # Parse command and arguments
    parts = message.split(None, 1)
    command = parts[0][1:]  # strip leading /
    user_args = parts[1] if len(parts) > 1 else ""

    # Map slash commands to skill files
    skill_map = {
        "scaffold": "scaffold",
        "debug": "debug",
        "review": "review",
        "wrapper": "wrapper",
        "dockerfile": "dockerfile",
        "convert": "convert",
        "help": "help",
    }

    skill_name = skill_map.get(command)
    if not skill_name:
        return message, None

    prompt = _load_skill_prompt(skill_name)
    if not prompt:
        return message, None

    # Inject skill prompt before user's message
    processed = f"[Using /{command} skill]\n\n{prompt}\n\nUser request: {user_args}"
    return processed, skill_name


# ── LLM request helpers ────────────────────────────────────────────

async def _anthropic_request(client, base_url, api_key, model, messages,
                             system_prompt, stream=False):
    """Make a request to the Anthropic Messages API.

    Returns parsed response dict with unified format:
    {
        "content": str,           # text content (if no tool calls)
        "tool_calls": [           # tool calls (if any)
            {"id": str, "name": str, "arguments": dict}
        ],
        "stop_reason": str,
    }

    Or for streaming, returns an async iterator of SSE lines.
    """
    url = f"{base_url}/v1/messages"
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    body = {
        "model": model,
        "max_tokens": 8192,
        "system": system_prompt,
        "messages": messages,
        "tools": TOOL_DEFINITIONS_ANTHROPIC,
    }

    if stream:
        body["stream"] = True
        return await client.send(
            client.build_request("POST", url, json=body, headers=headers),
            stream=True,
        )

    resp = await client.post(url, json=body, headers=headers)
    resp.raise_for_status()
    data = resp.json()

    # Parse Anthropic response into unified format
    result = {"content": "", "tool_calls": [], "stop_reason": data.get("stop_reason", "")}

    for block in data.get("content", []):
        if block["type"] == "text":
            result["content"] += block["text"]
        elif block["type"] == "tool_use":
            result["tool_calls"].append({
                "id": block["id"],
                "name": block["name"],
                "arguments": block["input"],
            })

    return result


async def _openai_request(client, base_url, api_key, model, messages,
                          system_prompt, stream=False):
    """Make a request to an OpenAI-compatible chat completions API.

    Returns same unified format as _anthropic_request.
    """
    url = f"{base_url}/chat/completions"
    headers = {
        "content-type": "application/json",
    }
    if api_key:
        headers["authorization"] = f"Bearer {api_key}"

    # Prepend system message
    full_messages = [{"role": "system", "content": system_prompt}] + messages

    body = {
        "model": model,
        "messages": full_messages,
        "tools": TOOL_DEFINITIONS,
        "max_tokens": 8192,
    }

    if stream:
        body["stream"] = True
        return await client.send(
            client.build_request("POST", url, json=body, headers=headers),
            stream=True,
        )

    resp = await client.post(url, json=body, headers=headers)
    resp.raise_for_status()
    data = resp.json()

    choice = data["choices"][0]
    msg = choice["message"]
    result = {
        "content": msg.get("content", "") or "",
        "tool_calls": [],
        "stop_reason": choice.get("finish_reason", ""),
    }

    for tc in msg.get("tool_calls", []) or []:
        fn = tc.get("function", {})
        try:
            args = json.loads(fn.get("arguments", "{}"))
        except json.JSONDecodeError:
            args = {}
        result["tool_calls"].append({
            "id": tc.get("id", str(uuid.uuid4())),
            "name": fn.get("name", ""),
            "arguments": args,
        })

    return result


async def _stream_anthropic_response(client, base_url, api_key, model,
                                     messages, system_prompt):
    """Stream an Anthropic response and yield SSE data lines."""
    resp = await _anthropic_request(
        client, base_url, api_key, model, messages, system_prompt, stream=True
    )
    try:
        async for line in resp.aiter_lines():
            if not line.startswith("data: "):
                continue
            data_str = line[6:]
            if data_str == "[DONE]":
                break
            try:
                event = json.loads(data_str)
            except json.JSONDecodeError:
                continue

            etype = event.get("type", "")
            if etype == "content_block_delta":
                delta = event.get("delta", {})
                if delta.get("type") == "text_delta":
                    text = delta.get("text", "")
                    if text:
                        yield json.dumps({"content": text})
            elif etype == "message_stop":
                break
    finally:
        await resp.aclose()


async def _stream_openai_response(client, base_url, api_key, model,
                                  messages, system_prompt):
    """Stream an OpenAI-compatible response and yield SSE data lines."""
    resp = await _openai_request(
        client, base_url, api_key, model, messages, system_prompt, stream=True
    )
    try:
        async for line in resp.aiter_lines():
            if not line.startswith("data: "):
                continue
            data_str = line[6:]
            if data_str == "[DONE]":
                break
            try:
                event = json.loads(data_str)
            except json.JSONDecodeError:
                continue

            choices = event.get("choices", [])
            if not choices:
                continue
            delta = choices[0].get("delta", {})
            content = delta.get("content", "")
            if content:
                yield json.dumps({"content": content})
    finally:
        await resp.aclose()


# ── Tornado Handlers ───────────────────────────────────────────────

class ChatStreamHandler(JupyterHandler):
    """POST /api/pegasus-ai/chat/stream — SSE-streaming chat with tool calling."""

    def check_xsrf_cookie(self):
        pass

    async def post(self):
        self.set_header("Content-Type", "text/event-stream")
        self.set_header("Cache-Control", "no-cache")
        self.set_header("Connection", "keep-alive")
        self.set_header("X-Accel-Buffering", "no")

        try:
            body = json.loads(self.request.body)
        except (json.JSONDecodeError, TypeError):
            self._send_sse(json.dumps({"error": "Invalid JSON body"}))
            self._send_sse("[DONE]")
            return

        messages = body.get("messages", [])
        model_override = body.get("model", "")
        agent_id = body.get("agent", "general")
        request_id = body.get("request_id", str(uuid.uuid4()))

        if not messages:
            self._send_sse(json.dumps({"error": "No messages provided"}))
            self._send_sse("[DONE]")
            return

        # Process slash commands in the last user message
        last_msg = messages[-1]
        if last_msg.get("role") == "user" and isinstance(last_msg.get("content"), str):
            processed, skill = _process_slash_command(last_msg["content"])
            if skill:
                messages[-1] = {**last_msg, "content": processed}

        # Load LLM config
        env_vars = _load_env_file()
        try:
            provider, base_url, api_key, default_model = _resolve_provider_config(env_vars)
        except ValueError as e:
            self._send_sse(json.dumps({"error": str(e)}))
            self._send_sse("[DONE]")
            return

        model = model_override or default_model
        is_anthropic = provider == "anthropic"

        # Build system prompt
        system_prompt = _load_system_prompt(agent_id)

        # Create httpx client for this request
        client = httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=30.0))
        _active_clients[request_id] = client

        try:
            await self._chat_loop(
                client, is_anthropic, base_url, api_key, model,
                messages, system_prompt, request_id,
            )
        except httpx.HTTPStatusError as e:
            error_body = e.response.text[:500] if e.response else str(e)
            self._send_sse(json.dumps({
                "error": f"LLM API error ({e.response.status_code}): {error_body}"
            }))
        except Exception as e:
            self._send_sse(json.dumps({"error": f"Error: {e}"}))
        finally:
            _active_clients.pop(request_id, None)
            await client.aclose()
            self._send_sse("[DONE]")
            self.finish()

    async def _chat_loop(self, client, is_anthropic, base_url, api_key,
                         model, messages, system_prompt, request_id):
        """Tool-calling loop: up to _MAX_TOOL_ROUNDS rounds."""
        # Convert messages to provider format
        conv_messages = _convert_messages(messages, is_anthropic)

        for _ in range(_MAX_TOOL_ROUNDS):
            # Check if cancelled
            if request_id not in _active_clients:
                return

            # Non-streaming call to check for tool use
            if is_anthropic:
                result = await _anthropic_request(
                    client, base_url, api_key, model,
                    conv_messages, system_prompt,
                )
            else:
                result = await _openai_request(
                    client, base_url, api_key, model,
                    conv_messages, system_prompt,
                )

            tool_calls = result.get("tool_calls", [])

            if not tool_calls:
                # No tools — stream the final text response
                # First send any text from the non-streaming response
                text = result.get("content", "")
                if text:
                    self._send_sse(json.dumps({"content": text}))
                return

            # Has tool calls — execute them
            # Add assistant message with tool calls to conversation
            if is_anthropic:
                # Build Anthropic assistant content blocks
                assistant_content = []
                if result.get("content"):
                    assistant_content.append({
                        "type": "text",
                        "text": result["content"],
                    })
                    # Stream any prefatory text
                    self._send_sse(json.dumps({"content": result["content"]}))

                for tc in tool_calls:
                    assistant_content.append({
                        "type": "tool_use",
                        "id": tc["id"],
                        "name": tc["name"],
                        "input": tc["arguments"],
                    })

                conv_messages.append({
                    "role": "assistant",
                    "content": assistant_content,
                })

                # Execute tools and build tool result message
                tool_results = []
                for tc in tool_calls:
                    # Stream tool call event
                    self._send_sse(json.dumps({
                        "tool_call": {
                            "id": tc["id"],
                            "name": tc["name"],
                            "arguments": tc["arguments"],
                        }
                    }))

                    tool_result = await execute_tool(tc["name"], tc["arguments"])

                    # Stream tool result event
                    self._send_sse(json.dumps({
                        "tool_result": {
                            "id": tc["id"],
                            "name": tc["name"],
                            "result": tool_result[:2000],  # Truncate for SSE
                        }
                    }))

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tc["id"],
                        "content": tool_result,
                    })

                conv_messages.append({
                    "role": "user",
                    "content": tool_results,
                })

            else:
                # OpenAI format
                assistant_msg = {"role": "assistant", "content": result.get("content") or None}
                if result.get("content"):
                    self._send_sse(json.dumps({"content": result["content"]}))

                openai_tool_calls = []
                for tc in tool_calls:
                    openai_tool_calls.append({
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc["name"],
                            "arguments": json.dumps(tc["arguments"]),
                        },
                    })
                assistant_msg["tool_calls"] = openai_tool_calls
                conv_messages.append(assistant_msg)

                # Execute tools and add results
                for tc in tool_calls:
                    self._send_sse(json.dumps({
                        "tool_call": {
                            "id": tc["id"],
                            "name": tc["name"],
                            "arguments": tc["arguments"],
                        }
                    }))

                    tool_result = await execute_tool(tc["name"], tc["arguments"])

                    self._send_sse(json.dumps({
                        "tool_result": {
                            "id": tc["id"],
                            "name": tc["name"],
                            "result": tool_result[:2000],
                        }
                    }))

                    conv_messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": tool_result,
                    })

    def _send_sse(self, data):
        """Write a single SSE data line and flush."""
        try:
            self.write(f"data: {data}\n\n")
            self.flush()
        except Exception:
            pass


def _convert_messages(messages, is_anthropic):
    """Convert frontend messages to provider-specific format.

    Frontend sends: [{"role": "user"|"assistant", "content": "..."}]
    Anthropic expects the same basic format.
    OpenAI expects the same basic format (system is prepended separately).
    """
    converted = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role in ("user", "assistant"):
            converted.append({"role": role, "content": content})
    return converted


class StopHandler(JupyterHandler):
    """POST /api/pegasus-ai/chat/stop — Cancel an active streaming request."""

    def check_xsrf_cookie(self):
        pass

    async def post(self):
        try:
            body = json.loads(self.request.body)
        except (json.JSONDecodeError, TypeError):
            body = {}

        request_id = body.get("request_id", "")

        if request_id and request_id in _active_clients:
            client = _active_clients.pop(request_id)
            await client.aclose()
            self.finish(json.dumps({"status": "stopped", "request_id": request_id}))
        else:
            # Stop all active requests
            for rid, client in list(_active_clients.items()):
                try:
                    await client.aclose()
                except Exception:
                    pass
            _active_clients.clear()
            self.finish(json.dumps({"status": "stopped", "cleared": True}))


class AgentsHandler(JupyterHandler):
    """GET /api/pegasus-ai/agents — List available agent personas."""

    def get(self):
        agents = _load_agents()
        result = {}
        for aid, agent in agents.items():
            result[aid] = {
                "name": agent["name"],
                "description": agent["description"],
            }
        self.finish(json.dumps({"agents": result}))


class ModelsHandler(JupyterHandler):
    """GET /api/pegasus-ai/models — Fetch available models for the configured provider."""

    def get(self):
        env_vars = _load_env_file()
        provider = env_vars.get("LLM_PROVIDER", "")

        if not provider:
            self.finish(json.dumps({
                "models": [],
                "default": "",
                "provider": "",
            }))
            return

        preset = _PROVIDERS.get(provider)
        if not preset:
            self.finish(json.dumps({
                "models": [],
                "default": "",
                "provider": provider,
            }))
            return

        # For Anthropic: static model list (no /models endpoint)
        if provider == "anthropic":
            models = [
                "claude-sonnet-4-5-20250929",
                "claude-haiku-4-5-20251001",
            ]
        else:
            # Try to fetch models from OpenAI-compatible endpoint
            models = self._fetch_models_sync(provider, env_vars, preset)

        default_model = env_vars.get("LLM_MODEL", preset["default_model"])

        # If the resolved default isn't in the fetched model list, fall back
        # to the first available model.  This prevents 401 errors when the
        # API key doesn't grant access to the hardcoded preset default.
        if models and default_model not in models:
            default_model = models[0]

        self.finish(json.dumps({
            "models": models,
            "default": default_model,
            "provider": provider,
        }))

    def _fetch_models_sync(self, provider, env_vars, preset):
        """Synchronously fetch models from an OpenAI-compatible /models endpoint."""
        import urllib.error
        import urllib.request

        if provider == "custom":
            base_url = env_vars.get("CUSTOM_BASE_URL", env_vars.get("OPENAI_API_BASE", ""))
        elif provider == "ollama":
            host = env_vars.get("OLLAMA_HOST", "http://host.docker.internal:11434")
            base_url = f"{host}/v1"
        else:
            base_url = preset["base_url"]

        if not base_url:
            return [preset["default_model"]] if preset["default_model"] else []

        # Resolve API key
        if provider == "ollama":
            api_key = "ollama"
        elif preset["api_key_env"]:
            api_key = env_vars.get(preset["api_key_env"], "")
        else:
            api_key = ""

        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        try:
            import json as _json
            req = urllib.request.Request(
                f"{base_url.rstrip('/')}/models", headers=headers
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = _json.loads(resp.read().decode())
                model_ids = sorted(
                    m.get("id", "") for m in data.get("data", []) if m.get("id")
                )
                if model_ids:
                    return model_ids
        except Exception:
            pass

        return [preset["default_model"]] if preset["default_model"] else []


class PanelHandler(JupyterHandler):
    """Serve the PegasusAI chat panel HTML page."""

    def initialize(self, path):
        self._static_dir = path

    def get(self):
        index_path = os.path.join(self._static_dir, "index.html")
        self.set_header("Content-Type", "text/html; charset=UTF-8")
        with open(index_path) as f:
            self.finish(f.read())
