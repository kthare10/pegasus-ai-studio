#!/usr/bin/env bash
# One-time host setup for Approach A (shared submit host, multi-user studio).
# Run as root from anywhere inside the repo checkout, on a host that already
# has Pegasus + HTCondor (schedd) configured. Idempotent.
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
    echo "Run as root (sudo $0)" >&2
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
INSTALL_DIR=/opt/pegasus-studio
CONF_DIR=/etc/pegasus-studio

# Optional: public DNS name for a real Let's Encrypt certificate.
# No DNS? Use sslip.io, which encodes the public IP in the hostname:
#   sudo STUDIO_DNS_NAME=$(curl -4 -s ifconfig.me).sslip.io ./provision.sh
# Requires port 80 reachable from the internet (issuance + renewals).
# Unset -> self-signed certificate.
STUDIO_DNS_NAME="${STUDIO_DNS_NAME:-}"
STUDIO_CERT_EMAIL="${STUDIO_CERT_EMAIL:-}"   # optional, for LE expiry notices

echo "==> Sanity checks (Pegasus + Condor must already be present)"
pegasus-version
condor_version | head -1

echo "==> System packages"
# Tolerate unrelated broken third-party repos (e.g. stale GPG keys)
apt-get update -q || echo "WARNING: apt-get update reported errors; continuing with available repos"
apt-get install -y -q nginx apache2-utils python3-venv python3-pip rsync curl

echo "==> Podman (rootless containers; docker CLI shim)"
apt-get install -y -q podman podman-docker uidmap slirp4netns
touch /etc/containers/nodocker   # silence the "emulating docker" banner

if ! command -v npm >/dev/null || [ "$(node --version | cut -dv -f2 | cut -d. -f1)" -lt 20 ]; then
    echo "==> Node.js 20 (NodeSource)"
    install -d /etc/apt/keyrings
    curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key \
        | gpg --dearmor --yes -o /etc/apt/keyrings/nodesource.gpg
    echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_20.x nodistro main" \
        > /etc/apt/sources.list.d/nodesource.list
    apt-get update -q || true
    apt-get install -y -q nodejs
fi

echo "==> studio-api -> $INSTALL_DIR/api (shared read-only code; per-user state lives in \$HOME)"
mkdir -p "$INSTALL_DIR"
rsync -a --delete --exclude .venv --exclude __pycache__ --exclude tests \
    "$REPO_DIR/studio-api/" "$INSTALL_DIR/api/"
python3 -m venv "$INSTALL_DIR/api/.venv"
"$INSTALL_DIR/api/.venv/bin/pip" install -q --upgrade pip
"$INSTALL_DIR/api/.venv/bin/pip" install -q -r "$INSTALL_DIR/api/requirements.txt"
# users execute the shared venv + code, never write to it
chmod -R a+rX "$INSTALL_DIR/api"

echo "==> studio-web build (Next.js standalone)"
cd "$REPO_DIR/studio-web"
# Telemetry must be off: its exit-time flush can hang `next build` forever on
# hosts with restricted/odd egress (observed on FABRIC slices).
export NEXT_TELEMETRY_DISABLED=1
npm ci
npm run build
mkdir -p "$INSTALL_DIR/web"
rsync -a --delete .next/standalone/ "$INSTALL_DIR/web/"
rsync -a .next/static/ "$INSTALL_DIR/web/.next/static/"
rsync -a public/ "$INSTALL_DIR/web/public/"
id studio-web &>/dev/null || useradd -r -s /usr/sbin/nologin -d /nonexistent studio-web
chown -R studio-web:studio-web "$INSTALL_DIR/web"
# Running under sudo leaves root-owned build artifacts (.next, node_modules)
# in the checkout, which breaks later rebuilds as the normal user — hand back.
if [ -n "${SUDO_USER:-}" ]; then
    chown -R "$SUDO_USER:$SUDO_USER" "$REPO_DIR/studio-web"
fi

echo "==> JupyterLab (shared venv; per-user jupyter@<user> units)"
if [ ! -x "$INSTALL_DIR/jupyter/.venv/bin/jupyter-lab" ]; then
    python3 -m venv "$INSTALL_DIR/jupyter/.venv"
    "$INSTALL_DIR/jupyter/.venv/bin/pip" install -q --upgrade pip
    "$INSTALL_DIR/jupyter/.venv/bin/pip" install -q jupyterlab
fi
chmod -R a+rX "$INSTALL_DIR/jupyter"

echo "==> workflow-monitor (drives the dashboard's run/job views via JSONL)"
# Not on PyPI; install from GitHub
WFMON_SRC="git+https://github.com/pegasus-isi/workflow-monitor.git"
python3 -m venv "$INSTALL_DIR/wfmon/.venv" 2>/dev/null || true
"$INSTALL_DIR/wfmon/.venv/bin/pip" install -q --upgrade pip
"$INSTALL_DIR/wfmon/.venv/bin/pip" install -q "$WFMON_SRC"
ln -sf "$INSTALL_DIR/wfmon/.venv/bin/workflow-monitor" /usr/local/bin/workflow-monitor

echo "==> Knowledge store -> /opt/pegasus-ai/knowledge"
mkdir -p /opt/pegasus-ai
rsync -a --delete "$REPO_DIR/knowledge/" /opt/pegasus-ai/knowledge/
chmod -R a+rX /opt/pegasus-ai/knowledge

echo "==> Config dirs"
mkdir -p "$CONF_DIR/users"
cp "$SCRIPT_DIR/jupyter/jupyter_server_config.py" "$CONF_DIR/jupyter_server_config.py"
touch "$CONF_DIR/nginx-users.map" "$CONF_DIR/nginx-jupyter.map" "$CONF_DIR/htpasswd"
chown www-data:www-data "$CONF_DIR/htpasswd"
chmod 640 "$CONF_DIR/htpasswd"

echo "==> TLS certificate (self-signed; replace with certbot once a DNS name exists)"
if [ ! -f "$CONF_DIR/ssl/fullchain.pem" ]; then
    mkdir -p "$CONF_DIR/ssl"
    openssl req -x509 -newkey rsa:2048 -nodes -days 365 \
        -keyout "$CONF_DIR/ssl/privkey.pem" \
        -out "$CONF_DIR/ssl/fullchain.pem" \
        -subj "/CN=$(hostname -f)"
    chmod 600 "$CONF_DIR/ssl/privkey.pem"
fi

echo "==> systemd units"
cp "$SCRIPT_DIR/systemd/studio-api@.service" /etc/systemd/system/
cp "$SCRIPT_DIR/systemd/studio-web.service" /etc/systemd/system/
cp "$SCRIPT_DIR/systemd/jupyter@.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now studio-web

echo "==> nginx"
cp "$SCRIPT_DIR/nginx/studio.conf" /etc/nginx/sites-available/studio.conf
ln -sf /etc/nginx/sites-available/studio.conf /etc/nginx/sites-enabled/studio.conf
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl reload nginx

if [ -n "$STUDIO_DNS_NAME" ]; then
    echo "==> Let's Encrypt certificate for $STUDIO_DNS_NAME"
    apt-get install -y -q certbot
    mkdir -p /var/www/letsencrypt
    EMAIL_ARGS="--register-unsafely-without-email"
    [ -n "$STUDIO_CERT_EMAIL" ] && EMAIL_ARGS="-m $STUDIO_CERT_EMAIL --no-eff-email"
    if certbot certonly --webroot -w /var/www/letsencrypt -d "$STUDIO_DNS_NAME" \
            --agree-tos -n $EMAIL_ARGS; then
        sed -i \
            -e "s|ssl_certificate .*|ssl_certificate     /etc/letsencrypt/live/$STUDIO_DNS_NAME/fullchain.pem;|" \
            -e "s|ssl_certificate_key .*|ssl_certificate_key /etc/letsencrypt/live/$STUDIO_DNS_NAME/privkey.pem;|" \
            /etc/nginx/sites-available/studio.conf
        install -d /etc/letsencrypt/renewal-hooks/deploy
        printf '#!/bin/sh\nsystemctl reload nginx\n' \
            > /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh
        chmod +x /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh
        nginx -t && systemctl reload nginx
    else
        echo "WARNING: Let's Encrypt issuance failed (is port 80 reachable from the"
        echo "         internet?). Keeping the self-signed certificate."
    fi
fi

echo
echo "Done. Next: sudo $SCRIPT_DIR/add-user.sh <username>"
echo "      then open https://${STUDIO_DNS_NAME:-<host>}/"
