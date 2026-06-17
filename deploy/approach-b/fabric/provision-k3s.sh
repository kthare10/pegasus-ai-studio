#!/usr/bin/env bash
# Install k3s for the Approach-B Studio control plane (M2+). Run on studio-cp as
# the server; on optional workers run with role=agent and the server URL+token.
#
# Server:  ./provision-k3s.sh server
# Agent:   ./provision-k3s.sh agent https://10.10.0.10:6443 <node-token>
#
# The per-user submit pods (the :approach-b image in submit mode) and JupyterHub
# run on this cluster. Pull the image from a registry (see README) so k3s nodes
# can fetch it.
set -euo pipefail

ROLE="${1:-server}"

if [ "$ROLE" = "server" ]; then
  # --node-ip pins k3s to the pool network; --tls-san lets the public IP serve the API/UI.
  POOL_IP="$(ip -4 -o addr show | awk '/10\.10\.0\./{print $4}' | cut -d/ -f1 | head -1)"
  curl -sfL https://get.k3s.io | sudo sh -s - server \
    --node-ip "${POOL_IP:-}" --write-kubeconfig-mode 644
  echo "[k3s] server up. Worker join token:"
  sudo cat /var/lib/rancher/k3s/server/node-token
  echo "[k3s] kubeconfig: /etc/rancher/k3s/k3s.yaml"
elif [ "$ROLE" = "agent" ]; then
  SERVER_URL="${2:?usage: provision-k3s.sh agent <server-url> <token>}"
  TOKEN="${3:?usage: provision-k3s.sh agent <server-url> <token>}"
  curl -sfL https://get.k3s.io | \
    sudo K3S_URL="${SERVER_URL}" K3S_TOKEN="${TOKEN}" sh -
  echo "[k3s] agent joined ${SERVER_URL}"
else
  echo "usage: provision-k3s.sh server | agent <server-url> <token>" >&2
  exit 1
fi
