"""PegasusAI Extension — Jupyter server extension.

Provides a chat-based workflow assistant for Pegasus WMS with SSE streaming,
tool calling, and agent personas.  Serves a self-contained HTML chat panel.
"""

import os

from jupyter_server.utils import url_path_join

from .handlers import (
    AgentsHandler,
    ChatStreamHandler,
    ModelsHandler,
    PanelHandler,
    StopHandler,
)


def _jupyter_server_extension_points():
    """Register this module as a Jupyter server extension."""
    return [{"module": "pegasus_ai_extension"}]


def _load_jupyter_server_extension(server_app):
    """Register Tornado handlers for the PegasusAI chat extension."""
    web_app = server_app.web_app
    base_url = web_app.settings["base_url"]

    static_dir = os.path.join(os.path.dirname(__file__), "static")

    handlers = [
        (url_path_join(base_url, "api/pegasus-ai/chat/stream"), ChatStreamHandler),
        (url_path_join(base_url, "api/pegasus-ai/chat/stop"), StopHandler),
        (url_path_join(base_url, "api/pegasus-ai/agents"), AgentsHandler),
        (url_path_join(base_url, "api/pegasus-ai/models"), ModelsHandler),
        (
            url_path_join(base_url, "pegasus-ai-panel/?"),
            PanelHandler,
            {"path": static_dir},
        ),
    ]
    web_app.add_handlers(".*$", handlers)

    server_app.log.info("PegasusAI Extension loaded — /pegasus-ai-panel/")


def setup_pegasus_ai_proxy():
    """Entry point for jupyter-server-proxy — provides the launcher icon."""
    return {
        "command": [],
        "port": 0,
        "timeout": 0,
        "launcher_entry": {
            "enabled": True,
            "title": "PegasusAI",
            "path_info": "pegasus-ai-panel/",
        },
        "new_browser_tab": True,
        "absolute_url": False,
    }
