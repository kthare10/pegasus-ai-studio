#!/usr/bin/env bash
# Generate a self-signed TLS cert for the auth proxy (local/dev use).
# For production, drop real certs here as fullchain.pem / privkey.pem instead.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CN="${1:-localhost}"

openssl req -x509 -newkey rsa:2048 -nodes \
    -keyout "${DIR}/privkey.pem" \
    -out "${DIR}/fullchain.pem" \
    -days 825 \
    -subj "/CN=${CN}" \
    -addext "subjectAltName=DNS:${CN},DNS:localhost,IP:127.0.0.1"

chmod 600 "${DIR}/privkey.pem"
echo "[ssl] wrote ${DIR}/fullchain.pem and ${DIR}/privkey.pem (CN=${CN})"
echo "[ssl] self-signed — browsers will warn; click through for local testing."
