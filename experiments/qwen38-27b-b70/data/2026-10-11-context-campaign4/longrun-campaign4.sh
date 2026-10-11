#!/usr/bin/env bash
# Campaign 4 (2026-10-11, early morning): one unattended runner (AGENTS.md speed rule 4) for the long-horizon context lane.
#   S1  B32ira seed 1, plain 240K stream       the arm round 3 lost when the memory guard stopped the server at 03:15
#   S2  rule / procedure probes, seed 0        B32ira W32 P32 B32ir on the --rules stream (OUT_DIR client-rules)
#   S3  C32 seed 0, plain 240K stream          summarise-at-75 %, the production-style method missing from the 32K table
# Server: the two-card Qwen3.8-27B FP8 recipe of rounds 2-3 (window 65,536), one arm at a time, started once, never restarted.
# Guard floor: B70_GUARD_MIN_AVAILABLE_GIB=1.6, the owner-approved research value of 2026-10-06 (see the launcher). Rounds
# 2-3 were launched without it; server + client left 2.06-2.25 GiB, and the 2.0 default fired on a 110 MB summary step.
# The runner stops the Gemma LAN service first and reinstalls the same recipe at the end, unless a GPU fault line was
# logged, in which case the cards are left empty for a health probe.
set -uo pipefail
LAB=/home/steve/b70-optimization-lab
CTX=$LAB/experiments/qwen38-27b-b70/scripts/context
O=/mnt/fast-ai/bench-results/context-longrun-20261010
SRV=$O/server/tp2-w65536-r4
PORT=18196
PY=/mnt/fast-ai/venvs/clm/bin/python
export SUDO_ASKPASS=${SUDO_ASKPASS:?set SUDO_ASKPASS}
GEMMA_RECIPE=${GEMMA_RECIPE:-throughput}
STAGES=${STAGES:-S1 S2 S3}
S3_LIMIT_S=${S3_LIMIT_S:-6000}
START=$(date '+%F %T')
FAULT_RE='(xe [0-9a-f:.]+|drm\]).*(Fault response|CAT error|engine reset|gt reset|GPU reset|coredump has been created|Timedout job|timed out|wedged|device lost)|soft lockup'
say() { echo "### $(date +%H:%M:%S) $*"; }
avail() { awk '/^MemAvailable:/ {printf "%d", $2/1024}' /proc/meminfo; }
faults() { journalctl -k --since "$START" --no-pager -o short-iso 2>/dev/null | grep -Ei "$FAULT_RE"; }
server_up() { curl -fsS -m 10 "http://127.0.0.1:$PORT/v1/models" >/dev/null 2>&1; }

say "campaign 4 start; stages: $STAGES; MemAvailable $(avail) MiB"
[[ -e $SRV ]] && { say "ABORT: $SRV already exists"; exit 2; }
ss -tln | grep -q ":$PORT " && { say "ABORT: port $PORT is in use"; exit 2; }
[[ -n $(docker ps -q --filter name=fp8-tp) ]] && { say "ABORT: an fp8 container is already running"; exit 2; }

# ---- Gemma off (wait for an idle front door, at most 10 min)
for i in $(seq 1 60); do
  st=$(curl -fsS -m 3 http://127.0.0.1:8000/v1/frontdoor/status 2>/dev/null | python3 -c 'import json,sys; f=json.load(sys.stdin)["frontdoor"]; print(f["active_generations"], f["queued_generations"])' 2>/dev/null || echo "down down")
  [[ $st == "0 0" || $st == "down down" ]] && break
  (( i % 6 == 1 )) && say "Gemma front door busy ($st active/queued); waiting"
  sleep 10
done
say "stopping the Gemma service (front door state: $st)"
sudo -A systemctl stop gemma4-26b-q8-quad-frontdoor.service gemma4-26b-q8-quad-backends.service
sudo -A systemctl reset-failed gemma4-26b-q8-quad-frontdoor.service gemma4-26b-q8-quad-backends.service 2>/dev/null
for i in $(seq 1 30); do pgrep -x llama-server >/dev/null || break; sleep 2; done
pgrep -x llama-server >/dev/null && { say "ABORT: llama-server still running"; exit 2; }
sleep 5
say "cards free; MemAvailable $(avail) MiB"

# ---- server (once)
systemctl --user reset-failed ctx-fp8-tp2-server 2>/dev/null
systemd-run --user --unit=ctx-fp8-tp2-server --collect -p WorkingDirectory=$LAB -E B70_GUARD_MIN_AVAILABLE_GIB=1.6 \
  python3 experiments/qwen38-27b-b70/scripts/run-fp8-tp1-server.py --out "$SRV" --port $PORT \
  --image neural-download/vllm-openai-xpu:qwen38-fp8-v0290-r314-state-stride --warmup --keep --startup-timeout 1800 \
  --tp 2 --mem 0.95 --max-model-len 65536 --batched 832 --fa-verify-rows --mtp 5 --draft-int4 \
  --shortlist /opt/draft-shortlists/shortlist-u-v1all-v2top65k.txt \
  --overlay b70-allgather-allreduce --extra-env B70_ALLGATHER_ALLREDUCE=1 \
  --overlay b70-chunked-upload --extra-env B70_CHUNKED_UPLOAD=1 \
  --serve-arg=--enable-auto-tool-choice --serve-arg=--tool-call-parser=qwen3_coder --serve-arg=--reasoning-parser=qwen3 \
  --prefix-cache align --overlay b70-prefix-cache-exact --extra-env B70_PREFIX_CACHE_EXACT=1 \
  --serve-arg=--prefix-cache-retention-interval=13312 \
  --overlay b70-spec-resume-accepted --extra-env B70_SPEC_RESUME_ACCEPTED=1 \
  --overlay b70-gdn-state-width --extra-env B70_GDN_STATE_WIDTH=1 2>&1 | tail -1
ready=0
for i in $(seq 1 120); do
  if server_up; then ready=1; say "server ready after ~$((i*15)) s; MemAvailable $(avail) MiB"; break; fi
  systemctl --user is-active --quiet ctx-fp8-tp2-server || { say "server unit ended before ready"; break; }
  sleep 15
done

run_arm() {  # out_dir sparse_args arm seed [time limit s]
  local od=$1 sa=$2 arm=$3 seed=$4 limit=${5:-0} t0=$SECONDS rc
  say "[$arm s$seed -> $(basename "$od")] start; MemAvailable $(avail) MiB"
  local cmd=(env OUT_DIR="$od" API_BASE="http://127.0.0.1:$PORT/v1" MODEL_NAME=qwen38-27b-fp8 SPARSE_ARGS="$sa" MAX_TOKENS=8192
             ARMS="$arm" KINDS=sparse SEEDS="$seed" SIZES=240000 SUBSET=core ./second-comparison.sh)
  if (( limit > 0 )); then timeout -s INT -k 120 "$limit" "${cmd[@]}" > "$od/arm-$arm-s$seed.out" 2>&1; else "${cmd[@]}" > "$od/arm-$arm-s$seed.out" 2>&1; fi
  rc=$?
  say "[$arm s$seed] done rc=$rc in $(( (SECONDS-t0)/60 )) min; MemAvailable $(avail) MiB"
  grep -h 'ledger score\|^!!!' "$od/arm-$arm-s$seed.out" | grep -v 'B16ira__sparse-memory-t240k-s1' | head -3 | cut -c1-200
}
ok_to_continue() {
  [[ -e $O/STOP-CAMPAIGN ]] && { say "stopped by STOP-CAMPAIGN"; return 1; }
  [[ -n $(faults) ]] && { say "GPU fault line in the kernel log; no further arms"; return 1; }
  server_up || { say "server is gone; no further arms (no restart)"; return 1; }
  return 0
}

if (( ready )); then
  cd "$CTX" || exit 2
  PLAIN="--density 3 --words --probes-every 25 --probes-k 3"
  mkdir -p "$O/client" "$O/client-rules"
  for stage in $STAGES; do
    case $stage in
      S1) ok_to_continue && run_arm "$O/client" "$PLAIN" B32ira 1 ;;
      S2) for arm in B32ira W32 P32 B32ir; do ok_to_continue || break; run_arm "$O/client-rules" "$PLAIN --rules" "$arm" 0; done ;;
      S3) ok_to_continue && run_arm "$O/client" "$PLAIN" C32 0 "$S3_LIMIT_S" ;;
    esac
  done
fi

# ---- server off, gracefully
say "stopping the server; MemAvailable $(avail) MiB"
if systemctl --user is-active --quiet ctx-fp8-tp2-server; then
  touch "$SRV/STOP"
  for i in $(seq 1 40); do systemctl --user is-active --quiet ctx-fp8-tp2-server || break; sleep 5; done
  systemctl --user is-active --quiet ctx-fp8-tp2-server && systemctl --user stop ctx-fp8-tp2-server
fi
sleep 5
[[ -e $SRV/state.json ]] && python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print("server state:", d.get("status"), d.get("error"), "stop_confirmed", d.get("stop_confirmed"))' "$SRV/state.json"
[[ -e $SRV/MEMORY-GUARD.json ]] && say "MEMORY GUARD fired: $(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["reason"])' "$SRV/MEMORY-GUARD.json")"
[[ -e $SRV/memory-guard.jsonl ]] && python3 - "$SRV/memory-guard.jsonl" <<'PY'
import json, sys
a = sorted(json.loads(l)["available"] / 2**30 for l in open(sys.argv[1]) if '"available"' in l)
if a: print(f"host memory available while the server ran: min {a[0]:.2f}  1% {a[len(a)//100]:.2f}  median {a[len(a)//2]:.2f} GiB  ({len(a)} samples)")
PY
for c in $(docker ps -q --filter name=sparse-); do say "removing leftover task container $c"; docker rm -f "$c" >/dev/null 2>&1; done

# ---- analysis (server is down, nothing else on the host needs the memory)
cd "$CTX" && {
  "$PY" ./probe_analysis.py "$O/client" --json "$O/client/probe-analysis-campaign4.json" > "$O/client/probe-analysis-campaign4.txt" 2>&1 || say "plain analysis rc=$?"
  [[ -d $O/client-rules/runs ]] && { "$PY" ./probe_analysis.py "$O/client-rules" --json "$O/client-rules/probe-analysis-rules.json" > "$O/client-rules/probe-analysis-rules.txt" 2>&1 || say "rules analysis rc=$?"; }
  say "plain stream, all rounds pooled"; sed -n '1,12p' "$O/client/probe-analysis-campaign4.txt" | cut -c1-260
  [[ -e $O/client-rules/probe-analysis-rules.txt ]] && { say "rule / procedure stream"; sed -n '1,8p' "$O/client-rules/probe-analysis-rules.txt" | cut -c1-260; }
}

# ---- Gemma back, unless a fault was logged
F=$(faults)
if [[ -n $F ]]; then
  say "GPU FAULT LINES since $START; cards left empty, Gemma NOT restored:"; echo "$F" | head -10 | cut -c1-220
else
  say "kernel log clean since $START; restoring Gemma ($GEMMA_RECIPE)"
  cd "$LAB" && timeout 900 scripts/gemma4-26b-two-b70-recipe.sh "$GEMMA_RECIPE" 2>&1 | grep -E '^backend|^frontdoor|timed out|died'
fi
say "campaign 4 complete"
