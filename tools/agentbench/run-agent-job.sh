#!/usr/bin/env bash
# run-agent-job.sh AGENT TASK_DIR OUT_DIR JOB_NAME PROXY_URL [TIME_LIMIT]
#
# One run of a third-party coding agent on a repair-marathon task, graded exactly as tools/freeagent/run-freeagent-job.sh
# grades freeagent (the task's own tests/grade.py in the task container, same job layout: OUT_DIR/jobs/JOB/trial/
# agent/ and verifier/details.json).
#
# Differences from the freeagent runner, all for safety:
#   - the agent runs INSIDE the task container (image agentbench-AGENT:TASK, built FROM the task image), as an
#     unprivileged user, --network none, --cap-drop ALL, no-new-privileges, a memory cap (AGENT_MEM, default 768m =
#     the task's 256 MiB plus ~512 MiB for the agent);
#   - its only way out is one Unix socket (a read-only mount of a directory holding nothing else), bridged on the host
#     to PROXY_URL (which must be http://127.0.0.1:PORT/... or localhost); inside the container the agent uses the
#     same URL;
#   - nothing else from the host is mounted: logs leave the container by `docker cp` after the run.
#
# Env: MODEL_NAME (qwen38-27b-fp8), AGENT_MEM (768m), TAP (summary | full: also store every request body),
#      KEEP_CONTAINER=1 (leave the container for inspection).
set -uo pipefail
AGENT=${1:?usage: run-agent-job.sh AGENT TASK_DIR OUT_DIR JOB_NAME PROXY_URL [TIME_LIMIT]}
TASK=${2:?}; OUT=${3:?}; JOB=${4:?}; PROXY_URL=${5:?}; TIME_LIMIT=${6:-3300}
MODEL_NAME=${MODEL_NAME:-qwen38-27b-fp8}
AGENT_MEM=${AGENT_MEM:-768m}
TAP=${TAP:-summary}
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
TASK=$(cd "$TASK" && pwd)
TNAME=$(basename "$TASK")
IMG="agentbench-$AGENT:$TNAME"
C="agentbench-$JOB"
TRIAL="$OUT/jobs/$JOB/trial"
T0=$SECONDS
say() { echo "### $(date +%H:%M:%S) $*"; }
die() { echo "run-agent-job: $*" >&2; exit 2; }

[[ $JOB =~ ^[A-Za-z0-9_.-]+$ ]] || die "JOB_NAME may hold only letters, digits, . _ -"
[[ $PROXY_URL =~ ^http://(127\.0\.0\.1|localhost):([0-9]+)(/.*)?$ ]] || die "PROXY_URL must be http://127.0.0.1:PORT/..."
PORT=${BASH_REMATCH[2]}
URL_IN="http://127.0.0.1:$PORT${BASH_REMATCH[3]}"
[ -f "$HERE/agents/$AGENT/Dockerfile" ] || die "no agent $AGENT (see $HERE/agents/)"
docker image inspect "$IMG" >/dev/null 2>&1 || "$HERE/build-agent-image.sh" "$AGENT" "$TASK" || die "image build failed"

mkdir -p "$TRIAL/agent" "$TRIAL/verifier"
SOCKDIR="${XDG_RUNTIME_DIR:-/tmp}/agentbench/$JOB"
rm -rf "$SOCKDIR"; mkdir -p "$SOCKDIR"; chmod 755 "$SOCKDIR"
python3 -I "$HERE/bridge.py" --listen "unix:$SOCKDIR/proxy.sock" --connect "tcp:127.0.0.1:$PORT" \
  --tap "$TRIAL/agent/requests.jsonl" --tap-mode "$TAP" > "$TRIAL/agent/host-bridge.log" 2>&1 &
BRIDGE=$!
for _ in $(seq 50); do [ -S "$SOCKDIR/proxy.sock" ] && break; sleep 0.1; done
[ -S "$SOCKDIR/proxy.sock" ] || die "host bridge did not start (see $TRIAL/agent/host-bridge.log)"
cleanup() {
  [ -n "${WATCH:-}" ] && kill "$WATCH" 2>/dev/null
  kill "$BRIDGE" 2>/dev/null
  [ "${KEEP_CONTAINER:-0}" = 1 ] || docker rm -f "$C" >/dev/null 2>&1
  rm -rf "$SOCKDIR"
}
trap cleanup EXIT

docker rm -f "$C" >/dev/null 2>&1 || true
docker run -d --name "$C" --network none --memory "$AGENT_MEM" --memory-swap "$AGENT_MEM" --cpus 2 --pids-limit 1024 \
  --cap-drop ALL --security-opt no-new-privileges -v "$SOCKDIR:/run/agentbench:ro" \
  --label agentbench.job="$JOB" "$IMG" sleep infinity >/dev/null || die "container did not start"
docker exec -i "$C" sh -c 'umask 022; cat > /opt/agentbench/task/instruction.md' < "$TASK/instruction.md"
python3 -I "$HERE/memwatch.py" "$C" "$TRIAL/agent/memory.json" --every 0.5 &
WATCH=$!
say "container $C up ($IMG, cap $AGENT_MEM); agent $AGENT starts (time limit ${TIME_LIMIT}s, proxy $PROXY_URL)"

timeout -k 30 $((TIME_LIMIT + 300)) docker exec -u agent -w /app \
  -e AB_PORT="$PORT" -e AB_PROXY_URL="$URL_IN" -e AB_MODEL="$MODEL_NAME" -e AB_TIME_LIMIT="$TIME_LIMIT" \
  "$C" /opt/agentbench/entry.sh > "$TRIAL/agent/agent-stdout.txt" 2> "$TRIAL/agent/agent-stderr.txt"
RC=$?
kill "$WATCH" 2>/dev/null; WATCH=
docker exec "$C" cat /sys/fs/cgroup/memory.peak > "$TRIAL/agent/memory.peak" 2>/dev/null
docker exec -u agent "$C" sh -c 'kill -9 -1' >/dev/null 2>&1      # nothing of the agent's may run during grading
say "agent done in $(( (SECONDS-T0)/60 )) min $(( (SECONDS-T0)%60 )) s (exit $RC); grading"

docker cp "$C:/logs/agent/." "$TRIAL/agent/" >/dev/null 2>&1 || true
docker cp "$C:/home/agent" "$TRIAL/agent/home" >/dev/null 2>&1 || true
docker cp "$TASK/tests/." "$C:/tests/" >/dev/null
docker exec "$C" mkdir -p /logs/verifier
docker exec "$C" ls -la /app > "$TRIAL/verifier/app-files.txt" 2>&1 || true
# The grader runs as root, but the container dropped every capability, so plain root cannot read a file the agent
# made owner-only (Mistral Vibe's write_file: FIXES.md and AUDIT.md were graded as empty in campaign 20d). The
# agent's processes are all gone by now; the grading command alone gets back the read access root normally has.
docker exec --privileged "$C" python3 /tests/grade.py 2>&1 | tee "$TRIAL/verifier/test-stdout.txt" | grep 'repair score' || true
docker cp "$C:/logs/verifier/." "$TRIAL/verifier/" >/dev/null 2>&1 || true

python3 -I "$HERE/check_history.py" "$TRIAL/agent/requests.jsonl" > "$TRIAL/agent/history-check.json" 2>/dev/null || true
python3 -I - "$TRIAL" "$AGENT" "$IMG" "$JOB" "$TNAME" "$PROXY_URL" "$MODEL_NAME" "$TIME_LIMIT" "$AGENT_MEM" "$RC" \
  "$((SECONDS - T0))" "$(docker image inspect -f '{{.Id}}' "$IMG")" \
  "$(docker image inspect -f '{{index .Config.Labels "agentbench.agent.version"}}' "$IMG")" <<'EOF'
import json, os, sys
trial, agent, img, job, task, url, model, limit, mem, rc, wall, img_id, ver = sys.argv[1:]
def load(p):
    try:
        return json.load(open(os.path.join(trial, p)))
    except (OSError, ValueError):
        return None
peak = None
try:
    peak = int(open(os.path.join(trial, "agent/memory.peak")).read())
except (OSError, ValueError):
    pass
rec = {"agent": agent, "agent_version": ver, "image": img, "image_id": img_id, "job": job, "task": task,
       "proxy_url": url, "model": model, "time_limit_s": int(limit), "memory_cap": mem, "exec_rc": int(rc),
       "wall_s": int(wall), "agent_exit": load("agent/exit.json"), "memory": load("agent/memory.json"),
       "memory_peak_cgroup_bytes": peak, "history": load("agent/history-check.json"),
       "verifier": {k: v for k, v in (load("verifier/details.json") or {}).items()
                    if k in ("score", "fixed", "clean", "rules", "audit", "tickets_fetched", "void")}}
json.dump(rec, open(os.path.join(trial, "agent/agentbench.json"), "w"), indent=1)
EOF
say "job $JOB complete"
