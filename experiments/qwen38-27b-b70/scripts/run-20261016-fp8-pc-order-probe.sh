#!/usr/bin/env bash
# 2026-10-16 probe (registered in notes/2026-10-04-fp8-multiuser-prereg.md, "order or timing?", before launch): one
# server in the Q3 setup (one sequence, drafting, prefix caching) plus b70-align-trace, six probe runs of the 64 long
# prompts (S0 S1 SH B0 BT ST), then STOP. Gemma stopped first and put back on its throughput recipe at the end unless
# a GPU fault line was logged.
#   SUDO_ASKPASS=... systemd-run --user ... bash run-20261016-fp8-pc-order-probe.sh
set -uo pipefail
LAB=/home/steve/b70-optimization-lab
cd "$LAB"
export SUDO_ASKPASS=${SUDO_ASKPASS:?set SUDO_ASKPASS}
export B70_GUARD_MIN_AVAILABLE_GIB=1.6
TAG=${TAG:-20261016-pcorder}
O=/mnt/fast-ai/bench-results/fp8-r314-T1-$TAG
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
[[ -e $O ]] && { say "ABORT: $O exists"; exit 2; }
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
  --overlay b70-spec-resume-accepted --extra-env B70_SPEC_RESUME_ACCEPTED=1 \
  --overlay b70-gdn-state-width --extra-env B70_GDN_STATE_WIDTH=1 \
  --overlay b70-align-trace --extra-env B70_ALIGN_TRACE=1 > "$D/owner.log" 2>&1 &
OWNER=$!
for i in $(seq 1 400); do
  s=$(python3 -c "import json;print(json.load(open('$O/state.json')).get('status'))" 2>/dev/null)
  [[ $s == ready ]] && break
  [[ $s == failed || $s == stopped* ]] && { say "server $s"; exit 3; }
  kill -0 $OWNER 2>/dev/null || { say "owner exited before ready"; exit 3; }
  sleep 5
done
[[ $s == ready ]] || { say "server not ready in time"; exit 3; }
say "server ready"
FLAG=$O/cache/b70-align-trace.on
probe() {  # label mode [extra args]
  local label=$1 mode=$2; shift 2
  python3 "$PROBE" --base-url http://127.0.0.1:$PORT --mode "$mode" --label "$label" --out "$D/$label.json" "$@" \
    || { say "probe $label failed"; return 1; }
}
probe S0 seq && probe S1 seq && probe SH shuffle && probe B0 burst &&
  { touch "$FLAG"; probe BT burst; rm -f "$FLAG"; } &&
  { touch "$FLAG"; probe ST seq; rm -f "$FLAG"; }
rm -f "$FLAG"
for pair in "S0 S1" "S0 SH" "S0 B0" "S0 BT" "S0 ST" "B0 BT"; do
  read -r a b <<< "$pair"
  python3 "$PROBE" --compare "$D/$a.json" "$D/$b.json" 2>&1 | tail -1
done
grep -o "b70_[a-z_]*: installed[^(]*\|b70_align_trace[^\"]*" "$O/server.log" 2>/dev/null | sort -u | head
