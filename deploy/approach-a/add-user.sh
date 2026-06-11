#!/usr/bin/env bash
# Provision one PegasusAI Studio user on the shared submit host.
# Creates the Unix account, assigns a backend port, sets the login password
# (htpasswd), starts studio-api@<user>, and adds the nginx route.
#
# Usage: sudo ./add-user.sh <username> [password]
#   With no password argument, htpasswd prompts interactively.
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
    echo "Run as root (sudo $0 <username> [password])" >&2
    exit 1
fi
USERNAME="${1:?usage: $0 <username> [password]}"
PASSWORD="${2:-}"
if ! [[ "$USERNAME" =~ ^[a-z][a-z0-9_-]{0,31}$ ]]; then
    echo "Invalid username: $USERNAME" >&2
    exit 1
fi

CONF_DIR=/etc/pegasus-studio
MAP_FILE="$CONF_DIR/nginx-users.map"
BASE_PORT=9100

echo "==> Unix account"
if ! id "$USERNAME" &>/dev/null; then
    useradd -m -s /bin/bash "$USERNAME"
fi
chmod 750 "/home/$USERNAME"

# Subordinate UID/GID ranges for rootless podman. Derive a non-overlapping
# 65536-wide range from the uid (uid 1000 -> 100000, 1001 -> 165536, ...).
if ! grep -q "^$USERNAME:" /etc/subuid; then
    UID_NUM=$(id -u "$USERNAME")
    SUB_START=$(( 100000 + (UID_NUM - 1000) * 65536 ))
    usermod --add-subuids "$SUB_START-$(( SUB_START + 65535 ))" \
            --add-subgids "$SUB_START-$(( SUB_START + 65535 ))" "$USERNAME"
fi
# Lingering gives the user a /run/user/<uid> runtime dir without a login
# session, which rootless podman needs when run from the studio terminals.
loginctl enable-linger "$USERNAME"

echo "==> Backend port"
if [ -f "$CONF_DIR/users/$USERNAME.env" ]; then
    PORT=$(grep -oP '(?<=STUDIO_PORT=)\d+' "$CONF_DIR/users/$USERNAME.env")
else
    # `|| true`: an empty map file (first user) must not trip pipefail
    LAST=$(grep -ohE '127\.0\.0\.1:[0-9]+' "$MAP_FILE" | cut -d: -f2 | sort -n | tail -1 || true)
    PORT=$(( ${LAST:-$BASE_PORT} + 1 ))
    echo "STUDIO_PORT=$PORT" > "$CONF_DIR/users/$USERNAME.env"
fi
echo "    $USERNAME -> 127.0.0.1:$PORT"

# JupyterLab port rides 100 above the API port
JUPYTER_PORT=$(( PORT + 100 ))
if ! grep -q STUDIO_JUPYTER_PORT "$CONF_DIR/users/$USERNAME.env"; then
    echo "STUDIO_JUPYTER_PORT=$JUPYTER_PORT" >> "$CONF_DIR/users/$USERNAME.env"
fi

echo "==> Studio login password (basic auth)"
if [ -n "$PASSWORD" ]; then
    htpasswd -B -b "$CONF_DIR/htpasswd" "$USERNAME" "$PASSWORD"
else
    htpasswd -B "$CONF_DIR/htpasswd" "$USERNAME"
fi

echo "==> nginx routes"
if ! grep -q "^$USERNAME " "$MAP_FILE"; then
    echo "$USERNAME 127.0.0.1:$PORT;" >> "$MAP_FILE"
fi
if ! grep -q "^$USERNAME " "$CONF_DIR/nginx-jupyter.map"; then
    echo "$USERNAME 127.0.0.1:$JUPYTER_PORT;" >> "$CONF_DIR/nginx-jupyter.map"
fi
nginx -t && systemctl reload nginx

echo "==> jupyter@$USERNAME"
systemctl enable --now "jupyter@$USERNAME"

echo "==> studio-api@$USERNAME"
systemctl enable --now "studio-api@$USERNAME"
sleep 2
systemctl is-active --quiet "studio-api@$USERNAME" \
    && echo "    running" \
    || { echo "    FAILED — journalctl -u studio-api@$USERNAME" >&2; exit 1; }

echo
echo "Done. Log in at https://<host>/ as '$USERNAME'."
