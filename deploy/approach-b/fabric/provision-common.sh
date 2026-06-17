#!/usr/bin/env bash
# Install HTCondor 25.x (matches the :approach-b pod image) on a FABRIC
# Ubuntu 24.04 (noble) node. Run on every condor-cm / condor-exec* node.
#
# Installs via the DEB packages + systemd, so condor_master runs as root and
# privilege-switches to read credentials — avoiding the read_secure_file()
# problems hit when running `condor_master -f` directly in a container.
set -euo pipefail

. /etc/os-release
if [ "${VERSION_CODENAME:-}" != "noble" ]; then
  echo "[provision] warning: expected Ubuntu noble (24.04), got '${VERSION_CODENAME:-?}'" >&2
fi

sudo install -d /etc/apt/keyrings
curl -fsSL https://htcss-downloads.chtc.wisc.edu/repo/keys/HTCondor-25.x-Key \
  | sudo tee /etc/apt/keyrings/htcondor.asc >/dev/null
curl -fsSL https://htcss-downloads.chtc.wisc.edu/repo/ubuntu/htcondor-25.x-noble.list \
  | sudo tee /etc/apt/sources.list.d/htcondor.list >/dev/null

sudo apt-get update
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends condor

# Don't start with the default personal-pool config; the role drop-in
# (provision-cm.sh / provision-exec.sh) configures and (re)starts condor.
sudo systemctl stop condor 2>/dev/null || true
echo "[provision] HTCondor $(condor_version | head -1) installed."
