#!/usr/bin/env bash
# 2026-10-17 gates 2-3 of notes/2026-10-17-tp2-package-one-launch-proposal.md (registered there before the run): the
# TP2 package's exact server (R310 image, block 64, 33,024 window, the comm-2 tp2-ag-mtp5 research launch) with
# B70_FA_VERIFY_ROWS_ONE_LAUNCH=1, against the no-MTP references. Servers in order:
#   R0  no MTP: a long-context reference at 24,576 / 30,720 / 32,768 tokens (none exists above 16K)
#   C1  MTP5 + one launch: gate suite (strict, context 2K/8K/16K, quality vs the 2026-09-16 no-MTP references),
#       strict again, then the long lengths against R0
#   O1  only if C1's long lengths differ from R0: MTP5 on 0.1.0 (per-row calls), the same long lengths against R0
# Gemma stopped first and put back at the end unless a GPU fault line was logged.
#   SUDO_ASKPASS=... systemd-run --user ... bash run-20261017-tp2-one-launch-gates.sh
set -uo pipefail
LAB=/home/steve/b70-optimization-lab
cd "$LAB"
export SUDO_ASKPASS=${SUDO_ASKPASS:?set SUDO_ASKPASS}
export B70_GUARD_MIN_AVAILABLE_GIB=1.6
TAG=${TAG:-20261017-tp2gates}
O=
D=$LAB/experiments/qwen38-27b-b70/data/2026-10-17-tp2-one-launch-gates
S=$LAB/experiments/qwen38-27b-b70/scripts
PORT=18193
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
REVIEW=/mnt/fast-ai/bench-results/fp8-review-20260916
G=/mnt/fast-ai/bench-results/fp8-tp2-one-launch-gates-20261017
LONG=24576,30720,32768
R310=sha256:eb8165070409959c9ce4ba4c605ebaf2a39f82ce6b755e408241ab85b08b1e04
start_server() {  # name mtp(0|5) one_launch(0|1)
  local name=$1 mtp=$2 one=$3 args=()
  wait_port || return 1
  [[ -n $(faults) ]] && { say "ABORT: GPU fault line before $name"; return 1; }
  O=$G/server-$name
  [[ -e $O ]] && { say "ABORT: $O exists"; return 1; }
  (( mtp )) && args+=(--mtp 5 --draft-int4 --shortlist /opt/draft-shortlists/shortlist-u-v1all-v2top65k.txt)
  (( one )) && args+=(--extra-env B70_FA_VERIFY_ROWS_ONE_LAUNCH=1)
  # the comm-2 campaign's tp2 arms (the package's qualified research launch)
  python3 $S/run-fp8-tp1-server.py --out "$O" --port $PORT --image $R310 --warmup --keep --startup-timeout 1800 \
    --tp 2 --mem 0.95 --max-model-len 33024 --batched 4096 --fa-verify-rows \
    --overlay b70-allgather-allreduce --extra-env B70_ALLGATHER_ALLREDUCE=1 "${args[@]}" > "$D/owner-$name.log" 2>&1 &
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
  say "server $name ready (mtp $mtp, one launch $one)"
  grep -o "b70_fa_verify_rows: enabled.*" "$O/server.log" | sort -u
}
long() {  # name [baseline summary]
  local b=(); [[ -n ${2:-} ]] && b=(--baseline "$2")
  python3 $S/bench-prefill-followup.py --base-url http://127.0.0.1:$PORT --model qwen38-27b-fp8 --out "$G/$1-long" \
    --corpus $LAB/experiments/qwen38-27b-b70/data/2026-09-17-long-corpus/corpus.json --lengths $LONG \
    --max-model-len 33024 --max-tokens 128 --repeats 2 --timeout 900 "${b[@]}" > "$D/$1-long.log" 2>&1
  python3 -c "import json;s=json.load(open('$G/$1-long/summary.json'));print('$1 long: passed', s.get('passed'), 'error', s.get('error'))" 2>&1
}

mkdir -p "$D" "$G"
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

OWNER=; start_server R0 0 0 || exit 1
long R0; stop_server
REF_LONG=$G/R0-long/summary.json
[[ -f $REF_LONG ]] || { say "no R0 long reference; stopping"; exit 1; }
OWNER=; start_server C1 5 1 || exit 1
python3 $S/fp8-gate-suite.py --base-url http://127.0.0.1:$PORT --name C1 --out "$G/C1-gates" --gates strict,context,quality \
  --ref-strict $REVIEW/tp2-mtp0-strict --ref-context $REVIEW/tp2-mtp0-context/summary.json \
  --ref-quality $REVIEW/tp2-mtp0-quality.json --max-model-len 33024 > "$D/C1-gates.log" 2>&1; say "C1 gate suite exit $?"
python3 $S/fp8-gate-suite.py --base-url http://127.0.0.1:$PORT --name C1-run2 --out "$G/C1-gates-run2" --gates strict \
  --ref-strict $REVIEW/tp2-mtp0-strict --max-model-len 33024 > "$D/C1-gates-run2.log" 2>&1; say "C1 strict run 2 exit $?"
long C1 $REF_LONG
c1=$(python3 -c "import json;print(json.load(open('$G/C1-long/summary.json')).get('passed'))" 2>/dev/null)
stop_server
if [[ $c1 != True ]]; then
  say "C1 long lengths differ from R0: the 0.1.0 arm"
  OWNER=; start_server O1 5 0 && long O1 $REF_LONG; stop_server
fi
for f in "$G"/C1-gates/gate-suite.json "$G"/C1-gates-run2/gate-suite.json; do [[ -f $f ]] && cp "$f" "$D/$(basename $(dirname $f)).gate-suite.json"; done
for n in R0 C1 O1; do [[ -f $G/$n-long/summary.json ]] && cp "$G/$n-long/summary.json" "$D/$n-long.summary.json"; done
