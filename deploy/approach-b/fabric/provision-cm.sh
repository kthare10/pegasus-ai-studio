#!/usr/bin/env bash
# Configure the HTCondor central manager (collector + negotiator + CCB +
# shared_port), create the pool signing key, and mint IDTOKENs for the execute
# nodes and submit pods. Run on condor-cm AFTER provision-common.sh.
#
# Usage: ./provision-cm.sh <cm-pool-ip>     e.g. ./provision-cm.sh 10.10.0.20
set -euo pipefail

CM_IP="${1:?usage: provision-cm.sh <cm-pool-ip>}"
HERE="$(cd "$(dirname "$0")" && pwd)"

# --- pool-identity config (loads after the DEB recommended-security template) ---
sed "s/@CONDOR_HOST@/${CM_IP}/g" "${HERE}/condor/50-central-manager.conf.tmpl" \
  | sudo tee /etc/condor/config.d/50-central-manager.conf >/dev/null

# --- pool signing key (root:root 600; the systemd master reads it as root) ---
# This is SEC_TOKEN_POOL_SIGNING_KEY_FILE — condor_token_create signs IDTOKENs
# with it and the daemons verify with it. Root ownership is the conventional,
# secure form for /etc/condor/passwords.d and is read fine because condor runs
# under a root-started master (unlike the bare-container `condor_master -f`).
if ! sudo test -s /etc/condor/passwords.d/POOL; then
  sudo install -d -m 700 /etc/condor/passwords.d
  openssl rand -base64 32 | sudo tee /etc/condor/passwords.d/POOL >/dev/null
  sudo chmod 600 /etc/condor/passwords.d/POOL
fi

sudo systemctl enable --now condor
sudo systemctl restart condor
echo "[cm] waiting for collector..."
for _ in $(seq 1 30); do condor_status -collector >/dev/null 2>&1 && break; sleep 2; done

# --- mint IDTOKENs ---
mkdir -p "${HERE}/tokens"
sudo condor_token_create -identity execute@pool \
  -authz ADVERTISE_STARTD -authz READ -authz WRITE -authz DAEMON > "${HERE}/tokens/execute.token"
sudo condor_token_create -identity submit@pool \
  -authz ADVERTISE_SCHEDD -authz READ -authz WRITE -authz DAEMON > "${HERE}/tokens/submit.token"

echo "[cm] tokens written under ${HERE}/tokens/:"
echo "       execute.token -> copy to each condor-exec node, then run provision-exec.sh"
echo "       submit.token  -> mount into the submit pod at \$HOME/.condor/tokens.d/ (M2)"
echo "[cm] === condor_status -collector ==="
condor_status -collector || true
