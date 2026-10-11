#!/usr/bin/env bash
# Campaign 5 (2026-10-11): the rule fix at the fast scale, then the confirmation at the owner's numbers
# (notes/2026-10-08-long-running-task-prereg.md, "Confirmation": best method and the lossy floor on a 1M history).
#   Phase 1  rules stream, 240K, seed 0, 32K live budget (the campaign-4 S2 task):
#              B32iraR      B32ira + permanent RULE lines in the pinned state (clm_rules.py)
#              B32ira-free  B32ira with free-text notes instead of `name value` lines (clm_freenotes.py)
#              B32iraR4     B32iraR fetching and folding four items per command (speed lever; a tie goes to B32iraR)
#   Phase 2  rules stream, 1M tokens, seed 0, probes every 20 batches x (5 + rule + procedure):
#              the better archive arm of phase 1 by questions right (ties: B32iraR, then B32ira-free; B32ira itself,
#              33/39 in campaign 4, if neither beats it), 32K live budget, no cap; then B32iraR4 as well if it lost
#              at most one question to B32iraR at 240K
#   Phase 3  plain stream, 240K, seed 0: C32, summarise at 75 % of a 32K budget (the production-style method; moved here
#              from campaign 4), cut after C32_CAP_S seconds. It runs before W200 so that a late problem costs the floor,
#              not the baseline.
#              W200  sliding window at the 200K cap, cut after W200_CAP_S seconds
# A cut arm is stopped with SIGINT; its answers file is copied out of the task container every 2 minutes and graded
# with partial_grade.py for the probes it reached (reported as cut, never as a valid trial).
# Server: the round-2..4 two-card recipe at --max-model-len 262144, guard floor 1.6 GiB (owner-approved research value),
# started once, never restarted; stopped only when no request is running (the 2026-10-09 02:11 fault was a stop under load).
# Gemma LAN service: stopped first, the same recipe reinstalled at the end unless a GPU fault line was logged.
set -uo pipefail
LAB=/home/steve/b70-optimization-lab
CTX=$LAB/experiments/qwen38-27b-b70/scripts/context
O=/mnt/fast-ai/bench-results/context-longrun-20261011
SRV=$O/server/tp2-w262144-c5
O10=/mnt/fast-ai/bench-results/context-longrun-20261010
OD1M=$O/client-1m
ODR=$O10/client-rules
ODP=$O10/client
PORT=18196
PY=/mnt/fast-ai/venvs/clm/bin/python
export SUDO_ASKPASS=${SUDO_ASKPASS:?set SUDO_ASKPASS}
GEMMA_RECIPE=${GEMMA_RECIPE:-throughput}
PHASE1=${PHASE1:-B32iraR B32ira-free B32iraR4}
W200_CAP_S=${W200_CAP_S:-5400}
C32_CAP_S=${C32_CAP_S:-4800}
SPPLAIN="--density 3 --words --probes-every 25 --probes-k 3"
SP240="--density 3 --words --probes-every 25 --probes-k 3 --rules"
SP1M="--density 3 --words --probes-every 20 --probes-k 5 --rules"
START=$(date '+%F %T')
FAULT_RE='(xe [0-9a-f:.]+|drm\]).*(Fault response|CAT error|engine reset|gt reset|GPU reset|coredump has been created|Timedout job|timed out|wedged|device lost)|soft lockup'
say() { echo "### $(date +%H:%M:%S) $*"; }
avail() { awk '/^MemAvailable:/ {printf "%d", $2/1024}' /proc/meminfo; }
faults() { journalctl -k --since "$START" --no-pager -o short-iso 2>/dev/null | grep -Ei "$FAULT_RE"; }
server_up() { curl -fsS -m 10 "http://127.0.0.1:$PORT/v1/models" >/dev/null 2>&1; }
wait_idle() {  # no request running on the server for two polls in a row (at most 3 min)
  local r quiet=0
  for i in $(seq 1 60); do
    r=$(curl -fsS -m 5 "http://127.0.0.1:$PORT/metrics" 2>/dev/null | awk '/^vllm:num_requests_(running|waiting)/ {s+=$NF} END {print s+0}')
    if [[ $r == 0 ]]; then quiet=$((quiet+1)); (( quiet >= 2 )) && return 0; else quiet=0; fi
    sleep 3
  done
  return 1
}
mline() {  # server totals so far: prompt tokens, of which served from the prefix cache, and generated tokens
  curl -fsS -m 5 "http://127.0.0.1:$PORT/metrics" 2>/dev/null | awk '/^vllm:prefix_cache_queries_total/ {q=$NF} /^vllm:prefix_cache_hits_total/ {h=$NF} /^vllm:generation_tokens_total/ {g=$NF} END {printf "server totals: prompt %d cached %d generated %d", q, h, g}'
}
env_arm() {  # out_dir size sparse_args VAR=value... command
  local od=$1 size=$2 sp=$3; shift 3
  env OUT_DIR="$od" API_BASE="http://127.0.0.1:$PORT/v1" MODEL_NAME=qwen38-27b-fp8 SPARSE_ARGS="$sp" MAX_TOKENS=8192 \
      KINDS=sparse SEEDS=0 SIZES="$size" SUBSET=core "$@"
}

say "campaign 5 start; phase 1: $PHASE1 (240K rules stream); phase 2: best archive arm at 1M; phase 3: C32 (cap ${C32_CAP_S}s); then W200 at 1M (cap ${W200_CAP_S}s); MemAvailable $(avail) MiB"
[[ -e $SRV ]] && { say "ABORT: $SRV already exists"; exit 2; }
ss -tln | grep -q ":$PORT " && { say "ABORT: port $PORT is in use"; exit 2; }
[[ -n $(docker ps -q --filter name=fp8-tp) ]] && { say "ABORT: an fp8 container is already running"; exit 2; }
mkdir -p "$OD1M/snap" "$ODR/snap" "$ODP/snap"
cd "$CTX" || exit 2

# ---- tasks first (the tokenizer costs host memory; nothing is generated while the server is up)
env_arm "$OD1M" 1000000 "$SP1M" ARMS="B32iraR B32iraR4 B32ira-free B32ira W200" DRY_RUN=1 ./second-comparison.sh > "$OD1M/plan.out" 2>&1 \
  || { say "ABORT: 1M task generation or planning failed"; tail -5 "$OD1M/plan.out"; exit 2; }
env_arm "$ODR" 240000 "$SP240" ARMS="$PHASE1" DRY_RUN=1 ./second-comparison.sh > "$ODR/plan-campaign5.out" 2>&1 \
  || { say "ABORT: phase-1 planning failed"; tail -5 "$ODR/plan-campaign5.out"; exit 2; }
env_arm "$ODP" 240000 "$SPPLAIN" ARMS="C32" DRY_RUN=1 ./second-comparison.sh > "$ODP/plan-campaign5.out" 2>&1 \
  || { say "ABORT: C32 planning failed"; tail -5 "$ODP/plan-campaign5.out"; exit 2; }
TASK1M=$(ls -d "$OD1M"/tasks/sparse-memory/sparse-memory-t*k-s0 | head -1)
say "1M task: $(basename "$TASK1M"); $(grep -o 'n_items = [0-9]*\|n_probes = [0-9]*\|stream_tokens = [0-9]*' "$TASK1M/task.toml" | paste -sd' ')"

# ---- Gemma off (wait for an idle front door, at most 10 min)
st="down down"
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
  --tp 2 --mem 0.95 --max-model-len 262144 --batched 832 --fa-verify-rows --mtp 5 --draft-int4 \
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

snap_loop() {  # out_dir arm: copy /app/answers.json out of the task container every 2 minutes while the arm runs
  local od=$1 arm=$2 c
  while :; do
    sleep 120
    c=$(docker ps --filter name=sparse- --format '{{.Names}}' | head -1)
    [[ -n $c ]] && docker cp "$c:/app/answers.json" "$od/snap/$arm-answers.tmp" >/dev/null 2>&1 \
      && mv "$od/snap/$arm-answers.tmp" "$od/snap/$arm-answers.json" && date +%s > "$od/snap/$arm-answers.at"
  done
}
run_arm() {  # arm cap_seconds out_dir size sparse_args
  local arm=$1 cap=$2 od=$3 size=$4 sp=$5 t0=$SECONDS rc snp
  say "[$arm, $((size/1000))K] start (cap ${cap}s); MemAvailable $(avail) MiB; $(mline)"
  snap_loop "$od" "$arm" & snp=$!
  if (( cap > 0 )); then
    timeout -s INT -k 180 "$cap" env OUT_DIR="$od" API_BASE="http://127.0.0.1:$PORT/v1" MODEL_NAME=qwen38-27b-fp8 SPARSE_ARGS="$sp" MAX_TOKENS=8192 \
      KINDS=sparse SEEDS=0 SIZES="$size" SUBSET=core ARMS="$arm" ./second-comparison.sh > "$od/arm-$arm-c5.out" 2>&1
  else
    env_arm "$od" "$size" "$sp" ARMS="$arm" ./second-comparison.sh > "$od/arm-$arm-c5.out" 2>&1
  fi
  rc=$?
  kill "$snp" 2>/dev/null; wait "$snp" 2>/dev/null
  say "[$arm, $((size/1000))K] done rc=$rc in $(( (SECONDS-t0)/60 )) min; MemAvailable $(avail) MiB; $(mline)"
  grep -h 'ledger score\|^!!!' "$od/arm-$arm-c5.out" | head -3 | cut -c1-200
  if (( rc == 124 || rc == 137 )); then
    say "[$arm] CUT at the time cap; last answers snapshot is $(( $(date +%s) - $(cat "$od/snap/$arm-answers.at" 2>/dev/null || echo 0) )) s old"
    for c in $(docker ps -q --filter name=sparse-); do docker rm -f "$c" >/dev/null 2>&1; done
    echo "$arm $od cut after $(( SECONDS - t0 )) s" >> "$O/CUT.txt"
  fi
  wait_idle || say "[$arm] server still busy after 3 min"
}
correct_of() {  # arm -> questions right on the phase-1 task (0 if void or missing)
  python3 - "$ODR" "$1" <<'PY'
import glob, json, sys
g = glob.glob(f"{sys.argv[1]}/runs/jobs/{sys.argv[2]}__sparse-memory-t240k-s0/*/verifier/details.json")
try:
    d = json.load(open(g[0])); print(0 if d.get("void") else d["counts"]["correct"])
except Exception:
    print(0)
PY
}
ok_to_continue() {
  [[ -e $O/STOP-CAMPAIGN ]] && { say "stopped by STOP-CAMPAIGN"; return 1; }
  [[ -n $(faults) ]] && { say "GPU fault line in the kernel log; no further arms"; return 1; }
  server_up || { say "server is gone; no further arms (no restart)"; return 1; }
  return 0
}

if (( ready )); then
  for arm in $PHASE1; do
    ok_to_continue || break
    run_arm "$arm" 0 "$ODR" 240000 "$SP240"
  done
  best=B32ira; bestn=$(correct_of B32ira)     # 33 of 39 in campaign 4
  say "phase 1: B32ira (campaign 4) $bestn right"
  for arm in B32iraR B32ira-free B32iraR4; do # an arm must beat the best so far, so the earlier one wins a tie
    n=$(correct_of "$arm"); say "phase 1: $arm $n right"
    (( n > bestn )) && { best=$arm; bestn=$n; }
  done
  say "phase 2 archive arm: $best ($bestn right at 240K)"
  ok_to_continue && run_arm "$best" 0 "$OD1M" 1000000 "$SP1M"
  # the four-items-per-command variant also goes to 1M if it lost at most one question at 240K (it is the speed lever)
  n4=$(correct_of B32iraR4); nr=$(correct_of B32iraR)
  if [[ $best != B32iraR4 ]] && (( n4 > 0 && n4 >= nr - 1 )); then
    say "B32iraR4 kept $n4 of B32iraR's $nr at 240K: running it at 1M too"
    ok_to_continue && run_arm B32iraR4 0 "$OD1M" 1000000 "$SP1M"
  else
    say "B32iraR4 not run at 1M ($n4 right at 240K against B32iraR $nr; best arm $best)"
  fi
  ok_to_continue && run_arm C32 "$C32_CAP_S" "$ODP" 240000 "$SPPLAIN"
  ok_to_continue && run_arm W200 "$W200_CAP_S" "$OD1M" 1000000 "$SP1M"
fi

# ---- server off, only when idle
say "stopping the server; MemAvailable $(avail) MiB"
if systemctl --user is-active --quiet ctx-fp8-tp2-server; then
  server_up && { wait_idle || say "server not idle after 3 min; stopping anyway"; }
  sleep 10
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

# ---- analysis (server is down)
"$PY" ./probe_analysis.py "$ODR" --json "$ODR/probe-analysis-rules.json" > "$ODR/probe-analysis-rules.txt" 2>&1 || say "rules analysis rc=$?"
say "rules stream, 240K (campaign 4 arms + phase 1)"; sed -n '1,10p' "$ODR/probe-analysis-rules.txt" | cut -c1-300
"$PY" ./probe_analysis.py "$ODP" --json "$ODP/probe-analysis-campaign5.json" > "$ODP/probe-analysis-campaign5.txt" 2>&1 || say "plain analysis rc=$?"
say "plain stream, 240K, all rounds pooled"; sed -n '1,12p' "$ODP/probe-analysis-campaign5.txt" | cut -c1-300
"$PY" ./probe_analysis.py "$OD1M" --json "$OD1M/probe-analysis.json" > "$OD1M/probe-analysis.txt" 2>&1 || say "1M analysis rc=$?"
say "1M stream, finished trials"; sed -n '1,6p' "$OD1M/probe-analysis.txt" | cut -c1-300
sed -n '/^# 2b/,/^# 3/p' "$OD1M/probe-analysis.txt" | cut -c1-240
if [[ -e $O/CUT.txt ]]; then
  while read -r arm od _; do
    say "cut arm $arm, probes reached before the cut"
    "$PY" ./partial_grade.py "$(ls -d "$od"/tasks/sparse-memory/sparse-memory-t*k-s0 | head -1)" "$od/snap/$arm-answers.json" --json "$od/snap/$arm-partial.json" 2>&1 | cut -c1-240
  done < "$O/CUT.txt"
fi

# ---- Gemma back, unless a fault was logged
F=$(faults)
if [[ -n $F ]]; then
  say "GPU FAULT LINES since $START; cards left empty, Gemma NOT restored:"; echo "$F" | head -10 | cut -c1-220
else
  say "kernel log clean since $START; restoring Gemma ($GEMMA_RECIPE)"
  cd "$LAB" && timeout 900 scripts/gemma4-26b-two-b70-recipe.sh "$GEMMA_RECIPE" 2>&1 | grep -E '^backend|^frontdoor|timed out|died'
fi
say "campaign 5 complete"
