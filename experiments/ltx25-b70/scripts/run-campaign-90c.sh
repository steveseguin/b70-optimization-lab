#!/bin/bash
# packet 90c: packet-90 sentries + busy-window timers + decode vae/save split
# (notes/2026-10-03-packet-90c-build.md). Arms as f90: warm (3), settle,
# 120-prompt endurance over the ten fixtures.
#
#   bash run-campaign-90c.sh [timed|control]
#
# timed   (default): server encoder-server-busy-90c, timers on.
# control          : server encoder-server-busy-90c-ctl launched with
#                    LTX_BUSY_WINDOWS=0 (timers off, sentries on), same packet.
#
# - sync after each arm and after every 10 completed endure prompts.
# - fresh index bases (90/90b used 202989/203089 and 204989/205089).
# - receipts committed, not pushed.
# - the server is stopped ONLY when quiescence is positively proven: the
#   queue request succeeds and is empty, AND every sample and decode job
#   this campaign submitted has written its worker-side done marker
#   (pipeline-done-<stage>-<index>.json). Then one SIGINT to the verified
#   launcher pid (ComfyUI runs in-process), bounded wait, no escalation.
#   Any doubt (queue unreachable, a marker missing, FAULT latched, an arm
#   error) leaves the server UP and exits non-zero. A failed stop exits 7.
#
# Exit codes: 0 all good; 3 endure oracle mismatch (server stopped);
# 1/2 arm error/timeout (server up); 4 FAULT (server up); 5 queue not
# provably empty (server up); 6 pipeline jobs not provably finished
# (server up); 7 stop failed; 8 pre-run refusal.
#
# Launch the server first (see the 90c note). Do not edit while running.
set -u
MODE=${1:-timed}
R=/mnt/fast-ai/bench-results/ltx25-baseline-20260913
P=$R/prepared-encoder-busy-90c
MANIFEST=80559bde4971229ab0a2ce927ab412ae1a2ca5fde5494abdef5f1da801a22be7
LANE=/home/steve/llm-optimizations/experiments/ltx25-b70
REPO=/home/steve/llm-optimizations
PY=/home/steve/.venvs/ltx25-baseline/bin/python
case $MODE in
  timed)   RUN_NAME=encoder-server-busy-90c;     TAG=f90c;     WARM_BASE=206989; ENDURE_BASE=207089; WANT_ENV=on;  OUT_NAME=busy-90c ;;
  control) RUN_NAME=encoder-server-busy-90c-ctl; TAG=f90c-ctl; WARM_BASE=207389; ENDURE_BASE=207489; WANT_ENV=off; OUT_NAME=busy-90c-ctl ;;
  *) echo "usage: $0 [timed|control]"; exit 8 ;;
esac
RUN=$R/$RUN_NAME
OUT=$LANE/data/$OUT_NAME
WARM_N=3
ENDURE_N=120
mkdir -p "$OUT"
step() { echo "=== $(date -u +%FT%TZ) $*"; }
save() { ( cd $REPO && git add "${OUT#$REPO/}" && git commit -q -m "LTX packet 90c ($MODE): $1 receipts

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>" ) >/dev/null 2>&1 && step "committed $1" || step "commit of $1 failed (continuing)"; }

SYNC_FLAG=$OUT/.sync-watch-stop
sync_watch() { # prefix
  local last=0 n
  while [ ! -e "$SYNC_FLAG" ]; do
    n=$(ls -d $R/requests/$1-*/history.json 2>/dev/null | wc -l)
    if [ $((n / 10)) -gt $((last / 10)) ]; then sync; step "sync at $n completed $1 prompts"; last=$n; fi
    sleep 2
  done
}

ARM_RC=0
arm() { # name graph-arm count index-base [watch]
  step "$1: arm $2, $3 prompts, index base $4"
  local wpid=
  if [ "${5:-}" = watch ]; then rm -f "$SYNC_FLAG"; sync_watch $1 & wpid=$!; fi
  $PY -B $LANE/scripts/run-throughput-fixtures.py $1 --graph $P/graphs/graph-capture-all48-$2.json \
    --arm $2 --server-run $RUN --count $3 --index-base $4 --out $OUT
  ARM_RC=$?
  if [ -n "$wpid" ]; then touch "$SYNC_FLAG"; wait $wpid; rm -f "$SYNC_FLAG"; fi
  sync
  step "$1 finished rc=$ARM_RC; synced"
  if [ $ARM_RC -ne 0 ]; then save "$1 (rc=$ARM_RC)"; else save "$1"; fi
}

pid_is_server() { # pid ticks: the launcher we verified, not a reused pid
  [ -r /proc/$1/cmdline ] || return 1
  tr '\0' ' ' < /proc/$1/cmdline | grep -q -- "serve-encoder.py .*--run-name $RUN_NAME " || \
    tr '\0' ' ' < /proc/$1/cmdline | grep -q -- "serve-encoder.py .*--run-name $RUN_NAME\$" || return 1
  [ "$($PY -c "import sys;print(open('/proc/$1/stat').read().split(') ')[1].split()[19])")" = "$2" ]
}

queue_empty() { # 0 only when a queue request succeeded and showed nothing running or pending
  local q
  q=$(curl -sf -m 10 http://127.0.0.1:8188/queue) || return 1
  echo "$q" | $PY -c "import json,sys
d=json.load(sys.stdin)
sys.exit(0 if d.get('queue_running') == [] and d.get('queue_pending') == [] else 1)"
}

missing_markers() { # prints every expected done marker that does not exist
  # Sampler depth 2, decode depth 1: prompt i submits sample job base+i and,
  # from i >= 2, decode job base+i-2. Every submitted job must have finished.
  local base n i
  for spec in "$WARM_BASE $WARM_N" "$ENDURE_BASE $ENDURE_N"; do
    set -- $spec; base=$1; n=$2
    for i in $(seq 0 $((n - 1))); do
      [ -f $RUN/pipeline-done-sample-$((base + i)).json ] || echo "sample-$((base + i))"
      [ $i -ge 2 ] && { [ -f $RUN/pipeline-done-decode-$((base + i - 2)).json ] || echo "decode-$((base + i - 2))"; }
    done
  done
}

stop_when_proven() {
  [ -f $R/FAULT.json ] && { step "FAULT latched: server left up for incident review"; return 4; }
  step "quiescence 1/2: waiting for a successful, empty queue response (up to 5 min)"
  local ok=0 i missing
  for i in $(seq 1 30); do queue_empty && { ok=1; break; }; sleep 10; done
  [ $ok = 1 ] || { step "queue never PROVABLY empty (request failed or work pending): server left UP"; return 5; }
  step "quiescence 2/2: waiting for done markers of every submitted sample/decode job (up to 10 min)"
  for i in $(seq 1 60); do
    missing=$(missing_markers | wc -l)
    [ "$missing" = 0 ] && break
    sleep 10
  done
  if [ "$missing" != 0 ]; then
    step "$missing pipeline jobs have no done marker (still running or failed): server left UP"
    missing_markers | head -10
    return 6
  fi
  sleep 10
  sync
  [ -f $R/FAULT.json ] && { step "FAULT latched: server left up"; return 4; }
  queue_empty || { step "queue no longer provably empty: server left UP"; return 5; }
  pid_is_server $PID $TICKS || { step "pid $PID is no longer the $RUN_NAME launcher: nothing stopped"; return 7; }
  step "quiescence proven; graceful stop: one SIGINT to launcher pid $PID"
  kill -INT $PID
  for i in $(seq 1 36); do [ -e /proc/$PID ] || break; sleep 5; done
  sync
  if [ -e /proc/$PID ]; then
    step "STOP FAILED: pid $PID alive 180 s after SIGINT; NOT escalating (bare kills have faulted the GPU)"
    return 7
  fi
  step "server stopped"
  return 0
}

[ "$(sha256sum $P/manifest.json | cut -d' ' -f1)" = "$MANIFEST" ] || { step "packet manifest differs from the reviewed one; refusing"; exit 8; }
/home/steve/llm-optimizations/scripts/check-b70-runtime-pm.sh || { step "runtime PM unsafe; refusing to run"; exit 8; }
step "mode $MODE: waiting for server health"
for i in $(seq 1 360); do
  [ -f $R/FAULT.json ] && { step FAULT latched; exit 4; }
  curl -sf http://127.0.0.1:8188/queue >/dev/null 2>&1 && break
  sleep 5
done
curl -sf http://127.0.0.1:8188/queue >/dev/null || { step server never answered; exit 8; }
[ -f $RUN/server-identity.json ] || { step "no $RUN/server-identity.json: the server on 8188 is not $RUN_NAME; refusing"; exit 8; }
PID=$($PY -c "import json;print(json.load(open('$RUN/server-identity.json'))['pid'])")
TICKS=$($PY -c "import json;print(json.load(open('$RUN/server-identity.json'))['proc_start_ticks'])")
[ "$($PY -c "import json;print(json.load(open('$RUN/server-identity.json'))['source_packet_manifest_sha256'])")" = "$MANIFEST" ] \
  || { step "server is not the 90c packet; refusing"; exit 8; }
pid_is_server $PID $TICKS || { step "server pid $PID does not match $RUN_NAME identity; refusing"; exit 8; }
BW=$(tr '\0' '\n' < /proc/$PID/environ 2>/dev/null | sed -n 's/^LTX_BUSY_WINDOWS=//p')
HAVE_ENV=on; [ "$BW" = 0 ] && HAVE_ENV=off
[ "$HAVE_ENV" = "$WANT_ENV" ] || { step "mode $MODE needs busy timers $WANT_ENV, server has LTX_BUSY_WINDOWS='$BW'; refusing"; exit 8; }
step "server pid $PID up, busy timers $HAVE_ENV"
# Rest after construction: the 17:26 segfault hit 14 s into warm, right after
# construction's own component loads. Give the machine a quiet minute.
step "rest 60 s after construction"
sleep 60
arm $TAG-warm pipe-samp2-tsh $WARM_N $WARM_BASE
[ $ARM_RC -eq 0 ] || { step "warm failed rc=$ARM_RC; server left up for review"; exit $ARM_RC; }
# Settle gap: the freezes hit at the warm->endure load step-change.
step "settle 60 s between arms"
sleep 60
arm $TAG-endure pipe-samp2-tsh $ENDURE_N $ENDURE_BASE watch
ENDURE_RC=$ARM_RC
if [ $ENDURE_RC -ne 0 ] && [ $ENDURE_RC -ne 3 ]; then
  step "endure ended rc=$ENDURE_RC (execution error/timeout): server left UP for review"
  exit $ENDURE_RC
fi
stop_when_proven
STOP_RC=$?
sync
if [ $STOP_RC -ne 0 ]; then
  step "campaign finished (endure rc=$ENDURE_RC) but the server was NOT stopped cleanly (rc=$STOP_RC)"
  exit $STOP_RC
fi
step "campaign complete (endure rc=$ENDURE_RC), server stopped"
exit $ENDURE_RC
