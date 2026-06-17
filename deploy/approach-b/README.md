# Approach B — Per-User Workspace Pods (prototype)

See `pegasus-ai-studio-design/Approach_B_Prototype_Plan.md` for the full plan
and milestones (M0–M6). This directory holds the Approach-B deployment assets as
they land, milestone by milestone.

## M0 — `:approach-b` image (DONE)

The Approach-A all-in-one image already bundles every in-pod component
(JupyterLab + Pegasus + HTCondor + studio-api + studio-web + nginx, supervised
by s6). M0 makes **HTCondor runtime-selectable** so the *same image* can run
either as a personal pool (Approach A) or as a submit-only schedd reporting to a
shared central manager (Approach B). The in-pod nginx already fronts everything
on a single port (`:80`), which is exactly what a hub proxy needs.

### What changed

- `docker/condor/condor_config.submit.local` — new submit-only config:
  `DAEMON_LIST = MASTER, SCHEDD, SHARED_PORT`, `CCB_ADDRESS`, IDTOKENS auth,
  state on the PVC (`$HOME/.condor`). Driven by env `STUDIO_CONDOR_HOST`.
- `Dockerfile` — ships both configs as named templates
  (`condor_config.personal.local`, `condor_config.submit.local`); default
  `STUDIO_CONDOR_MODE=personal` keeps the Approach-A image identical.
- `docker/s6-overlay/s6-rc.d/condor/run` — activates the right config at boot,
  prepares state dirs, and (submit mode) checks for a pool IDTOKEN.

### Build

```sh
# from repo root — HTCondor ships amd64 DEBs only, so build for linux/amd64
docker buildx build --platform linux/amd64 -t kthare10/pegasusai-studio:approach-b --load .
```

### Run

Personal pool (Approach A — unchanged default):

```sh
docker run --rm -p 8080:80 kthare10/pegasusai-studio:approach-b
# → http://localhost:8080  (Studio web, /api, /jupyter all on one port)
```

Submit-only (Approach B — needs a reachable central manager + a pool token):

```sh
docker run --rm -p 8080:80 \
  -e STUDIO_CONDOR_MODE=submit \
  -e STUDIO_CONDOR_HOST=central-manager.example.org:9618 \
  -v "$PWD/pvc-home:/home/pegasus" \
  kthare10/pegasusai-studio:approach-b
# drop the IDTOKEN at  pvc-home/.condor/tokens.d/pool.token  before/at start
```

### M0 exit criterion

`docker run` the image: nginx serves Studio web, `/api`, and `/jupyter` on the
single exposed port. In personal mode a local pool comes up (`condor_status`).
In submit mode the schedd starts and (once M1's central manager exists) will
register with it — that end-to-end check is **M2**.

## M1 — shared HTCondor pool (IN PROGRESS)

Single-host loop on a Docker host (alpha-5) to nail the CCB/IDTOKEN config before
porting to Kubernetes. `deploy/approach-b/condor/{central-manager,execute}.local`
+ `m1/up.sh` bring up a central manager (collector+negotiator+CCB+shared_port)
and an execute node, both reusing the `:approach-b` image.

Status: CM and execute containers start; the CM mints IDTOKENs; shared_port +
TCP collector updates + shared `TRUST_DOMAIN` (`pegasus-studio-pool`) configured;
PASSWORD method added to the template's method list with a shared pool secret
copied to both nodes. Progress through several real fixes (signing-key ownership,
not overriding `use security:recommended`, shared TRUST_DOMAIN, full method list).

**Current blocker (precise):** the execute startd still doesn't register. With
PASSWORD enabled, the startd now attempts every method (SCITOKENS, KERBEROS,
IDTOKENS, PASSWORD, FS) and all fail with:
`getTokenSigningKey(): read_secure_file(/etc/condor/passwords.d/POOL) failed!`
The file is `condor:condor 0600` in a `condor:condor 0700` dir and the `condor`
user CAN `cat` it, but HTCondor's stricter `read_secure_file()` rejects it. Root
cause hypothesis: the daemons run **as `condor`** (not root with privilege
switching) in this `--entrypoint bash -c 'condor_master -f'` setup
(`ps` shows `condor condor_master`, `CONDOR_IDS` undefined), so the credential
isn't considered "secure" by the daemon's check.

Most promising next steps (need an HTCondor reference, not more trial-and-error):
1. Create the pool credential with **`condor_store_cred -c add`** (the canonical
   path), which writes it in the exact secure form/ownership the daemons expect,
   rather than raw `/dev/urandom` bytes.
2. Ensure the **master runs as root** (so it privilege-switches to read
   root-owned creds) — likely by starting condor via the image's s6 `condor`
   service instead of bare `condor_master -f`, or setting `CONDOR_IDS`.
3. Then revisit per-pod **IDTOKENS** (the earlier blank-issuer issue) for
   per-user pool identity.

The CCB/shared-port/TCP-update wiring is done and carries over; only the
credential-security bootstrap remains for M1 to go green.

### Recommended path: the FABRIC kit (`fabric/`)

The container-only loop above hit an HTCondor credential-security wall because a
bare `condor_master -f` runs the daemons as `condor` (no root priv-switch). The
turnkey **`deploy/approach-b/fabric/`** kit stands the pool up on a dedicated
FABRIC slice with HTCondor installed via **systemd** (master runs as root →
credentials read normally, so the `read_secure_file` blocker does not occur). It
also provides the k3s control plane for the per-user-pod milestones. See
`fabric/README.md` — that is the intended way to take M1→M6 forward.

## Next: M2 (submit-only schedd-in-pod end-to-end) once M1 auth is green.
