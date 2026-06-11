#!/usr/bin/env python3
"""First-login onboarding broker for PegasusAI Studio (Approach A).

Runs as root on 127.0.0.1:9095. nginx routes any *authenticated* request whose
CILogon identity has no unix account yet (the per-user backend maps default
here). The broker derives a username from the email, runs add-user.sh
--email (account, ports, units, map entries, nginx reload), then redirects the
client back to its original URL — which now resolves to the user's own
backend. A flock serializes concurrent first requests from the same browser.
"""

import fcntl
import pwd
import re
import socket
import subprocess
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

CONF_DIR = "/etc/pegasus-studio"
IDENTITY_MAP = f"{CONF_DIR}/identity.map"
ADD_USER = "/opt/pegasus-studio/bin/add-user.sh"
LOCK_FILE = "/run/studio-broker.lock"

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")


def user_port(username: str) -> int | None:
    try:
        with open(f"{CONF_DIR}/users/{username}.env") as f:
            for line in f:
                if line.startswith("STUDIO_PORT="):
                    return int(line.split("=", 1)[1])
    except (OSError, ValueError):
        pass
    return None


def port_open(port: int) -> bool:
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def ensure_started(username: str) -> bool:
    """Start the user's session units if stopped (wake-on-demand after the
    reaper, or after a host reboot). Returns True once the API answers."""
    started = False
    for unit in (f"studio-api@{username}", f"jupyter@{username}"):
        active = subprocess.run(
            ["systemctl", "is-active", "--quiet", unit], check=False
        )
        if active.returncode != 0:
            subprocess.run(["systemctl", "start", unit], check=False, timeout=60)
            started = True
    port = user_port(username)
    if port is None:
        return False
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if port_open(port):
            return True
        time.sleep(0.5)
    log(f"wake timeout: {username} port {port} never opened (started={started})")
    return False


def log(msg: str) -> None:
    print(msg, flush=True)


def read_identity_map() -> dict[str, str]:
    mapping = {}
    try:
        with open(IDENTITY_MAP) as f:
            for line in f:
                parts = line.strip().rstrip(";").split()
                if len(parts) == 2:
                    mapping[parts[0].lower()] = parts[1]
    except FileNotFoundError:
        pass
    return mapping


def derive_username(email: str) -> str:
    """Email localpart -> valid unix name (^[a-z][a-z0-9_-]{0,31}$), uniquified."""
    base = re.sub(r"[^a-z0-9_-]", "-", email.split("@")[0].lower()).strip("-")
    if not base or not base[0].isalpha():
        base = "u-" + base
    base = base[:28]
    taken = set(read_identity_map().values())
    name = base
    n = 1
    while True:
        exists = name in taken
        try:
            pwd.getpwnam(name)
            exists = True
        except KeyError:
            pass
        if not exists:
            return name
        n += 1
        name = f"{base}-{n}"


class Handler(BaseHTTPRequestHandler):
    server_version = "studio-broker"

    def do_GET(self) -> None:  # noqa: N802 — http.server API
        self.handle_onboard()

    def do_POST(self) -> None:  # noqa: N802
        self.handle_onboard()

    def handle_onboard(self) -> None:
        email = (self.headers.get("X-Auth-User") or "").strip().lower()
        target = self.headers.get("X-Original-URI") or "/"
        if not EMAIL_RE.match(email):
            self.send_error(400, "missing or invalid X-Auth-User")
            return

        with open(LOCK_FILE, "w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            mapping = read_identity_map()
            if email in mapping:
                # Known identity but the request landed here: either the
                # user's units are stopped (reaped / host reboot) or nginx's
                # maps are stale. Wake first; reload covers the rest.
                username = mapping[email]
                log(f"wake: {email} -> {username}")
                if not ensure_started(username):
                    self.send_error(503, "workspace failed to start")
                    return
                subprocess.run(["systemctl", "reload", "nginx"], check=False)
            else:
                username = derive_username(email)
                log(f"provisioning: {email} -> {username}")
                result = subprocess.run(
                    [ADD_USER, "--email", email, username],
                    capture_output=True, text=True, timeout=120,
                )
                if result.returncode != 0:
                    log(f"FAILED: {result.stdout}\n{result.stderr}")
                    self.send_error(500, "workspace provisioning failed")
                    return
                log(f"provisioned: {email} -> {username}")

        self.send_response(302)
        self.send_header("Location", target)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

    def log_message(self, fmt: str, *args) -> None:  # quiet default access log
        pass


if __name__ == "__main__":
    addr = ("127.0.0.1", 9095)
    log(f"studio-broker listening on {addr[0]}:{addr[1]}")
    try:
        ThreadingHTTPServer(addr, Handler).serve_forever()
    except KeyboardInterrupt:
        sys.exit(0)
