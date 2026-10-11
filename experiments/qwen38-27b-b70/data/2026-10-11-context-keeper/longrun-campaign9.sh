#!/usr/bin/env bash
# Campaign 9 (2026-10-11): the proxy after its fixes. Arm X32b is X32 (the plain agent with no context budget of its
# own, served through tools/ctxkeeper at a 32K live window) with the proxy as of lab commit c16585171: the notes call
# uses the same reasoning effort as other calls and has 8,192 tokens, a rejected notes reply is logged and asked for
# again without thinking, a turn gets eight archive searches and the client is never handed a recall call, a history
# is recognised by what was said, thinking stays on while a question is open, an identical repeated call is flagged.
#   1  X32b  rules 240K, seed 1     the run that exposed the notes-call defect (X32: 42/46 in 47 min; N32j 46/46 in 16)
#   2  X32b  rules 240K, seed 0     (X32: 37/39 in 21 min; N32j 39/39 in 15)
#   3  X32b  rules 1M, seed 0, cut after X_1M_CAP_S    the proxy at the owner's scale (N32j: 226/228 in 83 min)
# A cut arm is stopped with SIGINT; its answers file is copied out of the task container every 2 minutes (every copy
# kept) and graded with partial_grade.py for the probes it reached (reported as cut, never as a valid trial).
# Server: the two-card recipe at --max-model-len 262144, guard floor 1.6 GiB (owner-approved research value), started
# once, never restarted; stopped only when no request is running. Gemma LAN service: stopped first, the same recipe
# reinstalled at the end unless a GPU fault line was logged.
set -uo pipefail
LAB=/home/steve/b70-optimization-lab
CTX=$LAB/experiments/qwen38-27b-b70/scripts/context
O=/mnt/fast-ai/bench-results/context-longrun-20261011
SRV=$O/server/tp2-w262144-c9
O10=/mnt/fast-ai/bench-results/context-longrun-20261010
OD1M=$O/client-1m
ODR=$O10/client-rules
ODP=$O10/client
PORT=18196
PY=/mnt/fast-ai/venvs/clm/bin/python
export SUDO_ASKPASS=${SUDO_ASKPASS:?set SUDO_ASKPASS}
GEMMA_RECIPE=${GEMMA_RECIPE:-throughput}
STAGE6=${STAGE6:-B32iraR B32ira}
X_BAR=${X_BAR:-33}
X_1M_CAP_S=${X_1M_CAP_S:-6600}
PPORT=18200
THINK_RE='(?m)^(?:ASK \S+?:|QUERY \S+|GET \S+)|^PROBE:|STREAM END|NOT RUN|Traceback|\(exit_code=[1-9-]'
RECITE_RE='(?m)^(?:ASK \S+?:|QUERY \S+|GET \S+)'
UNTIL_RE='(?m)^ITEM \d+/\d+ \(UPDATE\)'
KEEPER_1M_CAP_S=${KEEPER_1M_CAP_S:-7800}
HIST_CAP_S=${HIST_CAP_S:-3600}
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
env_arm() {  # out_dir size sparse_args seed VAR=value... command
  local od=$1 size=$2 sp=$3 seed=$4; shift 4
  env OUT_DIR="$od" API_BASE="http://127.0.0.1:$PORT/v1" MODEL_NAME=qwen38-27b-fp8 SPARSE_ARGS="$sp" MAX_TOKENS=8192 \
      CTXKEEPER_BASE="http://127.0.0.1:$PPORT/v1" KINDS=sparse SEEDS="$seed" SIZES="$size" SUBSET=core "$@"
}

say "campaign 9 start; X32b (proxy after fixes) seed 1, seed 0, then 1M (cap ${X_1M_CAP_S}s); MemAvailable $(avail) MiB"
ss -tln | grep -q ":$PPORT " && { say "ABORT: proxy port $PPORT is in use"; exit 2; }
[[ -e $SRV ]] && { say "ABORT: $SRV already exists"; exit 2; }
ss -tln | grep -q ":$PORT " && { say "ABORT: port $PORT is in use"; exit 2; }
[[ -n $(docker ps -q --filter name=fp8-tp) ]] && { say "ABORT: an fp8 container is already running"; exit 2; }
mkdir -p "$OD1M/snap/kept" "$ODR/snap/kept" "$ODP/snap/kept"
cd "$CTX" || exit 2

# ---- tasks first (the tokenizer costs host memory; nothing is generated while the server is up)
[[ -d $ODR/tasks/sparse-memory/sparse-memory-t240k-s1 ]] || { say "ABORT: the seed-1 rules task is missing (generate it before launch)"; exit 2; }
env_arm "$OD1M" 1000000 "$SP1M" 0 CTXKEEPER_BASE="http://127.0.0.1:$PPORT/v1" ARMS="X32b" DRY_RUN=1 ./second-comparison.sh > "$OD1M/plan-campaign9.out" 2>&1 \
  || { say "ABORT: 1M planning failed"; tail -5 "$OD1M/plan-campaign9.out"; exit 2; }
env_arm "$ODR" 240000 "$SP240" "0 1" CTXKEEPER_BASE="http://127.0.0.1:$PPORT/v1" ARMS="X32b" DRY_RUN=1 ./second-comparison.sh > "$ODR/plan-campaign9.out" 2>&1 \
  || { say "ABORT: rules-stream planning failed"; tail -5 "$ODR/plan-campaign9.out"; exit 2; }
env_arm "$ODP" 240000 "$SPPLAIN" 0 ARMS="C32" DRY_RUN=1 ./second-comparison.sh > "$ODP/plan-campaign9.out" 2>&1 \
  || { say "ABORT: C32 planning failed"; tail -5 "$ODP/plan-campaign9.out"; exit 2; }
TASK1M=$(ls -d "$OD1M"/tasks/sparse-memory/sparse-memory-t*k-s0 | head -1)
say "tasks ready: $(basename "$TASK1M"), rules 240K seeds 0 and 1, plain 240K seed 0"

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

keep_best() {  # snap_dir tag: the new copy becomes the current one unless it lost probe answers the current one has
  # (campaign 5: the agent rewrote its answers file at the final item and the next copy overwrote the good one)
  python3 - "$1/$2-answers.tmp" "$1/$2-answers.json" <<'PY'
import json, os, re, sys
new, cur = sys.argv[1:3]
def probes(path):
    try:
        return {k for k in json.load(open(path)) if re.fullmatch(r"p\d+_\d+", k)}
    except Exception:
        return None
n, c = probes(new), probes(cur)
if n is not None and (c is None or c <= n):
    os.replace(new, cur)
else:
    os.replace(new, cur.replace("-answers.json", "-answers-after-loss.json"))
PY
}
snap_loop() {  # snap_dir tag: copy /app/answers.json out of the task container every 2 minutes while the arm runs
  local sd=$1 tag=$2 c
  while :; do
    sleep 120
    c=$(docker ps --filter name=sparse- --format '{{.Names}}' | head -1)
    [[ -n $c ]] && docker cp "$c:/app/answers.json" "$sd/$tag-answers.tmp" >/dev/null 2>&1 \
      && cp "$sd/$tag-answers.tmp" "$sd/kept/$tag-$(date +%H%M%S).json" \
      && keep_best "$sd" "$tag" && date +%s > "$sd/$tag-answers.at"
  done
}
start_proxy() {  # state tag: one fresh proxy per X32 arm
  systemctl --user reset-failed ctx-keeper-proxy 2>/dev/null
  systemd-run --user --unit=ctx-keeper-proxy --collect -p WorkingDirectory=$LAB python3 tools/ctxkeeper/ctxkeeper.py \
    --upstream "http://127.0.0.1:$PORT" --port $PPORT --budget 32768 --reply-reserve 2048 --headroom 1024 --target-ratio 0.6 \
    --notes-thinking on --effort medium --think-when "$THINK_RE" --think-until "$UNTIL_RE" --recite-when "$RECITE_RE" --state-dir "$O/proxy-state/$1" 2>&1 | tail -1
  for i in $(seq 1 30); do curl -fsS -m 3 "http://127.0.0.1:$PPORT/v1/models" >/dev/null 2>&1 && return 0; sleep 1; done
  say "proxy did not come up"; return 1
}
stop_proxy() {  # status file: keep the proxy's own counters, then stop it
  curl -fsS -m 5 "http://127.0.0.1:$PPORT/ctxkeeper/status" > "$1" 2>/dev/null
  systemctl --user stop ctx-keeper-proxy 2>/dev/null
  python3 - "$1" <<'PY'
import json, sys
try:
    for v in json.load(open(sys.argv[1])).values():
        print(f"proxy: cuts {v['cuts']}, messages archived {v['cut']}, recalls {v['recalls']}, notes failed {v['notes_failed']}, "
              f"rules put back {v['rules_put_back']}, restarts {v.get('restarts', 0)}, chars per token {v['ratio']}")
except Exception as exc:
    print("proxy: no status:", exc)
PY
}
run_x() {  # cap_seconds out_dir size sparse_args seed: X32 through a fresh proxy
  local tag="c9-X32b-$(($3/1000))k-s$5"
  start_proxy "$tag" || return 1
  run_arm X32b "$1" "$2" "$3" "$4" "$5"
  stop_proxy "$2/proxy-status-$tag.json"
}
run_arm() {  # arm cap_seconds out_dir size sparse_args [seed]
  local arm=$1 cap=$2 od=$3 size=$4 sp=$5 seed=${6:-0} t0=$SECONDS rc snp
  local tag="c9-$arm-$((size/1000))k-s$seed"      # one snapshot series per arm, stream and seed of this campaign
  rm -f "$od/snap/$tag-answers.json" "$od/snap/$tag-answers.at" "$od/snap/$tag-answers.tmp"
  say "[$arm, $((size/1000))K, seed $seed] start (cap ${cap}s); MemAvailable $(avail) MiB; $(mline)"
  snap_loop "$od/snap" "$tag" & snp=$!
  if (( cap > 0 )); then
    timeout -s INT -k 180 "$cap" env OUT_DIR="$od" API_BASE="http://127.0.0.1:$PORT/v1" MODEL_NAME=qwen38-27b-fp8 SPARSE_ARGS="$sp" MAX_TOKENS=8192 \
      CTXKEEPER_BASE="http://127.0.0.1:$PPORT/v1" KINDS=sparse SEEDS="$seed" SIZES="$size" SUBSET=core ARMS="$arm" ./second-comparison.sh > "$od/arm-$arm-s$seed-c9.out" 2>&1
  else
    env_arm "$od" "$size" "$sp" "$seed" ARMS="$arm" ./second-comparison.sh > "$od/arm-$arm-s$seed-c9.out" 2>&1
  fi
  rc=$?
  kill "$snp" 2>/dev/null; wait "$snp" 2>/dev/null
  say "[$arm, $((size/1000))K, seed $seed] done rc=$rc in $(( (SECONDS-t0)/60 )) min; MemAvailable $(avail) MiB; $(mline)"
  grep -h 'ledger score\|^!!!' "$od/arm-$arm-s$seed-c9.out" | grep -v 'B16ira__sparse-memory-t240k-s1' | head -3 | cut -c1-200
  if (( rc == 124 || rc == 137 )); then
    say "[$arm] CUT at the time cap; last answers snapshot is $(( $(date +%s) - $(cat "$od/snap/$tag-answers.at" 2>/dev/null || echo 0) )) s old"
    for c in $(docker ps -q --filter name=sparse-); do docker rm -f "$c" >/dev/null 2>&1; done
    echo "$arm $od $seed $tag cut after $(( SECONDS - t0 )) s" >> "$O/CUT9.txt"
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
  [[ -e $O/STOP-CAMPAIGN9 ]] && { say "stopped by STOP-CAMPAIGN9"; return 1; }
  [[ -n $(faults) ]] && { say "GPU fault line in the kernel log; no further arms"; return 1; }
  server_up || { say "server is gone; no further arms (no restart)"; return 1; }
  return 0
}

if (( ready )); then
  ok_to_continue && run_x 0 "$ODR" 240000 "$SP240" 1
  ok_to_continue && run_x 0 "$ODR" 240000 "$SP240" 0
  ok_to_continue && run_x "$X_1M_CAP_S" "$OD1M" 1000000 "$SP1M" 0
fi
systemctl --user stop ctx-keeper-proxy 2>/dev/null

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
say "rules stream, 240K, seeds pooled"; sed -n '1,12p' "$ODR/probe-analysis-rules.txt" | cut -c1-300
"$PY" ./probe_analysis.py "$ODP" --json "$ODP/probe-analysis-campaign9.json" > "$ODP/probe-analysis-campaign9.txt" 2>&1 || say "plain analysis rc=$?"
say "plain stream, 240K, all rounds pooled"; sed -n '1,13p' "$ODP/probe-analysis-campaign9.txt" | cut -c1-300
"$PY" ./probe_analysis.py "$OD1M" --json "$OD1M/probe-analysis.json" > "$OD1M/probe-analysis.txt" 2>&1 || say "1M analysis rc=$?"
say "1M stream, finished trials"; sed -n '1,6p' "$OD1M/probe-analysis.txt" | cut -c1-300
sed -n '/^# 2b/,/^# 3/p' "$OD1M/probe-analysis.txt" | cut -c1-240
if [[ -e $O/CUT9.txt ]]; then
  while read -r arm od seed tag _; do
    say "cut arm $arm (seed $seed), probes reached before the cut"
    "$PY" ./partial_grade.py "$(ls -d "$od"/tasks/sparse-memory/sparse-memory-t*k-s"$seed" | head -1)" "$od/snap/$tag-answers.json" --json "$od/snap/$tag-partial.json" 2>&1 | cut -c1-240
  done < "$O/CUT9.txt"
fi

# ---- Gemma back, unless a fault was logged
F=$(faults)
if [[ -n $F ]]; then
  say "GPU FAULT LINES since $START; cards left empty, Gemma NOT restored:"; echo "$F" | head -10 | cut -c1-220
else
  say "kernel log clean since $START; restoring Gemma ($GEMMA_RECIPE)"
  cd "$LAB" && timeout 900 scripts/gemma4-26b-two-b70-recipe.sh "$GEMMA_RECIPE" 2>&1 | grep -E '^backend|^frontdoor|timed out|died'
fi
say "campaign 9 complete"
