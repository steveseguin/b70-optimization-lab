#!/usr/bin/env bash
# 2026-10-17 step-floor arm Pk (registered 11:46 EDT in notes/2026-10-17-fp8-step-floor.md before it ran): the TP2
# package exactly as shipped (packages/qwen38-27b-fp8-tp2-b70/scripts/serve.py start --profile recommended, R310 image
# eb8165..., its own environment and overlays), then the same write probe as arms L..P0. Is the package's drafting
# step about 38 ms like R314's, or the quoted 33.0?
# One server, started once and stopped gracefully; the first fault line or failed start stops the run; cards left empty.
#   SUDO_ASKPASS=... systemd-run --user --unit=ctx-step-floor-pk ... bash run-20261017-step-floor-pk.sh
set -uo pipefail
LAB=/home/steve/b70-optimization-lab
cd "$LAB"
export SUDO_ASKPASS=${SUDO_ASKPASS:?set SUDO_ASKPASS}
PKG=$LAB/packages/qwen38-27b-fp8-tp2-b70/scripts/serve.py
D=$LAB/experiments/qwen38-27b-b70/data/2026-10-17-step-floor
S=$LAB/experiments/qwen38-27b-b70/scripts
ST=/mnt/fast-ai/bench-results/fp8-pkg-floor-Pk-20261017
PORT=18197
START=$(date '+%F %T')
FAULT_RE='(xe [0-9a-f:.]+|drm\]).*(Fault response|CAT error|engine reset|gt reset|GPU reset|coredump has been created|Timedout job|timed out|wedged|device lost|failed to respond)|soft lockup'
say() { echo "### $(date +%H:%M:%S) $*"; }
faults() { sudo -A journalctl -k --since "$START" --no-pager -o short-iso 2>/dev/null | grep -Ei "$FAULT_RE"; }
status() { python3 -c "import json;print(json.load(open('$ST/state.json')).get('status'))" 2>/dev/null; }

for u in ctx-after-reboot ctx-fp8-tp2-server; do
  systemctl --user is-active --quiet $u && { say "unit $u is still running; nothing run"; exit 1; }
done
[[ -n $(docker ps -q) ]] && { say "containers running; nothing run"; docker ps --format '{{.Names}} {{.Image}}'; exit 1; }
pgrep -x llama-server >/dev/null && { say "llama-server running; nothing run"; exit 1; }
[[ -e $ST ]] && { say "$ST exists; nothing run"; exit 1; }
for i in $(seq 1 60); do ss -tanH "( sport = :$PORT or dport = :$PORT )" | grep -q . || break; sleep 2; done

say "Pk: the TP2 package as shipped (profile recommended), port $PORT; MemAvailable $(awk '/MemAvailable/{print int($2/1024)}' /proc/meminfo) MiB"
systemctl --user reset-failed ctx-pkg-pk 2>/dev/null
systemd-run --user --unit=ctx-pkg-pk --collect -p WorkingDirectory=$LAB \
  -p StandardOutput=append:$D/owner-Pk.log -p StandardError=append:$D/owner-Pk.log \
  python3 "$PKG" start --state-dir "$ST" --model-dir /mnt/fast-ai/llm-models/qwen3.8-27b-fp8 --profile recommended --port $PORT
s=
for i in $(seq 1 360); do
  s=$(status)
  [[ $s == ready ]] && break
  systemctl --user is-active --quiet ctx-pkg-pk || { say "package owner exited before ready (status $s)"; tail -5 $D/owner-Pk.log; exit 1; }
  [[ -n $(faults) ]] && { say "GPU fault line during the package start"; faults | head -5; python3 "$PKG" stop --state-dir "$ST"; exit 1; }
  sleep 5
done
[[ $s == ready ]] || { say "package not ready in time"; python3 "$PKG" stop --state-dir "$ST"; exit 1; }
say "package ready; MemAvailable $(awk '/MemAvailable/{print int($2/1024)}' /proc/meminfo) MiB"
python3 $S/probe-write-rate-vs-context.py --base-url http://127.0.0.1:$PORT --lengths 1000,8000,16000,30000 \
  --out "$D/write-Pk.json" > "$D/write-Pk.log" 2>&1 || say "write probe failed on Pk"
grep "^WRITE" "$D/write-Pk.log"
python3 "$PKG" stop --state-dir "$ST"
for i in $(seq 1 90); do systemctl --user is-active --quiet ctx-pkg-pk || break; sleep 2; done
systemctl --user is-active --quiet ctx-pkg-pk && say "package owner still running after the stop request"
say "package stopped: $(status)"
F=$(faults)
if [[ -n $F ]]; then say "GPU FAULT LINES since $START; cards left empty"; echo "$F" | head -10; exit 1; fi
say "kernel log clean since $START; cards left empty; arm Pk complete"
