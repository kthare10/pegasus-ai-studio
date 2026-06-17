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

## Next: M1 (shared Condor pool on K8s) and M2 (schedd-in-pod networking).
