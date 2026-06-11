# JupyterLab config for per-user jupyter@<user> units (Approach A).
#
# Adapted from docker/jupyter/jupyter_server_config.py. Auth (token/password)
# is disabled because the server binds to 127.0.0.1 only and is fronted by the
# nginx gateway (TLS + auth + per-user routing).

import os

c = get_config()  # noqa: F821 — Jupyter config magic

c.ServerApp.ip = "127.0.0.1"
c.ServerApp.port = int(os.environ["STUDIO_JUPYTER_PORT"])
c.ServerApp.base_url = "/jupyter/"
c.ServerApp.token = ""
c.ServerApp.password = ""
c.ServerApp.open_browser = False
c.ServerApp.root_dir = os.path.expanduser("~/work")

# The gateway forwards the public hostname in Host; without this Jupyter
# rejects any non-local Host header with a bare 403.
c.ServerApp.allow_remote_access = True

# Behind the auth proxy the usual XSRF dance adds failure modes without
# adding protection (the gateway authenticates every request).
c.ServerApp.disable_check_xsrf = True

c.ServerApp.terminals_enabled = True
c.TerminalManager.shell_command = ["/bin/bash"]

# Keep websocket_ping_timeout <= websocket_ping_interval (see container config).
c.ServerApp.tornado_settings = {
    "websocket_ping_interval": 30000,
    "websocket_ping_timeout": 30000,
}
