#!/usr/bin/env bash
# Session reaper: reclaim per-user resources from logged-out / idle users
# WITHOUT touching running workflows (which live under condor, not these units).
#
# Policy, per provisioned user:
#   jupyter@user     stopped after JUPYTER_IDLE_HOURS with no Jupyter activity
#                    (Jupyter's own last_activity API).
#   studio-api@user  stopped after API_IDLE_HOURS with no gateway activity
#                    (nginx studio-activity.log), no attached terminals, AND
#                    an empty condor queue for the user (defense in depth —
#                    the API's startup rescan re-arms workflow monitors, but a
#                    running workflow keeps its live JSONL feed this way).
#
# Stopped sessions restart transparently: the next authenticated request 502s
# into the onboarding broker, which starts the units and redirects back.
#
# Run from studio-reaper.timer (every 15 min). Dry run: studio-reaper.sh -n
set -uo pipefail

JUPYTER_IDLE_HOURS="${JUPYTER_IDLE_HOURS:-2}"
API_IDLE_HOURS="${API_IDLE_HOURS:-8}"
ACTIVITY_LOG=/var/log/nginx/studio-activity.log
CONF_DIR=/etc/pegasus-studio

DRY=""
[ "${1:-}" = "-n" ] && DRY="echo DRY-RUN:"

now=$(date +%s)

last_activity_epoch() {  # $1=username -> epoch of last gateway request (0 if none)
    local ts
    ts=$(grep -h " $1 " "$ACTIVITY_LOG" "$ACTIVITY_LOG.1" 2>/dev/null | tail -1 | cut -d" " -f1)
    [ -n "$ts" ] && date -d "$ts" +%s 2>/dev/null || echo 0
}

for envfile in "$CONF_DIR"/users/*.env; do
    [ -e "$envfile" ] || continue
    user=$(basename "$envfile" .env)
    port=$(grep -oP '(?<=^STUDIO_PORT=)\d+' "$envfile")
    jport=$(grep -oP '(?<=^STUDIO_JUPYTER_PORT=)\d+' "$envfile")

    last=$(last_activity_epoch "$user")
    idle_h=$(( (now - last) / 3600 ))

    # --- JupyterLab: stop on Jupyter-side inactivity -----------------------
    if systemctl is-active --quiet "jupyter@$user"; then
        jlast=$(curl -s --max-time 3 "http://127.0.0.1:$jport/jupyter/api/status" \
            | python3 -c "import json,sys,datetime;
d=json.load(sys.stdin); t=d.get('last_activity','');
print(int(datetime.datetime.fromisoformat(t.replace('Z','+00:00')).timestamp()) if t else 0)" \
            2>/dev/null || echo 0)
        jidle_h=$(( (now - ${jlast:-0}) / 3600 ))
        if [ "${jlast:-0}" -gt 0 ] && [ "$jidle_h" -ge "$JUPYTER_IDLE_HOURS" ] \
           && [ "$idle_h" -ge "$JUPYTER_IDLE_HOURS" ]; then
            $DRY systemctl stop "jupyter@$user" \
                && echo "reaped jupyter@$user (idle ${jidle_h}h)"
        fi
    fi

    # --- studio-api: stop only when truly quiet ----------------------------
    if systemctl is-active --quiet "studio-api@$user"; then
        [ "$idle_h" -lt "$API_IDLE_HOURS" ] && continue

        # any attached terminal client? (live xterm in some browser)
        attached=$(curl -s --max-time 3 "http://127.0.0.1:$port/api/terminals" \
            | python3 -c "import json,sys; print(sum(s.get('attached',0) for s in json.load(sys.stdin)))" \
            2>/dev/null || echo 1)
        [ "${attached:-1}" -gt 0 ] && continue

        # any jobs in the user's condor queue? (idle/running/held all count)
        jobs=$(condor_q -submitter "$user" -totals 2>/dev/null \
            | grep -oP '^\d+(?= jobs)' | tail -1)
        [ "${jobs:-0}" -gt 0 ] && continue

        $DRY systemctl stop "studio-api@$user" \
            && echo "reaped studio-api@$user (idle ${idle_h}h, queue empty)"
    fi
done
exit 0
