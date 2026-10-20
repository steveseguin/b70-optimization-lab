#!/usr/bin/env bash
# Campaign 50: registered G1–G4 release gate. No builds, installs or publishing.
# Prepare a fresh pip-installed VENV, an archive-built IMG, and the prebuilt
# CPU task image freeagent-repair-n40-s2x before loading the research server.
# Required: VENV, IMG, SOURCE_ARCHIVE, RELEASE_SOURCE (extracted archive root),
# SUDO_ASKPASS. Optional: VERSION=1.2.0, RUN=c50, OUT=/new/evidence/directory.
# A failed check stops the sequence. No restarts/retries or resident restoration.
# Run on otherwise empty cards; this script refuses to stop unrelated services.
set -Eeuo pipefail
LAB=$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)
CHECK=$LAB/experiments/qwen38-27b-b70/scripts/ctxkeeper-release-gate-check.py
VERSION=${VERSION:-1.2.0}
RUN=${RUN:-c50}
OUT=${OUT:-/mnt/fast-ai/bench-results/context-longrun-20261012/$RUN}
VENV=${VENV:?set VENV to the freshly installed release venv}
IMG=${IMG:?set IMG to the image built from the release source archive}
SOURCE_ARCHIVE=${SOURCE_ARCHIVE:?set SOURCE_ARCHIVE}
RELEASE_SOURCE=${RELEASE_SOURCE:?set RELEASE_SOURCE to its extracted root}
export SUDO_ASKPASS=${SUDO_ASKPASS:?set SUDO_ASKPASS}
TASK=/mnt/fast-ai/bench-results/context-longrun-20261012/client-repair2/tasks/repair-n40-s2x
TASK_IMG=freeagent-repair-n40-s2x
PORT=18196 PPORT=18200 DPORT=18201
SRV=$OUT/server
PREFIX=ctx-release-$RUN
SERVER_UNIT=$PREFIX-server
PROXY_UNIT=$PREFIX-proxy
BACKEND_UNIT=$PREFIX-gemma
FRONT_UNIT=$PREFIX-frontdoor
DOCKER_PROXY=$PREFIX-docker
TASK_CONTAINER=$PREFIX-repair
START=$(date --iso-8601=seconds)
FAULT_RE='(xe [0-9a-f:.]+|drm\]).*(Fault response|CAT error|engine reset|gt reset|GPU reset|coredump has been created|Timedout job|timed out|wedged|device lost|failed to respond)|soft lockup'
SERVER_OWNED=0 PROXY_OWNED=0 BACKEND_OWNED=0 FRONT_OWNED=0 DOCKER_OWNED=0 TASK_OWNED=0
CURRENT=preflight
say() { printf '### %s %s\n' "$(date +%H:%M:%S)" "$*"; }
record() { python3 "$CHECK" record "$OUT" "$1" "$2" "$3"; }
die() { say "FAIL: $*" >&2; record "$CURRENT" failed "$*"; exit 1; }
unit_alive() {
  local state
  state=$(systemctl --user show "$1" -p ActiveState --value 2>/dev/null) || return 1
  [[ $state == active || $state == activating || $state == deactivating ]]
}
wait_unit_off() {
  local n
  for n in $(seq 1 60); do unit_alive "$1" || return 0; sleep 3; done
  return 1
}
stop_unit() {
  systemctl --user stop --no-block "$1" || return 1
  wait_unit_off "$1"
}
fault_check() {
  sudo -A journalctl -k --since "$START" --no-pager -o short-iso > "$OUT/kernel.log" || return 1
  if grep -Ei "$FAULT_RE" "$OUT/kernel.log" > "$OUT/kernel-faults.log"; then return 1; fi
}
ready() {
  local base=$1 unit=$2 limit=$3 n
  for n in $(seq 1 "$limit"); do
    unit_alive "$unit" || return 1
    fault_check || return 1
    if curl -fsS -m 3 "$base/v1/models" >/dev/null 2>&1; then
      if [[ $unit != "$SERVER_UNIT" ]] || python3 - "$SRV/state.json" <<'PY'
import json, sys
try:
    sys.exit(0 if json.load(open(sys.argv[1])).get('status') == 'ready' else 1)
except (OSError, ValueError):
    sys.exit(1)
PY
      then return 0; fi
    fi
    sleep 3
  done
  return 1
}
idle_fp8() {
  local n quiet=0
  for n in $(seq 1 60); do
    if curl -fsS -m 5 "http://127.0.0.1:$PORT/metrics" | python3 "$CHECK" idle; then
      quiet=$((quiet+1)); (( quiet >= 2 )) && return 0
    else quiet=0; fi
    sleep 3
  done
  return 1
}
idle_gemma() {
  local n
  for n in $(seq 1 60); do
    if curl -fsS -m 5 http://127.0.0.1:8000/v1/frontdoor/status | python3 -c 'import json,sys; d=json.load(sys.stdin)["frontdoor"]; sys.exit(0 if d["active_generations"] == 0 and d["queued_generations"] == 0 else 1)'; then return 0; fi
    sleep 3
  done
  return 1
}
stop_server() {
  (( SERVER_OWNED )) || return 0
  if unit_alive "$SERVER_UNIT"; then
    # Before readiness the owner loop can observe STOP after its startup/warmup
    # completes. After admission, require real idle metrics before requesting it.
    if [[ $CURRENT != server ]] && ! idle_fp8; then
      say "Cannot confirm idle FP8 server; no forced GPU stop"; return 1
    fi
    touch "$SRV/STOP"
    wait_unit_off "$SERVER_UNIT" || return 1
  fi
  python3 - "$SRV/state.json" <<'PY' || return 1
import json, sys
d = json.load(open(sys.argv[1]))
assert d.get('stop_confirmed') is True, d
assert d.get('status') == 'stopped' and d.get('error') is None, d
PY
  SERVER_OWNED=0
}
stop_proxy() {
  (( PROXY_OWNED )) || return 0
  stop_unit "$PROXY_UNIT" || return 1
  PROXY_OWNED=0
}
stop_cpu_container() {
  # Both owned containers have no GPU devices and use --init so TERM reaches
  # their children. Bound this CPU-only stop; an unresponsive task must not
  # prevent the subsequent upstream drain and graceful GPU shutdown.
  timeout --foreground --signal=TERM 45 docker stop --time 30 "$1" >/dev/null && docker rm "$1" >/dev/null
}
cleanup() {
  local bad=0
  if (( DOCKER_OWNED )); then stop_cpu_container "$DOCKER_PROXY" || bad=1; DOCKER_OWNED=0; fi
  stop_proxy || bad=1
  if (( TASK_OWNED )); then stop_cpu_container "$TASK_CONTAINER" || bad=1; TASK_OWNED=0; fi
  stop_server || bad=1
  if (( BACKEND_OWNED )); then
    if (( FRONT_OWNED )) && ! idle_gemma; then
      say "Cannot confirm idle Gemma; no forced GPU stop"; bad=1
    else
      if (( FRONT_OWNED )); then stop_unit "$FRONT_UNIT" || bad=1; FRONT_OWNED=0; fi
      stop_unit "$BACKEND_UNIT" || bad=1; BACKEND_OWNED=0
    fi
  elif (( FRONT_OWNED )); then stop_unit "$FRONT_UNIT" || bad=1; FRONT_OWNED=0; fi
  fault_check || bad=1
  return "$bad"
}
finish() {
  local rc=$? clean=0
  trap - EXIT INT TERM ERR
  set +e
  cleanup || clean=1
  python3 "$CHECK" finish "$OUT" "$rc" "$clean" || rc=1
  say "gate finished rc=$rc; receipts $OUT/status.json; cleanup status $clean"
  exit "$rc"
}
start_proxy() {
  local gate=$1; shift
  systemd-run --user --unit="$PROXY_UNIT" --collect -p Restart=no -p SendSIGKILL=no \
    "$VENV/bin/ctxkeeper" --host 127.0.0.1 --port "$PPORT" --state-dir "$OUT/proxy-state/$gate" "$@"
  PROXY_OWNED=1
  ready "http://127.0.0.1:$PPORT" "$PROXY_UNIT" 30
}
status_proxy() {
  curl -fsS -m 10 "$1/ctxkeeper/status" > "$OUT/$2-proxy-status.json"
  if [[ $2 != G2 ]]; then journalctl --user -u "$PROXY_UNIT" --since "$START" --no-pager -o cat > "$OUT/$2-proxy.log"; fi
}

[[ $RUN =~ ^[a-zA-Z0-9_-]+$ ]] || { echo 'RUN must contain only letters, numbers, _ or -' >&2; exit 2; }
[[ ! -e $OUT ]] || { echo "Refusing existing OUT: $OUT" >&2; exit 2; }
mkdir -p "$OUT/proxy-state"
python3 "$CHECK" init "$OUT" "$VERSION" "$VENV" "$IMG" "$SOURCE_ARCHIVE" "$RELEASE_SOURCE"
trap finish EXIT
trap 'record "$CURRENT" interrupted "signal received"; exit 130' INT TERM
trap 'record "$CURRENT" failed "command failed at line $LINENO"' ERR
cd "$LAB"
[[ $("$VENV/bin/ctxkeeper" --version) == "ctxkeeper $VERSION" ]] || die 'pip version differs'
"$VENV/bin/python" -c 'import openai'
[[ -f $TASK/tests/spec.json && -f $RELEASE_SOURCE/examples/long_chat.py ]] || die 'task or release example missing'
docker image inspect "$IMG" > "$OUT/image.json"
docker image inspect "$TASK_IMG" > "$OUT/task-image.json"
docker image inspect neural-download/vllm-openai-xpu:qwen38-fp8-v0290-r314-state-stride > "$OUT/server-image.json"
[[ $(docker run --rm --network none "$IMG" --version) == "ctxkeeper $VERSION" ]] || die 'Docker version differs'
# Bind both installed forms to the archive bytes, not only their version labels.
hash_code='import hashlib,json,ctxkeeper,notesdelta; print(json.dumps({m.__name__:hashlib.sha256(open(m.__file__,"rb").read()).hexdigest() for m in (ctxkeeper,notesdelta)},sort_keys=True))'
"$VENV/bin/python" -I -c "$hash_code" > "$OUT/pip-source-hashes.json"
docker run --rm --network none --entrypoint python3 "$IMG" -c "$hash_code" > "$OUT/docker-source-hashes.json"
python3 - "$OUT" "$RELEASE_SOURCE" <<'PY'
import hashlib, json, pathlib, sys
out, src = map(pathlib.Path, sys.argv[1:])
expected = {m: hashlib.sha256((src / (m + '.py')).read_bytes()).hexdigest() for m in ('ctxkeeper', 'notesdelta')}
for name in ('pip-source-hashes.json', 'docker-source-hashes.json'):
    assert json.loads((out / name).read_text()) == expected, name
PY
for unit in "$SERVER_UNIT" "$PROXY_UNIT" "$BACKEND_UNIT" "$FRONT_UNIT"; do
  [[ $(systemctl --user show "$unit" -p LoadState --value) == not-found ]] || die "unit already exists: $unit"
done
for name in "$DOCKER_PROXY" "$TASK_CONTAINER"; do
  if docker container inspect "$name" >/dev/null 2>&1; then die "container already exists: $name"; fi
done
python3 - "$PORT" "$PPORT" "$DPORT" 8000 19350 19351 <<'PY'
import socket, sys
for port in map(int, sys.argv[1:]):
    with socket.socket() as s:
        s.bind(('127.0.0.1', port))
PY
if pgrep -x llama-server >/dev/null || pgrep -f '^VLLM::|^vllm serve' >/dev/null; then die 'existing model process'; fi
# Refuse existing containers with direct GPU device mounts; no wildcard stops.
ids=$(docker ps -q)
if [[ -n $ids ]]; then
  docker inspect $ids > "$OUT/preexisting-containers.json"
  python3 - "$OUT/preexisting-containers.json" <<'PY'
import json, sys
for c in json.load(open(sys.argv[1])):
    h = c['HostConfig']
    assert not h.get('Privileged') and not h.get('DeviceRequests'), c['Name']
    assert not any('/dev/dri' in str(x) for x in h.get('Devices', []) + (h.get('Binds') or [])), c['Name']
PY
fi
[[ $(awk '/^MemAvailable:/ {print $2}' /proc/meminfo) -ge 10000000 ]] || die 'less than 10 GB available before launch'
fault_check || die 'kernel evidence unavailable or fault already logged'
python3 "$CHECK" env "$LAB/deploy/systemd/two-b70-host/balanced-backends.conf" > "$OUT/balanced-backends.env0"
python3 "$CHECK" env "$LAB/deploy/systemd/two-b70-host/balanced-frontdoor.conf" > "$OUT/balanced-frontdoor.env0"
mapfile -d '' -t BACKEND_ENV < "$OUT/balanced-backends.env0"
mapfile -d '' -t FRONT_ENV < "$OUT/balanced-frontdoor.env0"
record preflight passed 'fresh versions and inputs present; no builds or resident services changed'

CURRENT=server
systemd-run --user --unit="$SERVER_UNIT" --collect -p WorkingDirectory="$LAB" -p Restart=no \
  -p KillMode=process -p SendSIGKILL=no -E B70_GUARD_MIN_AVAILABLE_GIB=1.6 -E B70_ALLOW_BUSY_RENDER=0 \
  python3 experiments/qwen38-27b-b70/scripts/run-fp8-tp1-server.py --out "$SRV" --port "$PORT" \
  --image neural-download/vllm-openai-xpu:qwen38-fp8-v0290-r314-state-stride --warmup --keep --startup-timeout 1800 \
  --tp 2 --mem 0.95 --max-model-len 262144 --batched 832 --seqs 2 --fa-verify-rows --mtp 5 --draft-int4 \
  --shortlist /opt/draft-shortlists/shortlist-u-v1all-v2top65k.txt \
  --overlay b70-allgather-allreduce --extra-env B70_ALLGATHER_ALLREDUCE=1 \
  --overlay b70-chunked-upload --extra-env B70_CHUNKED_UPLOAD=1 \
  --serve-arg=--enable-auto-tool-choice --serve-arg=--tool-call-parser=qwen3_coder --serve-arg=--reasoning-parser=qwen3 \
  --prefix-cache align --overlay b70-prefix-cache-exact --extra-env B70_PREFIX_CACHE_EXACT=1 \
  --serve-arg=--prefix-cache-retention-interval=13312 \
  --overlay b70-spec-resume-accepted --extra-env B70_SPEC_RESUME_ACCEPTED=1 \
  --overlay b70-gdn-state-width --extra-env B70_GDN_STATE_WIDTH=1 \
  --overlay b70-exclusive-prefill --extra-env B70_EXCLUSIVE_PREFILL=1 \
  --extra-env B70_FA_VERIFY_ROWS_ONE_LAUNCH=1 --extra-env B70_PREFIX_CACHE_EXACT_TAIL=1 \
  --overlay b70-step-breadcrumbs --extra-env B70_STEP_BREADCRUMBS=1
SERVER_OWNED=1
ready "http://127.0.0.1:$PORT" "$SERVER_UNIT" 600 || die 'research server failed readiness'

CURRENT=G1
record G1 running 'freeagent, default --recipe qwen; registered 40 fixed / 38 clean / 6 audits / 45 min'
start_proxy G1 --upstream "http://127.0.0.1:$PORT" --recipe qwen
[[ $(awk '/^MemAvailable:/ {print $2}' /proc/meminfo) -ge 1940000 ]] || die 'insufficient room for 256 MiB CPU task'
docker run -d --init --name "$TASK_CONTAINER" --network none --memory 256m --memory-swap 256m --cpus 2 "$TASK_IMG" sleep infinity
TASK_OWNED=1
mkdir -p "$OUT/G1/trial/verifier"
t0=$SECONDS
timeout --foreground --signal=INT 3600 python3 tools/freeagent/freeagent.py \
  --api-base "http://127.0.0.1:$PPORT/v1" --model qwen38-27b-fp8 --container "$TASK_CONTAINER" \
  --instruction "$TASK/instruction.md" --out "$OUT/G1/trial" --max-steps 900 --time-limit 3300 > "$OUT/G1.out" 2>&1
docker cp "$TASK/tests/." "$TASK_CONTAINER:/tests/"
docker exec "$TASK_CONTAINER" mkdir -p /logs/verifier
docker exec "$TASK_CONTAINER" python3 /tests/grade.py > "$OUT/G1/trial/verifier/test-stdout.txt" 2>&1
docker cp "$TASK_CONTAINER:/logs/verifier/." "$OUT/G1/trial/verifier/"
elapsed=$((SECONDS-t0))
status_proxy "http://127.0.0.1:$PPORT" G1
stop_proxy
stop_cpu_container "$TASK_CONTAINER"; TASK_OWNED=0
idle_fp8 && fault_check || die 'server did not drain cleanly after G1'
python3 "$CHECK" g1 "$OUT" "$OUT/G1/trial" "$elapsed"

CURRENT=G2
record G2 running 'archive-built Docker image; 300K demo, thinking off'
mkdir -p "$OUT/proxy-state/G2"
docker run -d --init --name "$DOCKER_PROXY" --network host --user "$(id -u):$(id -g)" \
  -v "$OUT/proxy-state/G2:/state" "$IMG" --recipe qwen --upstream "http://127.0.0.1:$PORT" --host 127.0.0.1 --port "$DPORT"
DOCKER_OWNED=1
for n in $(seq 1 30); do
  curl -fsS -m 3 "http://127.0.0.1:$DPORT/v1/models" >/dev/null 2>&1 && break
  sleep 1
done
curl -fsS -m 3 "http://127.0.0.1:$DPORT/v1/models" > "$OUT/G2-models.json"
rc=0
timeout --foreground --signal=INT 3600 "$VENV/bin/python" "$RELEASE_SOURCE/examples/long_chat.py" \
  --base-url "http://127.0.0.1:$DPORT/v1" --tokens 300000 \
  --extra-body '{"chat_template_kwargs":{"enable_thinking":false}}' > "$OUT/G2-long_chat.out" 2>&1 || rc=$?
status_proxy "http://127.0.0.1:$DPORT" G2
docker logs "$DOCKER_PROXY" > "$OUT/G2-proxy.log" 2>&1
stop_cpu_container "$DOCKER_PROXY"; DOCKER_OWNED=0
idle_fp8 && fault_check || die 'server did not drain cleanly after G2'
python3 "$CHECK" demo "$OUT" G2 "$OUT/G2-long_chat.out" "$rc"

CURRENT=G3
record G3 running 'OpenAI SDK types: plain, tool call and streaming; SDK retries disabled'
start_proxy G3 --upstream "http://127.0.0.1:$PORT" --recipe qwen
timeout --foreground --signal=INT 600 "$VENV/bin/python" "$CHECK" sdk "http://127.0.0.1:$PPORT/v1" "$OUT/G3-sdk.json" > "$OUT/G3-sdk.out" 2>&1
status_proxy "http://127.0.0.1:$PPORT" G3
stop_proxy
idle_fp8 && fault_check || die 'server did not drain cleanly after G3'
record G3 passed 'all three SDK response contracts passed; G3-sdk.json retains responses'
stop_server

CURRENT=G4
record G4 running 'balanced Gemma transient smoke; 100K demo; no quality bar'
# Load the balanced recipe without installing drop-ins, enabling services,
# restarting an existing server or restoring the throughput resident service.
systemd-run --user --unit="$BACKEND_UNIT" --collect -p WorkingDirectory="$LAB" -p Restart=no \
  -p KillSignal=SIGINT -p SendSIGKILL=no -p TimeoutStopSec=180 \
  /usr/bin/env "${BACKEND_ENV[@]}" GEMMA4_26B_PROFILE=service HOST=127.0.0.1 BASE_PORT=19350 \
  OUT_DIR="$OUT/gemma" PID_DIR="$OUT/gemma/pids" "$LAB/scripts/serve-gemma4-26b-q8-quad-production.sh"
BACKEND_OWNED=1
ready http://127.0.0.1:19350 "$BACKEND_UNIT" 300 || die 'Gemma backend 0 not ready'
ready http://127.0.0.1:19351 "$BACKEND_UNIT" 300 || die 'Gemma backend 1 not ready'
systemd-run --user --unit="$FRONT_UNIT" --collect -p Restart=no -p SendSIGKILL=no \
  /usr/bin/env "${FRONT_ENV[@]}" FRONTDOOR_HOST=127.0.0.1 FRONTDOOR_PORT=8000 \
  FRONTDOOR_PAUSE_FILE="$OUT/gemma/PAUSE" "$LAB/scripts/run-gemma4-26b-q8-quad-frontdoor.sh"
FRONT_OWNED=1
ready http://127.0.0.1:8000 "$FRONT_UNIT" 30 || die 'Gemma frontdoor not ready'
start_proxy G4 --upstream http://127.0.0.1:8000 --recipe agent --budget 15360
rc=0
timeout --foreground --signal=INT 3600 "$VENV/bin/python" "$RELEASE_SOURCE/examples/long_chat.py" \
  --base-url "http://127.0.0.1:$PPORT/v1" --tokens 100000 > "$OUT/G4-long_chat.out" 2>&1 || rc=$?
status_proxy "http://127.0.0.1:$PPORT" G4
stop_proxy
python3 "$CHECK" demo "$OUT" G4 "$OUT/G4-long_chat.out" "$rc"
idle_gemma && fault_check || die 'Gemma did not drain cleanly after G4'
say 'G1–G4 complete; stopping owned Gemma units and leaving the cards empty'
# EXIT performs and verifies graceful cleanup before marking the gate passed.
