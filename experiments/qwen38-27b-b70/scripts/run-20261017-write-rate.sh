#!/usr/bin/env bash
# 2026-10-17 writing speed against context length (registered in notes/2026-10-17-fp8-writing-attention.md).
# One context-lane server (campaign 24's flags, 832-token pieces), then probe-write-rate-vs-context.py: copy and
# story tasks of 512 tokens at 1K-246K, with the server's draft counters per request. Gemma stopped first and put
# back at the end unless a GPU fault line was logged.
# NAME= names the server arm (default W832); ONE_LAUNCH=1 adds B70_FA_VERIFY_ROWS_ONE_LAUNCH=1 (b70-fa-verify-rows 0.2.0).
#   SUDO_ASKPASS=... systemd-run --user ... bash run-20261017-write-rate.sh
set -uo pipefail
LAB=/home/steve/b70-optimization-lab
cd "$LAB"
export SUDO_ASKPASS=${SUDO_ASKPASS:?set SUDO_ASKPASS}
export B70_GUARD_MIN_AVAILABLE_GIB=1.6
TAG=${TAG:-20261017-write}
O=
D=$LAB/experiments/qwen38-27b-b70/data/2026-10-17-write-rate
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
    --overlay b70-exclusive-prefill --extra-env B70_EXCLUSIVE_PREFILL=1 "${ARM_ARGS[@]}" > "$D/owner-$name.log" 2>&1 &
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
NAME=${NAME:-W832}
ARM_ARGS=()
[[ ${ONE_LAUNCH:-0} == 1 ]] && ARM_ARGS=(--extra-env B70_FA_VERIFY_ROWS_ONE_LAUNCH=1)
OWNER=; start_server $NAME 832 || exit 1
grep -o "b70_fa_verify_rows: enabled.*" "$O/server.log" | sort -u
python3 $S/probe-write-rate-vs-context.py --base-url http://127.0.0.1:$PORT --out "$D/write-$NAME.json" > "$D/write-$NAME.log" 2>&1 \
  || say "write probe failed"
grep "^WRITE" "$D/write-$NAME.log"
grep -o "b70_fa_verify_rows: [0-9]* one-launch.*\|b70_fa_verify_rows: verifier attention.*" "$O/server.log" | sort | uniq -c | tail -3
