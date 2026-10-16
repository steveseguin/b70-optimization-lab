#!/usr/bin/env bash
# 2026-10-16 probe (registered in notes/2026-10-04-fp8-multiuser-prereg.md, "order or timing?" and its 19:04
# amendment, before launch). A: a server in the Q3 setup (one sequence, drafting, prefix caching) with
# b70-spec-resume-accepted 0.5.0's new-request reset OFF and b70-align-trace on: paused suite order twice, paused
# shuffle, burst. B: the same server with the reset ON: paused, burst, burst shuffled, paused shuffle. C: the
# standard two-user P1 arm (three passes, long suite) with the reset on. Gemma stopped first and put back on its
# throughput recipe at the end unless a GPU fault line was logged.
#   SUDO_ASKPASS=... systemd-run --user ... bash run-20261016-fp8-pc-order-probe.sh
set -uo pipefail
LAB=/home/steve/b70-optimization-lab
cd "$LAB"
export SUDO_ASKPASS=${SUDO_ASKPASS:?set SUDO_ASKPASS}
export B70_GUARD_MIN_AVAILABLE_GIB=1.6
TAG=${TAG:-20261016-pcorder}
O=
D=$LAB/experiments/qwen38-27b-b70/data/2026-10-16-r314-pcorder
PROBE=$LAB/experiments/qwen38-27b-b70/scripts/probe-pc-order-vs-timing.py
PORT=18196
START=$(date '+%F %T')
FAULT_RE='(xe [0-9a-f:.]+|drm\]).*(Fault response|CAT error|engine reset|gt reset|GPU reset|coredump has been created|Timedout job|timed out|wedged|device lost)|soft lockup'
say() { echo "### $(date +%H:%M:%S) $*"; }
faults() { sudo -A journalctl -k --since "$START" --no-pager -o short-iso 2>/dev/null | grep -Ei "$FAULT_RE"; }
stop_server() {
  [[ -d $O ]] || return
  touch "$O/STOP"
  for i in $(seq 1 90); do [[ -n ${OWNER:-} ]] && kill -0 "$OWNER" 2>/dev/null || break; sleep 2; done
  say "server stopped: $(python3 -c "import json;s=json.load(open('$O/state.json'));print(s.get('status'), s.get('stop_confirmed'))" 2>/dev/null)"
}
restore() {
  stop_server
  F=$(faults)
  if [[ -n $F ]]; then say "GPU FAULT LINES since $START; cards left empty, Gemma NOT restored"; echo "$F" | head -10; return; fi
  say "kernel log clean since $START; Gemma back on its throughput recipe"
  timeout 900 scripts/gemma4-26b-two-b70-recipe.sh throughput 2>&1 | grep -E '^backend|^frontdoor|timed out|died'
  say "probe $TAG complete"
}

mkdir -p "$D"
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
trap restore EXIT
for i in $(seq 1 30); do pgrep -x llama-server >/dev/null || break; sleep 2; done
pgrep -x llama-server >/dev/null && { say "ABORT: llama-server still running"; exit 2; }
sleep 5
# The Q3 server (fp8-r314-Q3-20261016-pcwhy/tp2-pb8-pure-pc-faseq-mtp5-s1-owner.command.json) plus the trace overlay.
wait_port() {  # a stop leaves the port in TIME_WAIT; the launcher's bind probe fails with Errno 98 until it clears
  for i in $(seq 1 120); do ss -tanH "( sport = :$PORT or dport = :$PORT )" | grep -q . || return 0; sleep 2; done
  say "port $PORT still busy"; return 1
}
start_server() {  # name fresh(0|1)
  wait_port || return 1
  O=/mnt/fast-ai/bench-results/fp8-r314-$1-$TAG
  [[ -e $O ]] && { say "ABORT: $O exists"; return 1; }
  python3 experiments/qwen38-27b-b70/scripts/run-fp8-tp1-server.py --out "$O" --port $PORT \
    --image sha256:eb8165070409959c9ce4ba4c605ebaf2a39f82ce6b755e408241ab85b08b1e04 --warmup --keep --startup-timeout 1800 \
    --tp 2 --mem 0.95 --max-model-len 33024 --batched 4096 --fa-verify-rows --mtp 5 --draft-int4 \
    --shortlist /opt/draft-shortlists/shortlist-u-v1all-v2top65k.txt \
    --overlay b70-allgather-allreduce --extra-env B70_ALLGATHER_ALLREDUCE=1 \
    --overlay b70-exclusive-prefill --extra-env B70_EXCLUSIVE_PREFILL=1 --extra-env B70_EXCLUSIVE_PREFILL_BATCH=8 \
    --overlay b70-fa-decode-per-seq --extra-env B70_FA_DECODE_PER_SEQ=1 \
    --overlay b70-chunked-upload --extra-env B70_CHUNKED_UPLOAD=1 \
    --batched 832 --prefix-cache align --overlay b70-prefix-cache-exact --extra-env B70_PREFIX_CACHE_EXACT=1 \
    --serve-arg=--prefix-cache-retention-interval=6656 --seqs 1 \
    --image neural-download/vllm-openai-xpu:qwen38-fp8-v0290-r314-state-stride \
    --overlay b70-spec-resume-accepted --extra-env B70_SPEC_RESUME_ACCEPTED=1 --extra-env B70_SPEC_RESUME_FRESH=$2 \
    --overlay b70-gdn-state-width --extra-env B70_GDN_STATE_WIDTH=1 \
    --overlay b70-align-trace --extra-env B70_ALIGN_TRACE=1 > "$D/owner-$1.log" 2>&1 &
  OWNER=$!
  local s=
  for i in $(seq 1 400); do
    s=$(python3 -c "import json;print(json.load(open('$O/state.json')).get('status'))" 2>/dev/null)
    [[ $s == ready ]] && break
    [[ $s == failed || $s == stopped* ]] && { say "server $1 $s"; return 1; }
    kill -0 $OWNER 2>/dev/null || { say "owner $1 exited before ready"; return 1; }
    sleep 5
  done
  [[ $s == ready ]] || { say "server $1 not ready in time"; return 1; }
  touch "$O/cache/b70-align-trace.on"
  say "server $1 ready (new-request count reset $2), tracing"
  grep -o "b70_spec_resume_accepted 0.5.0: installed[^)]*)\|b70_align_trace 0.1.0: installed[^)]*)" "$O/server.log" | sort -u
}
probe() {  # label mode [extra args]
  local label=$1 mode=$2; shift 2
  python3 "$PROBE" --base-url http://127.0.0.1:$PORT --mode "$mode" --label "$label" --out "$D/$label.json" "$@" \
    || { say "probe $label failed"; return 1; }
}
cmp() { python3 "$PROBE" --compare "$D/$1.json" "$D/$2.json" > "$D/compare-$1-$2.txt" 2>&1; tail -1 "$D/compare-$1-$2.txt"; }
PARTS=${PARTS:-A B C}
if [[ $PARTS == *A* ]]; then
# A: fix off (0.4.0 behaviour), traced
start_server A0 0 || exit 3
probe AS0 seq && probe AS1 seq && probe ASH shuffle && probe AB0 burst || exit 3
stop_server
cmp AS0 AS1; cmp AS0 ASH; cmp AS0 AB0
cp "$O"/cache/b70-align-trace/rank0-*.jsonl "$D/trace-A0.jsonl" 2>/dev/null
fi
if [[ $PARTS == *B* ]]; then
# B: fix on, traced
OWNER=
start_server B1 1 || exit 3
probe BS0 seq && probe BB0 burst && probe BB1 burst-shuffle && probe BSH shuffle || exit 3
stop_server
cmp BS0 BB0; cmp BS0 BB1; cmp BS0 BSH; cmp AS0 BS0
cp "$O"/cache/b70-align-trace/rank0-*.jsonl "$D/trace-B1.jsonl" 2>/dev/null
grep -o "b70_spec_resume_accepted: first new-request count reset[^)]*)" "$O/server.log" | head -2
O=
fi
[[ $PARTS == *C* ]] || exit 0
wait_port || exit 3
# C: the standard two-user check (the P1 arm) with the fix
export MU_MODE=longsweep MU_PURE=1 MU_FA_PER_SEQ=1 MU_PREFILL_BATCH=8 MU_STATE_WIDTH=1 MU_SPEC_RESUME=1 MU_SEQS=2 \
  MU_IMAGE=neural-download/vllm-openai-xpu:qwen38-fp8-v0290-r314-state-stride MU_SKIP_SHORT=1 MU_LONG_REPEATS=3 \
  MU_MTP=1 MU_PREFIX_CACHE=1
say "arm C2 (P1 with the fix) -> /mnt/fast-ai/bench-results/fp8-r314-C2-$TAG"
CAMPAIGN_OUT=/mnt/fast-ai/bench-results/fp8-r314-C2-$TAG python3 experiments/qwen38-27b-b70/scripts/run-20261004-fp8-multiuser-campaign.py \
  || say "arm C2 failed rc=$?"
