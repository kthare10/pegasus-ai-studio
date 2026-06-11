#!/usr/bin/env bash
# Switch the studio gateway from basic auth to CILogon (vouch-proxy) with
# automatic first-login user provisioning.
#
# Prerequisites:
#   1. A CILogon OIDC client registered with callback https://<dns-name>/auth
#   2. /etc/pegasus-studio/vouch/config.yaml filled in (see
#      vouch/config.yaml.example — only client_id/client_secret are manual)
#
# Usage: sudo ./enable-cilogon.sh <dns-name>     e.g. 23.134.232.66.sslip.io
# Rollback: sudo ./enable-cilogon.sh --rollback
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
    echo "Run as root (sudo $0 <dns-name>)" >&2
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONF_DIR=/etc/pegasus-studio
VOUCH_CFG="$CONF_DIR/vouch/config.yaml"

if [ "${1:-}" = "--rollback" ]; then
    ln -sf /etc/nginx/sites-available/studio.conf /etc/nginx/sites-enabled/studio.conf
    nginx -t && systemctl reload nginx
    systemctl stop vouch studio-broker 2>/dev/null || true
    echo "Rolled back to basic auth."
    exit 0
fi

DNS_NAME="${1:?usage: $0 <dns-name>}"

[ -f "$VOUCH_CFG" ] || {
    echo "ERROR: $VOUCH_CFG not found. Copy vouch/config.yaml.example there" >&2
    echo "       and fill in the CILogon client id/secret." >&2
    exit 1
}
# Only non-comment lines count — the template's own comments mention the
# placeholder names.
if grep -v '^\s*#' "$VOUCH_CFG" | grep -q "REPLACE_WITH_CILOGON"; then
    echo "ERROR: $VOUCH_CFG still has REPLACE_WITH_CILOGON_* placeholders." >&2
    exit 1
fi
chmod 600 "$VOUCH_CFG"

# Auto-fill the JWT secret and DNS name placeholders
if grep -q "REPLACE_WITH_RANDOM" "$VOUCH_CFG"; then
    sed -i "s|REPLACE_WITH_RANDOM_44CHAR_BASE64|$(openssl rand -base64 33)|" "$VOUCH_CFG"
fi
sed -i "s|REPLACE_DNS_NAME|$DNS_NAME|g" "$VOUCH_CFG"

echo "==> Broker + add-user.sh + reaper -> /opt/pegasus-studio/bin"
install -d /opt/pegasus-studio/bin
install -m 755 "$SCRIPT_DIR/broker/studio-broker.py" /opt/pegasus-studio/bin/
install -m 755 "$SCRIPT_DIR/add-user.sh" /opt/pegasus-studio/bin/
install -m 755 "$SCRIPT_DIR/reaper/studio-reaper.sh" /opt/pegasus-studio/bin/

echo "==> Landing page -> /opt/pegasus-studio/landing"
install -d /opt/pegasus-studio/landing
install -m 644 "$SCRIPT_DIR/landing/index.html" /opt/pegasus-studio/landing/

# Older configs: add the session-lifetime cap if missing (minutes)
if ! grep -q "maxAge" "$VOUCH_CFG"; then
    sed -i "/^    jwt:/a\\
        maxAge: 480" "$VOUCH_CFG"
fi

# Older configs (pre-logout): add the post_logout whitelist if missing
if ! grep -q "post_logout_redirect_uris" "$VOUCH_CFG"; then
    sed -i "/^    port: 9090/a\\
\\
    post_logout_redirect_uris:\\
        - https://$DNS_NAME/welcome\\
        - https://cilogon.org/logout" "$VOUCH_CFG"
fi

echo "==> Services"
cp "$SCRIPT_DIR/systemd/vouch.service" /etc/systemd/system/
cp "$SCRIPT_DIR/systemd/studio-broker.service" /etc/systemd/system/
cp "$SCRIPT_DIR/systemd/studio-reaper.service" /etc/systemd/system/
cp "$SCRIPT_DIR/systemd/studio-reaper.timer" /etc/systemd/system/
systemctl daemon-reload
systemctl enable vouch studio-broker >/dev/null 2>&1
systemctl enable --now studio-reaper.timer >/dev/null 2>&1
systemctl restart vouch studio-broker   # restart picks up config changes on re-runs
sleep 3
systemctl is-active --quiet vouch || {
    echo "ERROR: vouch failed to start — journalctl -u vouch" >&2
    exit 1
}

echo "==> nginx cutover"
touch "$CONF_DIR/identity.map"
cp "$SCRIPT_DIR/nginx/studio-logformat.conf" /etc/nginx/conf.d/studio-logformat.conf
cp "$SCRIPT_DIR/nginx/studio-cilogon.conf" /etc/nginx/sites-available/studio-cilogon.conf
# Use the Let's Encrypt cert when present
if [ -d "/etc/letsencrypt/live/$DNS_NAME" ]; then
    sed -i \
        -e "s|ssl_certificate .*|ssl_certificate     /etc/letsencrypt/live/$DNS_NAME/fullchain.pem;|" \
        -e "s|ssl_certificate_key .*|ssl_certificate_key /etc/letsencrypt/live/$DNS_NAME/privkey.pem;|" \
        /etc/nginx/sites-available/studio-cilogon.conf
fi
ln -sf /etc/nginx/sites-available/studio-cilogon.conf /etc/nginx/sites-enabled/studio.conf
nginx -t && systemctl reload nginx

echo
echo "CILogon auth is live: https://$DNS_NAME/"
echo "First login auto-creates the user's workspace (username from email)."
echo "Rollback to basic auth: sudo $0 --rollback"
