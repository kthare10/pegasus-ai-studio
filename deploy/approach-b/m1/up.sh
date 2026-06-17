#!/usr/bin/env bash
# Approach B — M1: shared HTCondor pool on one Docker host.
#
# Brings up a central manager (collector + negotiator + CCB + shared_port) and
# one execute node, both authenticating with IDTOKENS minted by the CM's pool
# signing key. This is the fast single-node loop to validate the CCB/token
# config before porting to Kubernetes (M2 adds the submit-only schedd-in-pod).
#
# Reuses the all-in-one studio image (Condor 25.x already installed, so the
# pool is version-matched with the Approach-B submit pod) by overriding its
# entrypoint to run condor_master directly in a CM/execute role.
#
# Usage:  IMAGE=pegasusai-studio:approach-b ./up.sh
# Exit:   condor_status lists the execute node; tokens/ holds submit.token (M2).

set -euo pipefail

IMAGE="${IMAGE:-pegasusai-studio:approach-b}"
NET="${NET:-condorpool}"
HERE="$(cd "$(dirname "$0")" && pwd)"
CONF="$(cd "${HERE}/../condor" && pwd)"
TOKENS="${HERE}/tokens"
mkdir -p "${TOKENS}"

echo "[m1] image=${IMAGE} net=${NET}"

docker rm -f cm execute >/dev/null 2>&1 || true
docker network create "${NET}" >/dev/null 2>&1 || true

# --- Central manager ---------------------------------------------------------
# Create the pool signing key inside the container, then run the daemons.
echo "[m1] starting central manager (cm)..."
docker run -d --name cm --hostname cm --network "${NET}" \
  -v "${CONF}/central-manager.local:/etc/condor/condor_config.local:ro" \
  --entrypoint /bin/bash "${IMAGE}" -c '
    set -e
    mkdir -p /etc/condor/passwords.d
    if [ ! -s /etc/condor/passwords.d/POOL ]; then
      head -c 32 /dev/urandom | base64 > /etc/condor/passwords.d/POOL
    fi
    # The DEB condor_master drops privilege to the "condor" user, so the daemons
    # read the pool signing key as condor. It must therefore be condor-owned
    # (mode 600); token minting is also done as condor (see below). A root-owned
    # key is unreadable by the daemons -> "DC_AUTHENTICATE: Unable to reconcile".
    chown -R condor:condor /etc/condor/passwords.d
    chmod 700 /etc/condor/passwords.d
    chmod 600 /etc/condor/passwords.d/POOL
    exec /usr/sbin/condor_master -f
  ' >/dev/null

echo "[m1] waiting for collector..."
for i in $(seq 1 30); do
  if docker exec cm bash -lc 'condor_status -collector >/dev/null 2>&1'; then break; fi
  sleep 2
done

# --- Mint IDTOKENs (signed by the CM pool key) -------------------------------
echo "[m1] minting IDTOKENs (as the condor user, which owns the signing key)..."
docker exec cm runuser -u condor -- condor_token_create -identity execute@pool \
    -authz ADVERTISE_STARTD -authz READ -authz WRITE -authz DAEMON > "${TOKENS}/execute.token"
docker exec cm runuser -u condor -- condor_token_create -identity submit@pool \
    -authz ADVERTISE_SCHEDD -authz READ -authz WRITE -authz DAEMON > "${TOKENS}/submit.token"
echo "[m1] tokens written to ${TOKENS}/ (submit.token is for M2)"

# --- Execute node ------------------------------------------------------------
echo "[m1] starting execute node..."
docker run -d --name execute --hostname execute --network "${NET}" \
  -v "${CONF}/execute.local:/etc/condor/condor_config.local:ro" \
  -v "${TOKENS}/execute.token:/tmp/pool.token:ro" \
  --entrypoint /bin/bash "${IMAGE}" -c '
    set -e
    mkdir -p /etc/condor/tokens.d
    cp /tmp/pool.token /etc/condor/tokens.d/pool.token
    chown condor:condor /etc/condor/tokens.d/pool.token
    chmod 600 /etc/condor/tokens.d/pool.token
    exec /usr/sbin/condor_master -f
  ' >/dev/null

echo "[m1] waiting for the execute node to register..."
for i in $(seq 1 30); do
  if docker exec cm bash -lc 'condor_status -startd 2>/dev/null | grep -q execute'; then break; fi
  sleep 2
done

echo "[m1] === condor_status (from the central manager) ==="
docker exec cm bash -lc 'condor_status' || true
echo "[m1] done."
