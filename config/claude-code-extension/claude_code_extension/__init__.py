"""Claude Code Extension — Jupyter server extension.

Provides a launcher card and landing panel for Claude Code CLI.
Checks API key status and guides users to open a terminal session.
"""

import os

from jupyter_server.utils import url_path_join

from .handlers import ClaudeCodePanelHandler, StatusHandler


def _jupyter_server_extension_points():
    """Register this module as a Jupyter server extension."""
    return [{"module": "claude_code_extension"}]


def _load_jupyter_server_extension(server_app):
    """Register Tornado handlers for the Claude Code extension."""
    web_app = server_app.web_app
    base_url = web_app.settings["base_url"]

    static_dir = os.path.join(os.path.dirname(__file__), "static")

    handlers = [
        (url_path_join(base_url, "api/claude-code/status"), StatusHandler),
        (
            url_path_join(base_url, "claude-code-panel/?"),
            ClaudeCodePanelHandler,
            {"path": static_dir},
        ),
    ]
    web_app.add_handlers(".*$", handlers)

    server_app.log.info("Claude Code Extension loaded — /claude-code-panel/")


def setup_claude_code_proxy():
    """Entry point for jupyter-server-proxy — provides the launcher icon."""
    return {
        "command": [],
        "port": 0,
        "timeout": 0,
        "launcher_entry": {
            "enabled": True,
            "title": "Claude Code",
            "path_info": "claude-code-panel/",
        },
        "new_browser_tab": True,
        "absolute_url": False,
    }
