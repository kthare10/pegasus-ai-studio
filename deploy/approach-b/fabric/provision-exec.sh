#!/usr/bin/env bash
# Configure an HTCondor execute node (startd) that reports to the shared central
# manager via CCB. Run on each condor-exec* node AFTER provision-common.sh, with
# the execute.token minted by provision-cm.sh.
#
# Usage: ./provision-exec.sh <cm-pool-ip> <path-to-execute.token>
#   e.g. ./provision-exec.sh 10.10.0.20 ./execute.token
set -euo pipefail

CM_IP="${1:?usage: provision-exec.sh <cm-pool-ip> <execute.token>}"
TOKEN="${2:?usage: provision-exec.sh <cm-pool-ip> <execute.token>}"
HERE="$(cd "$(dirname "$0")" && pwd)"

sed "s/@CONDOR_HOST@/${CM_IP}/g" "${HERE}/condor/50-execute.conf.tmpl" \
  | sudo tee /etc/condor/config.d/50-execute.conf >/dev/null

# Install the pool IDTOKEN (root-owned 600; the systemd master reads it as root).
sudo install -d -m 700 /etc/condor/tokens.d
sudo cp "${TOKEN}" /etc/condor/tokens.d/pool.token
sudo chmod 600 /etc/condor/tokens.d/pool.token

sudo systemctl enable --now condor
sudo systemctl restart condor

echo "[exec] waiting to register with ${CM_IP}..."
for _ in $(seq 1 30); do
  condor_status -startd 2>/dev/null | grep -q . && break; sleep 2
done
echo "[exec] === condor_status (pool view) ==="
condor_status || true
