# Approach A: Shared Submit Host (multi-user prototype)

Deploys PegasusAI Studio for multiple users on a **single submit host** that is
already part of an HTCondor pool (e.g. `pegasus-submit-sage-submit`: CM + schedd
+ remote workers). Multi-tenancy comes from Unix accounts: **one `studio-api`
instance per user, running as that user** — no privilege-dropping layer, no
sudo allowlist. Everything in studio-api derives from `$HOME`
(workspace `~/work`, SQLite `~/work/.studio/studio.db`, npm prefix
`~/.npm-global`, PTYs, `pegasus-plan`, `workflow-monitor`), so the backend runs
**unmodified**.

```
                 browser (HTTPS, basic auth, user = unix account)
                              │
                  nginx :443 ── TLS + htpasswd  (:80 redirects)
                    │ map $remote_user → backend port
   ┌────────────────┼──────────────────────────────────┐
   /  → studio-web  │ /api,/ws → 127.0.0.1:910N        │
   (ONE shared      │   studio-api@alice  (User=alice) │
    Next.js :3000)  │   studio-api@bob    (User=bob)   │
                    │   ...                            │
                    └───────────────┬──────────────────┘
                                    │ spawns as the user
                 pegasus-plan · workflow-monitor · PTYs · AI tools
                                    │
                 shared condor_schedd (UNCHANGED — Owner=alice/bob
                 is automatic because the submitting process IS the user)
                                    │
                 shared pool workers (UCSD-gpu-worker-*, …)
```

**Condor and Pegasus on the host are not touched.** The schedd already exists;
per-user job ownership falls out of process identity.

## Files

| File | Purpose |
|------|---------|
| `provision.sh` | One-time host setup (root): Node 20, nginx, rootless podman (docker shim), JupyterLab venv, workflow-monitor, api/web/knowledge deploy, units, TLS (Let's Encrypt or self-signed) |
| `add-user.sh` | Provision one studio user: account, subuids + lingering (podman), ports, htpasswd, units, nginx map entries |
| `systemd/studio-api@.service` | Template unit — per-user backend (`studio-api@alice`) |
| `systemd/jupyter@.service` | Template unit — per-user JupyterLab (`jupyter@alice`) |
| `systemd/studio-web.service` | Shared Next.js frontend (`:3000`) |
| `nginx/studio.conf` | TLS gateway with basic auth and per-user `$remote_user → port` maps for `/api`, `/ws`, `/jupyter` |

## Runbook

Prerequisites on the submit host: Ubuntu 24.04, **Pegasus + HTCondor already
configured** (schedd on this host, workers in the pool), sudo access, and —
for a real TLS certificate — **ports 80 and 443 open** to the internet.

```bash
# 1. Get the repo onto the host (git clone or rsync from your machine)
git clone <this-repo> && cd pegasus-ai-studio

# 2. Provision (Node 20, nginx, podman, JupyterLab, workflow-monitor, units).
#    STUDIO_DNS_NAME enables a real Let's Encrypt cert; with no DNS name of
#    your own, sslip.io gives you one derived from the public IP for free:
sudo STUDIO_DNS_NAME=$(curl -4 -s ifconfig.me).sslip.io \
     STUDIO_CERT_EMAIL=you@example.org \
     deploy/approach-a/provision.sh
#    (omit STUDIO_DNS_NAME to fall back to a self-signed cert)

# 3. Create users (password prompt, or pass it as the 2nd argument)
sudo deploy/approach-a/add-user.sh alice
sudo deploy/approach-a/add-user.sh bob
```

Open `https://<dns-name>/`, log in as `alice` — Workflows/Workbench/Chat/
Terminal/Notebooks all act as the `alice` Unix account. Log in as `bob` in
another browser profile and confirm complete separation (workflows, files,
LLM keys, AI tools).

No public access? An SSH tunnel works without exposing anything:
`ssh -L 8443:localhost:443 <host>` → `https://localhost:8443`.

### TLS and DNS

- With `STUDIO_DNS_NAME` set, provision.sh issues a Let's Encrypt cert via
  the webroot challenge (**port 80 must be reachable from the internet** —
  issuance *and* renewals), points nginx at it, and installs a renewal
  reload hook. Renewals are automatic (certbot's systemd timer).
- The host's public IP changed (new slice/VM)? Re-run provision.sh with the
  new `STUDIO_DNS_NAME` — everything else is idempotent.
- IPv6-only host: Let's Encrypt validates over AAAA; sslip.io supports v6
  names (`2610-1e0--1.sslip.io` style), but make sure port 80 is open on
  the v6 path. Prefer the IPv4 name when both exist.
- CILogon later: register the OIDC client with callback
  `https://<dns-name>/auth` — a real cert (not self-signed) is required.

### Exposing the host publicly

- Open **only 22, 80, and 443** in the firewall/security group. Do **not**
  expose Condor ports (9618 etc.) or the per-user backend ports (9101+,
  bound to 127.0.0.1 anyway) — the workers reach the CM over the existing
  private paths, and nothing about this deployment changes that.
- `add-user.sh` sets only the **studio** (htpasswd) password — accounts get no
  Unix password, so the new users cannot SSH in. Keep it that way (key-based
  SSH only).

### Smoke tests

```bash
# per-user API up?
sudo systemctl status studio-api@alice
curl -k -u alice https://localhost/api/health

# job ownership: submit a workflow from alice's UI, then
condor_q                       # → "Total for alice: ..." (Owner = alice)

# cross-user isolation
sudo -u bob ls /home/alice     # → Permission denied (homes are 0750)
```

## CILogon + automatic user creation

Federated login with first-visit auto-provisioning (no admin step per user):
nginx `auth_request` → vouch-proxy → CILogon. The authenticated email maps to
a unix account via `/etc/pegasus-studio/identity.map`; identities with no
account yet are routed to a small **onboarding broker** (`:9095`, root) that
derives a username from the email, runs `add-user.sh --email`, and redirects
back — the user lands in their freshly created workspace.

```bash
# 1. Register a CILogon OIDC client (https://cilogon.org/oauth2/register)
#    callback: https://<dns-name>/auth   scopes: openid email profile

# 2. Put the secrets in place (this file is never committed):
sudo mkdir -p /etc/pegasus-studio/vouch
sudo cp deploy/approach-a/vouch/config.yaml.example /etc/pegasus-studio/vouch/config.yaml
sudo vi /etc/pegasus-studio/vouch/config.yaml   # paste client_id + client_secret

# 3. Cut over (starts vouch + broker, swaps the nginx site):
sudo deploy/approach-a/enable-cilogon.sh <dns-name>

# Rollback to basic auth at any time:
sudo deploy/approach-a/enable-cilogon.sh --rollback
```

Pre-mapping a specific identity to a chosen username (instead of the
auto-derived one): `sudo add-user.sh --email alice@example.org alice`.

## Phase 2 leftovers

- **Workflow-aware idle stop**: stop `studio-api@user`/`jupyter@user` when idle
  **and** `condor_q -submitter user` is empty (units are cheap, so this is an
  optimization, not a need).
- **Fair-share**: per-user Condor accounting groups; per-user systemd
  `MemoryMax`/`CPUQuota` are already in the template unit.

## Caveats

- Users get real shells (web PTY + AI tools are arbitrary command execution by
  design). Treat the host accordingly: 0750 homes, no shared secrets on disk,
  quotas on `/home`.
- LLM API keys are per-user (each user's SQLite DB) — set in their Settings page.
- Workflow jobs that use containers need Apptainer **on the workers**, not just
  the submit host (workers without it won't match container jobs).
- Users can `docker build/run/push` via rootless podman (the `docker` command
  is the podman shim); image layers land in each user's
  `~/.local/share/containers`, so size `/home` accordingly. Workers pull
  workflow images from a registry — built images must be **pushed** to be
  usable in workflows (`docker://...` in the transformation catalog).
- Without `STUDIO_DNS_NAME` the cert is self-signed (browser warning
  expected). Move to vouch/CILogon for real federated users.
