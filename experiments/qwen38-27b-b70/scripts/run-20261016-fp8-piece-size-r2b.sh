#!/usr/bin/env bash
# 2026-10-16 piece-size campaign, round 2b only (amendment in notes/2026-10-16-fp8-piece-size-prereg.md).
# The exact prefix cache reads prompts in one-block steps. The prompt-attention kernel works in 256-row query tiles,
# one per head (12 per card on TP2), without a split over the context, so an 832-token step is 48 work-groups on 32
# Xe cores: two waves, the second half empty. 1,280-token blocks fill two waves (60), 2,048 fill three (96).
# Round 1: one server each for 832 (control), 1280, 2048: edit-cost probe at 30K/120K/200K (cold read, repeat,
# edits), then the 64-prompt order probe (paused twice, back to back once; 832: paused once, for timing only).
# Round 2: fresh servers for 832 and the round-1 winner (if its 200K cold read beats 832 by 10 % or more), edit-cost
# probe again. Gemma stopped first and put back at the end unless a GPU fault line was logged.
#   SUDO_ASKPASS=... systemd-run --user ... bash run-20261016-fp8-piece-size.sh
set -uo pipefail
LAB=/home/steve/b70-optimization-lab
cd "$LAB"
export SUDO_ASKPASS=${SUDO_ASKPASS:?set SUDO_ASKPASS}
export B70_GUARD_MIN_AVAILABLE_GIB=1.6
TAG=${TAG:-20261016-piece}
O=
D=$LAB/experiments/qwen38-27b-b70/data/2026-10-16-r314-piece-size
S=$LAB/experiments/qwen38-27b-b70/scripts
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
  O=
}
restore() {
  stop_server
  F=$(faults)
  if [[ -n $F ]]; then say "GPU FAULT LINES since $START; cards left empty, Gemma NOT restored"; echo "$F" | head -10; return; fi
  say "kernel log clean since $START; Gemma back on its throughput recipe"
  timeout 900 scripts/gemma4-26b-two-b70-recipe.sh throughput 2>&1 | grep -E '^backend|^frontdoor|timed out|died'
  say "campaign $TAG complete"
}
wait_port() {  # a stop leaves the port in TIME_WAIT; the launcher's bind probe fails with Errno 98 until it clears
  for i in $(seq 1 120); do ss -tanH "( sport = :$PORT or dport = :$PORT )" | grep -q . || return 0; sleep 2; done
  say "port $PORT still busy"; return 1
}
start_server() {  # name block
  local name=$1 block=$2
  wait_port || return 1
  [[ -n $(faults) ]] && { say "ABORT: GPU fault line before $name"; return 1; }
  O=/mnt/fast-ai/bench-results/fp8-r314-$name-$TAG
  [[ -e $O ]] && { say "ABORT: $O exists"; return 1; }
  local blockarg=() retention=$(( block * (12800 / block) ))
  (( block != 832 )) && blockarg=(--serve-arg=--block-size=$block)
  (( block == 832 )) && retention=13312
  # The context-lane server (campaign 24's flags, seqs 1, MTP 5) with the piece size as the only change.
  python3 $S/run-fp8-tp1-server.py --out "$O" --port $PORT \
    --image neural-download/vllm-openai-xpu:qwen38-fp8-v0290-r314-state-stride --warmup --keep --startup-timeout 1800 \
    --tp 2 --mem 0.95 --max-model-len 262144 --batched $block --seqs 1 --fa-verify-rows --mtp 5 --draft-int4 \
    --shortlist /opt/draft-shortlists/shortlist-u-v1all-v2top65k.txt "${blockarg[@]}" \
    --overlay b70-allgather-allreduce --extra-env B70_ALLGATHER_ALLREDUCE=1 \
    --overlay b70-chunked-upload --extra-env B70_CHUNKED_UPLOAD=1 \
    --prefix-cache align --overlay b70-prefix-cache-exact --extra-env B70_PREFIX_CACHE_EXACT=1 \
    --serve-arg=--prefix-cache-retention-interval=$retention \
    --overlay b70-spec-resume-accepted --extra-env B70_SPEC_RESUME_ACCEPTED=1 \
    --overlay b70-gdn-state-width --extra-env B70_GDN_STATE_WIDTH=1 \
    --overlay b70-exclusive-prefill --extra-env B70_EXCLUSIVE_PREFILL=1 > "$D/owner-$name.log" 2>&1 &
  OWNER=$!
  local s=
  for i in $(seq 1 400); do
    s=$(python3 -c "import json;print(json.load(open('$O/state.json')).get('status'))" 2>/dev/null)
    [[ $s == ready ]] && break
    [[ $s == failed || $s == stopped* ]] && { say "server $name $s"; return 1; }
    kill -0 $OWNER 2>/dev/null || { say "owner $name exited before ready"; return 1; }
    [[ -n $(faults) ]] && { say "GPU fault line during $name start"; return 1; }
    sleep 5
  done
  [[ $s == ready ]] || { say "server $name not ready in time"; return 1; }
  say "server $name ready (block $block, retention $retention)"
  grep -o "Setting attention block size to [0-9]* tokens\|b70_spec_resume_accepted 0.5.0: installed[^)]*)" "$O/server.log" | sort -u
}
edit_probe() {  # label
  python3 $S/qwen38-fp8-edit-cost-probe.py --base-url http://127.0.0.1:$PORT --lengths 30000,120000,200000 \
    --out "$D/edit-$1.json" > "$D/edit-$1.log" 2>&1 || { say "edit probe $1 failed"; tail -3 "$D/edit-$1.log"; return 1; }
  grep "request=cold\|request=edit@0.1 " "$D/edit-$1.log"
}
order_probe() {  # label mode
  python3 $S/probe-pc-order-vs-timing.py --base-url http://127.0.0.1:$PORT --mode "$2" --label "$1" --out "$D/$1.json" \
    || { say "order probe $1 failed"; return 1; }
}
cmp() { python3 $S/probe-pc-order-vs-timing.py --compare "$D/$1.json" "$D/$2.json" > "$D/compare-$1-$2.txt" 2>&1; tail -1 "$D/compare-$1-$2.txt"; }
cold200() { python3 -c "import json;r=json.load(open('$D/edit-$1.json'))['rows'];print([x['first_token_s'] for x in r if x['length']==200000 and x['request']=='cold'][0])"; }

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

# Round 2b (amendment 21:00, registered before it ran): one more fresh K1280 server, edit-cost probe only.
OWNER=; start_server K1280b 1280 && edit_probe K1280b; stop_server
