"""OpenCode Web Extension — Jupyter server extension.

Provides API endpoints for managing the OpenCode web subprocess and
serves a self-contained HTML panel with sidebar + embedded iframe.
"""

import os

from jupyter_server.utils import url_path_join

from .handlers import (
    ModelsHandler,
    OpenCodePanelHandler,
    StartHandler,
    StatusHandler,
    StopHandler,
)

# The named proxy path used by jupyter-server-proxy for this entry point.
# All sub-paths (e.g. /opencode/assets/...) are proxied to OpenCode.
PROXY_PATH = "/opencode/"


def _jupyter_server_extension_points():
    """Register this module as a Jupyter server extension."""
    return [{"module": "opencode_extension"}]


def _load_jupyter_server_extension(server_app):
    """Register Tornado handlers and add a JupyterLab launcher entry."""
    web_app = server_app.web_app
    base_url = web_app.settings["base_url"]

    # Static files directory for the panel HTML
    static_dir = os.path.join(os.path.dirname(__file__), "static")

    handlers = [
        (url_path_join(base_url, "api/opencode-web/start"), StartHandler),
        (url_path_join(base_url, "api/opencode-web/stop"), StopHandler),
        (url_path_join(base_url, "api/opencode-web/status"), StatusHandler),
        (url_path_join(base_url, "api/opencode-web/models"), ModelsHandler),
        (
            url_path_join(base_url, "opencode-panel/?"),
            OpenCodePanelHandler,
            {"path": static_dir},
        ),
    ]
    web_app.add_handlers(".*$", handlers)

    server_app.log.info("OpenCode Web Extension loaded — /opencode-panel/")


# jupyter-server-proxy entry point — provides the launcher icon.
# The iframe connects directly to OpenCode's port (bypassing proxy)
# because OpenCode's web UI uses absolute asset paths that break
# behind prefix-based proxies.
# The actual OpenCode process is managed by StartHandler/StopHandler.
def setup_opencode_proxy():
    """Entry point for jupyter-server-proxy."""
    return {
        "command": [],
        "port": 9198,
        "timeout": 0,
        "launcher_entry": {
            "enabled": True,
            "title": "OpenCode",
            "path_info": "opencode-panel/",
        },
        "new_browser_tab": True,
        "absolute_url": False,
    }
