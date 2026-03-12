"""PegasusAI tool definitions and execution.

Provides 11 tools for file operations, shell commands, and Pegasus WMS
workflow lifecycle management.  All file operations are confined to the
workspace root (~/work/).
"""

import asyncio
import glob as _glob
import json
import os
import shutil

WORKSPACE_ROOT = os.path.join(os.environ.get("HOME", "/home/jovyan"), "work")

# Maximum sizes for safety
_MAX_READ_BYTES = 100 * 1024  # 100 KB
_MAX_OUTPUT_BYTES = 8 * 1024  # 8 KB
_CMD_TIMEOUT = 300  # 5 minutes


def _safe_path(path):
    """Resolve path and verify it's inside WORKSPACE_ROOT.

    Returns the resolved absolute path or raises ValueError.
    """
    if not path:
        raise ValueError("Path is required.")
    # Expand ~ and resolve to absolute
    resolved = os.path.realpath(os.path.expanduser(path))
    root = os.path.realpath(WORKSPACE_ROOT)
    if not resolved.startswith(root + os.sep) and resolved != root:
        raise ValueError(
            f"Access denied: path must be inside {WORKSPACE_ROOT}"
        )
    return resolved


# ── Tool definitions (OpenAI function-calling format) ──────────────

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to a file in the workspace. Creates parent directories as needed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path relative to ~/work/ or absolute path inside ~/work/",
                    },
                    "content": {
                        "type": "string",
                        "description": "Content to write to the file",
                    },
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file from the workspace (max 100KB).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path relative to ~/work/ or absolute path inside ~/work/",
                    },
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "List files and directories in the workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Directory path relative to ~/work/ or absolute. Defaults to ~/work/.",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_directory",
            "description": "Create a directory (and parents) in the workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Directory path relative to ~/work/ or absolute path inside ~/work/",
                    },
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_path",
            "description": "Delete a file or directory from the workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to delete, relative to ~/work/ or absolute path inside ~/work/",
                    },
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Execute a shell command in the workspace (5 min timeout, 8KB output limit).",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Shell command to execute",
                    },
                    "cwd": {
                        "type": "string",
                        "description": "Working directory (default: ~/work/)",
                    },
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_workflow",
            "description": "Run workflow_generator.py in a workflow directory to produce the Pegasus DAG.",
            "parameters": {
                "type": "object",
                "properties": {
                    "workflow_dir": {
                        "type": "string",
                        "description": "Path to the workflow directory containing workflow_generator.py",
                    },
                    "args": {
                        "type": "string",
                        "description": "Additional arguments to pass to workflow_generator.py",
                    },
                },
                "required": ["workflow_dir"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "submit_workflow",
            "description": "Submit a Pegasus workflow using pegasus-plan --submit.",
            "parameters": {
                "type": "object",
                "properties": {
                    "workflow_dir": {
                        "type": "string",
                        "description": "Path to the workflow directory",
                    },
                    "site": {
                        "type": "string",
                        "description": "Execution site (e.g., 'condorpool', 'local')",
                    },
                    "output": {
                        "type": "string",
                        "description": "Output site (default: 'local')",
                    },
                },
                "required": ["workflow_dir"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_workflow_status",
            "description": "Check the status of a running Pegasus workflow.",
            "parameters": {
                "type": "object",
                "properties": {
                    "run_dir": {
                        "type": "string",
                        "description": "Path to the Pegasus run directory",
                    },
                },
                "required": ["run_dir"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_workflow",
            "description": "Analyze a completed or failed Pegasus workflow using pegasus-analyzer.",
            "parameters": {
                "type": "object",
                "properties": {
                    "run_dir": {
                        "type": "string",
                        "description": "Path to the Pegasus run directory",
                    },
                },
                "required": ["run_dir"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_workflows",
            "description": "List workflow directories found in the workspace.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
]

# Anthropic tool format (converted from OpenAI format)
TOOL_DEFINITIONS_ANTHROPIC = []
for _t in TOOL_DEFINITIONS:
    _fn = _t["function"]
    TOOL_DEFINITIONS_ANTHROPIC.append({
        "name": _fn["name"],
        "description": _fn["description"],
        "input_schema": _fn["parameters"],
    })


def _resolve_path(path):
    """Resolve a user-provided path to an absolute path inside workspace."""
    if not path:
        return WORKSPACE_ROOT
    path = path.strip()
    if not os.path.isabs(path):
        path = os.path.join(WORKSPACE_ROOT, path)
    return _safe_path(path)


async def _run_subprocess(cmd, cwd=None, timeout=_CMD_TIMEOUT):
    """Run a command asynchronously and return (stdout, stderr, returncode)."""
    cwd = cwd or WORKSPACE_ROOT
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=timeout
        )
        out = stdout.decode("utf-8", errors="replace")[:_MAX_OUTPUT_BYTES]
        err = stderr.decode("utf-8", errors="replace")[:_MAX_OUTPUT_BYTES]
        return out, err, proc.returncode
    except asyncio.TimeoutError:
        try:
            proc.kill()
        except Exception:
            pass
        return "", "Command timed out", -1
    except FileNotFoundError as e:
        return "", f"Command not found: {e}", -1


async def _run_shell(command, cwd=None, timeout=_CMD_TIMEOUT):
    """Run a shell command string asynchronously."""
    cwd = cwd or WORKSPACE_ROOT
    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=timeout
        )
        out = stdout.decode("utf-8", errors="replace")[:_MAX_OUTPUT_BYTES]
        err = stderr.decode("utf-8", errors="replace")[:_MAX_OUTPUT_BYTES]
        return out, err, proc.returncode
    except asyncio.TimeoutError:
        try:
            proc.kill()
        except Exception:
            pass
        return "", "Command timed out", -1


async def execute_tool(name, arguments):
    """Execute a tool by name with the given arguments dict.

    Returns a string result suitable for sending back to the LLM.
    """
    try:
        if name == "write_file":
            path = _resolve_path(arguments["path"])
            content = arguments["content"]
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as f:
                f.write(content)
            return f"Wrote {len(content)} bytes to {path}"

        elif name == "read_file":
            path = _resolve_path(arguments["path"])
            with open(path, "r") as f:
                content = f.read(_MAX_READ_BYTES)
            return content

        elif name == "list_directory":
            path = _resolve_path(arguments.get("path", ""))
            entries = sorted(os.listdir(path))
            result = []
            for entry in entries:
                full = os.path.join(path, entry)
                kind = "dir" if os.path.isdir(full) else "file"
                size = os.path.getsize(full) if os.path.isfile(full) else ""
                result.append(f"{kind}\t{entry}\t{size}")
            return "\n".join(result) if result else "(empty directory)"

        elif name == "create_directory":
            path = _resolve_path(arguments["path"])
            os.makedirs(path, exist_ok=True)
            return f"Created directory: {path}"

        elif name == "delete_path":
            path = _resolve_path(arguments["path"])
            if os.path.isdir(path):
                shutil.rmtree(path)
                return f"Deleted directory: {path}"
            elif os.path.isfile(path):
                os.remove(path)
                return f"Deleted file: {path}"
            else:
                return f"Path not found: {path}"

        elif name == "run_command":
            command = arguments["command"]
            cwd = arguments.get("cwd")
            if cwd:
                cwd = _resolve_path(cwd)
            out, err, rc = await _run_shell(command, cwd=cwd)
            parts = []
            if out:
                parts.append(f"stdout:\n{out}")
            if err:
                parts.append(f"stderr:\n{err}")
            parts.append(f"exit code: {rc}")
            return "\n".join(parts)

        elif name == "generate_workflow":
            wf_dir = _resolve_path(arguments["workflow_dir"])
            gen = os.path.join(wf_dir, "workflow_generator.py")
            if not os.path.isfile(gen):
                return f"workflow_generator.py not found in {wf_dir}"
            cmd = ["python3", gen]
            extra_args = arguments.get("args", "")
            if extra_args:
                cmd.extend(extra_args.split())
            out, err, rc = await _run_subprocess(cmd, cwd=wf_dir)
            parts = []
            if out:
                parts.append(out)
            if err:
                parts.append(f"stderr: {err}")
            parts.append(f"exit code: {rc}")
            return "\n".join(parts)

        elif name == "submit_workflow":
            wf_dir = _resolve_path(arguments["workflow_dir"])
            site = arguments.get("site", "condorpool")
            output = arguments.get("output", "local")
            # Find workflow YAML/DAX in directory
            wf_file = None
            for ext in ("*.yml", "*.yaml", "*.dax"):
                matches = _glob.glob(os.path.join(wf_dir, ext))
                if matches:
                    wf_file = matches[0]
                    break
            if not wf_file:
                return f"No workflow file (.yml/.yaml/.dax) found in {wf_dir}"
            cmd = [
                "pegasus-plan", "--submit",
                "-s", site,
                "-o", output,
                wf_file,
            ]
            out, err, rc = await _run_subprocess(cmd, cwd=wf_dir)
            parts = []
            if out:
                parts.append(out)
            if err:
                parts.append(f"stderr: {err}")
            parts.append(f"exit code: {rc}")
            return "\n".join(parts)

        elif name == "check_workflow_status":
            run_dir = _resolve_path(arguments["run_dir"])
            cmd = ["pegasus-status", run_dir]
            out, err, rc = await _run_subprocess(cmd)
            return out + (f"\nstderr: {err}" if err else "")

        elif name == "analyze_workflow":
            run_dir = _resolve_path(arguments["run_dir"])
            cmd = ["pegasus-analyzer", run_dir]
            out, err, rc = await _run_subprocess(cmd)
            return out + (f"\nstderr: {err}" if err else "")

        elif name == "list_workflows":
            entries = sorted(os.listdir(WORKSPACE_ROOT))
            workflows = []
            for entry in entries:
                full = os.path.join(WORKSPACE_ROOT, entry)
                if os.path.isdir(full) and entry.endswith("-workflow"):
                    # Check for workflow_generator.py
                    has_gen = os.path.isfile(
                        os.path.join(full, "workflow_generator.py")
                    )
                    workflows.append(f"{entry}  {'(has generator)' if has_gen else ''}")
            if not workflows:
                return "No workflow directories found in ~/work/"
            return "\n".join(workflows)

        else:
            return f"Unknown tool: {name}"

    except ValueError as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Error executing {name}: {e}"
