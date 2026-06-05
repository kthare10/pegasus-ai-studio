# CILogon Authentication for PegasusAI Studio

Puts CILogon (OIDC) login in front of the whole studio using **Vouch Proxy** +
an **nginx `auth_request`** front proxy — the *sidecar* pattern. The studio
container is never published directly; all traffic goes through the
authenticating proxy.

```
Browser ──TLS──▶ proxy (nginx :443)
   ├─ /login /logout /auth /validate ──▶ vouch (:9090) ──▶ CILogon
   └─ everything else: auth_request /validate (valid session?) ──▶ studio (:80)
```

Mode: **authenticate-only** — any successful CILogon login is allowed in
(no role restriction). Role-gating can be layered on later (see the
`add-vouch-proxy` skill for the FABRIC Core API role-check variant).

## One-time setup

### 1. Register a CILogon OIDC client
At <https://cilogon.org/oauth2/register>:
- **Callback/redirect URI** must match `oauth.callback_url` exactly.
  - Local: `https://localhost:8443/auth`
  - Prod:  `https://YOUR_HOST/auth`
- Scopes: `openid`, `email`, `profile`, `org.cilogon.userinfo`
- You'll receive a **client_id** and **client_secret** (registration may need approval).

### 2. Fill the Vouch config
```bash
cp auth/vouch/config.yaml.example auth/vouch/config.yaml
openssl rand -base64 33          # paste as vouch.jwt.secret
# then set client_id, client_secret, and callback_url in auth/vouch/config.yaml
```

### 3. TLS certificate (CILogon requires HTTPS)
```bash
./auth/ssl/generate-self-signed.sh            # local/dev (browser will warn)
# or drop real certs as auth/ssl/fullchain.pem + auth/ssl/privkey.pem
```

### 4. Run
```bash
docker compose -f docker-compose.auth.yml up -d
# open https://localhost:8443  → redirected to CILogon → back into the studio
docker compose -f docker-compose.auth.yml logs -f proxy vouch
docker compose -f docker-compose.auth.yml down
```

(Plain unauthenticated run: `docker compose up -d` — the default
`docker-compose.yml` — or `make run`.)

`auth/vouch/config.yaml` and `auth/ssl/*.pem` are git-ignored (secrets/keys).

## Verify
- `curl -k -I https://localhost:8443/` → `302` to `/login`
- Log in via CILogon → studio loads (dashboard, workflows, notebooks-in-tab, chat)
- `https://localhost:8443/logout` clears the session

## Notes / gotchas
- **`publicAccess: false`** in the vouch config is mandatory — `true` lets
  unauthenticated users through.
- **Cookie domain is required** (with `allowAllUsers`): vouch refuses to start
  unless `vouch.cookie.domain` covers the `callback_url` host. The example uses
  `cookie.domain: localhost`; for a real host set it to that host or its parent
  domain. (Note: vouch requires *exactly one* of `allowAllUsers` or `domains`.)
- WebSockets (Jupyter kernels/terminals, studio `/ws`) and SSE (`/api`) pass
  through the proxy — the `Upgrade`/`Connection` headers and `proxy_buffering off`
  in `nginx/default.conf` handle that.
- Plain unauthenticated dev still works via `make run` (bypasses this proxy).

## Eventual GKE migration
This sidecar maps almost 1:1 to GKE:
- **studio** → Deployment + ClusterIP Service (unchanged image).
- **vouch** → Deployment + ClusterIP Service; config via ConfigMap, secrets via
  a Kubernetes Secret.
- **proxy** → replace with **ingress-nginx** using the external-auth annotations
  instead of a hand-written `auth_request` block:
  ```yaml
  nginx.ingress.kubernetes.io/auth-url: "http://vouch.NAMESPACE.svc.cluster.local:9090/validate"
  nginx.ingress.kubernetes.io/auth-signin: "https://$host/login?url=$escaped_request_uri"
  ```
  Add a separate Ingress (or path rules) routing `/login /logout /auth` to the
  vouch Service. TLS via cert-manager. The vouch config and CILogon client are
  identical — only `callback_url`/cookie domain change to the GKE hostname.
