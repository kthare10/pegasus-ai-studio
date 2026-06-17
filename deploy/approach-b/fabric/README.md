# Approach B on FABRIC — turnkey provisioning kit

Stands up the PegasusAI Studio Approach-B prototype on a dedicated FABRIC slice:
a shared HTCondor pool (central manager + execute nodes) and a k3s control plane
for per-user submit pods. HTCondor is installed via the DEB packages + **systemd**
(so `condor_master` runs as root and reads credentials normally) — this avoids
the `read_secure_file()` / credential-ownership problems hit when running
`condor_master -f` directly in a container.

## Files
- `create_slice.py` — fablib slice builder (topology, L2 pool network, public IPv4).
- `provision-common.sh` — installs HTCondor 25.x on a node (run on cm + exec).
- `provision-cm.sh <cm-ip>` — central manager + pool signing key + token minting.
- `provision-exec.sh <cm-ip> <execute.token>` — execute node (startd) + token.
- `provision-k3s.sh server|agent …` — k3s for the Studio control plane (M2+).
- `condor/50-*.conf.tmpl` — HTCondor config.d drop-ins (pool identity, CCB, TRUST_DOMAIN).

## 1. Create the slice
```sh
# from a FABRIC JupyterHub notebook (or any host with fabric creds)
python3 create_slice.py        # edit SITE / sizes / WORKERS at the top first
```
Gives `studio-cp` (10.10.0.10, public IPv4), `condor-cm` (10.10.0.20),
`condor-exec1` (10.10.0.30), all on one L2 `poolnet`.

## 2. Shared HTCondor pool (M1)
```sh
# copy this kit to each node (scp -r deploy/approach-b/fabric <node>:)
# --- on condor-cm and condor-exec1 ---
./provision-common.sh
# --- on condor-cm ---
./provision-cm.sh 10.10.0.20          # mints tokens under ./tokens/
# copy the execute token to the exec node
scp ./tokens/execute.token condor-exec1:~/fabric/
# --- on condor-exec1 ---
./provision-exec.sh 10.10.0.20 ~/fabric/execute.token
```
**M1 exit:** `condor_status` on condor-cm lists `condor-exec1` with its slots.

## 3. Submit-only schedd in a pod (M2)
Push the image so k3s/podman can pull it, then run it in **submit** mode pointed
at the CM, with the submit token on the (PVC-backed) `$HOME`:
```sh
docker push kthare10/pegasusai-studio:approach-b      # one-time, from a build host

# on studio-cp (or as a k8s pod — see step 4), with submit.token in place:
mkdir -p $HOME/pvc-home/.condor/tokens.d
cp submit.token $HOME/pvc-home/.condor/tokens.d/pool.token
docker run -d --name studio-submit \
  -e STUDIO_CONDOR_MODE=submit -e STUDIO_CONDOR_HOST=10.10.0.20:9618 \
  -v "$HOME/pvc-home:/home/pegasus" -p 8080:80 \
  kthare10/pegasusai-studio:approach-b
# inside: condor_submit a sleep job; it should run on condor-exec1 via CCB.
```
**M2 exit:** a job submitted from the pod's schedd runs on `condor-exec1` and
completes — proving CCB + token auth across the unroutable-pod boundary.

## 4. Studio control plane (M3+)
```sh
# on studio-cp
./provision-k3s.sh server                 # prints the worker join token
# (optional) on studio-w1
./provision-k3s.sh agent https://10.10.0.10:6443 <token>
```
Then deploy JupyterHub + KubeSpawner (CILogon auth — reuse the Approach-A client,
redirect URI `/hub/oauth_callback`), spawning the `:approach-b` image as per-user
submit pods with a per-user PVC and a `submit.token` minted per user. PVC carries
the Condor spool + submit dirs + `~/.pegasus/workflow.db` for DAGMan recovery (M4).

## Notes
- **Trust domain** `pegasus-studio-pool` is identical on the CM, execute nodes,
  and submit pods so IDTOKEN issuers match.
- **Image pull:** the all-in-one image is large; pre-pull to k3s nodes to keep
  spawn latency down.
- **Secrets** (CILogon client secret, pool signing key, per-user tokens) live on
  the nodes / in k8s Secrets, never in the repo.
