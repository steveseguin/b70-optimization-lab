#!/bin/bash
# packet 92a: is the pipeline bound by its shared interpreter?
# (notes/2026-10-03-process-split-design.md section 1; notes/2026-10-03-packet-92a-build.md)
#
#   bash run-campaign-92a.sh
#
# One server (encoder-server-gil-92a), launched with LTX_BUSY_WINDOWS=0.
# Control placement throughout (decode on xpu:3 only, as 90c):
#   1. warm (3, pipe-samp2-tsh)
#   2. idle baseline: knob drain, 30 s with no request, knob (lock-wait idle histogram)
#   3. four arms of 40 prompts (37 verified clips each), switch interval
#      5 ms, 1 ms, 20 ms, 5 ms; the knob applies each interval only when no
#      pipeline job is queued or running
#   4. knob back to 5 ms, then the proven-quiescence stop.
#
# - sync after each arm and every 10 completed prompts of each arm.
# - fresh index bases (highest earlier: 208809 from 91b).
# - every client call is bounded by `timeout`.
# - receipts committed, not pushed.
# - an oracle mismatch (rc 3) in an arm is recorded and the next arm runs;
#   any other arm failure tries the knob back to 5 ms (the server also restores
#   5 ms when a node latches) and leaves the server UP with a non-zero exit.
#
# Exit codes: 0 all good; 3 an arm had an oracle mismatch (server stopped);
# 1/2/124 arm error/timeout (server up); 4 FAULT (server up); 5 queue not
# provably empty or a knob refused (server up); 6 jobs not provably finished
# (server up); 7 stop failed; 8 pre-run refusal.
#
# Launch the server first (see the 92a note). Do not edit while running.
set -u
R=/mnt/fast-ai/bench-results/ltx25-baseline-20260913
P=$R/prepared-encoder-gil-92a
MANIFEST=b201580c08ea6e540a4b2bee70b1fd4a4e8480c254c37391e5be07773d329fb9
LANE=/home/steve/llm-optimizations/experiments/ltx25-b70
REPO=/home/steve/llm-optimizations
PY=/home/steve/.venvs/ltx25-baseline/bin/python
RUN_NAME=encoder-server-gil-92a
RUN=$R/$RUN_NAME
OUT=$LANE/data/gil-92a
WARM_BASE=209089; WARM_N=3
ARM_N=40
# arm name, switch interval ms, index base
ARMS_PLAN="s05a:5:209189 s01:1:209289 s20:20:209389 s05b:5:209489"
mkdir -p "$OUT"
step() { echo "=== $(date -u +%FT%TZ) $*"; }
save() { ( cd $REPO && git add "${OUT#$REPO/}" && git commit -q -m "LTX packet 92a: $1 receipts

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
ARMS_RUN=""   # "base n" pairs whose jobs must all have done markers
arm() { # name graph-arm count index-base client-timeout-s [watch]
  step "$1: arm $2, $3 prompts, index base $4"
  local wpid=
  if [ "${6:-}" = watch ]; then rm -f "$SYNC_FLAG"; sync_watch $1 & wpid=$!; fi
  timeout $5 $PY -B $LANE/scripts/run-throughput-fixtures.py $1 --graph $P/graphs/graph-capture-all48-$2.json \
    --arm $2 --server-run $RUN --count $3 --index-base $4 --out $OUT
  ARM_RC=$?
  ARMS_RUN="$ARMS_RUN $4:$3"
  if [ -n "$wpid" ]; then touch "$SYNC_FLAG" || kill $wpid; wait $wpid; rm -f "$SYNC_FLAG"; fi
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

missing_markers() { # every expected done marker that does not exist
  # Sampler depth 2: prompt i submits sample job base+i and, from i >= 2, the
  # decode job base+i-2 (whatever the decode depth), whose preview the writer
  # saves (all packet-91 arms save previews).
  local spec base n i
  for spec in $ARMS_RUN; do
    base=${spec%%:*}; n=${spec##*:}
    for i in $(seq 0 $((n - 1))); do
      [ -f $RUN/pipeline-done-sample-$((base + i)).json ] || echo "sample-$((base + i))"
      if [ $i -ge 2 ]; then
        [ -f $RUN/pipeline-done-decode-$((base + i - 2)).json ] || echo "decode-$((base + i - 2))"
        [ -f $RUN/pipeline-done-save-$((base + i - 2)).json ] || echo "save-$((base + i - 2))"
      fi
    done
  done
}

stop_when_proven() {
  [ -f $R/FAULT.json ] && { step "FAULT latched: server left up for incident review"; return 4; }
  step "quiescence 1/2: waiting for a successful, empty queue response (up to 5 min)"
  local ok=0 i missing
  for i in $(seq 1 30); do queue_empty && { ok=1; break; }; sleep 10; done
  [ $ok = 1 ] || { step "queue never PROVABLY empty (request failed or work pending): server left UP"; return 5; }
  step "quiescence 2/2: waiting for done markers of every submitted sample/decode/save job (up to 10 min)"
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

finish() { # final endure-like rc
  local rc=$1 stop_rc
  stop_when_proven
  stop_rc=$?
  sync
  if [ $stop_rc -ne 0 ]; then
    step "campaign finished (rc=$rc) but the server was NOT stopped cleanly (rc=$stop_rc)"
    exit $stop_rc
  fi
  step "campaign complete (rc=$rc), server stopped"
  exit $rc
}

[ "$(sha256sum $P/manifest.json | cut -d' ' -f1)" = "$MANIFEST" ] || { step "packet manifest differs from the reviewed one; refusing"; exit 8; }
/home/steve/llm-optimizations/scripts/check-b70-runtime-pm.sh || { step "runtime PM unsafe; refusing to run"; exit 8; }
step "waiting for server health"
for i in $(seq 1 360); do
  [ -f $R/FAULT.json ] && { step FAULT latched; exit 4; }
  curl -sf -m 10 http://127.0.0.1:8188/queue >/dev/null 2>&1 && break
  sleep 5
done
curl -sf -m 10 http://127.0.0.1:8188/queue >/dev/null || { step server never answered; exit 8; }
[ -f $RUN/server-identity.json ] || { step "no $RUN/server-identity.json: the server on 8188 is not $RUN_NAME; refusing"; exit 8; }
PID=$($PY -c "import json;print(json.load(open('$RUN/server-identity.json'))['pid'])")
TICKS=$($PY -c "import json;print(json.load(open('$RUN/server-identity.json'))['proc_start_ticks'])")
[ "$($PY -c "import json;print(json.load(open('$RUN/server-identity.json'))['source_packet_manifest_sha256'])")" = "$MANIFEST" ] \
  || { step "server is not the 92a packet; refusing"; exit 8; }
pid_is_server $PID $TICKS || { step "server pid $PID does not match $RUN_NAME identity; refusing"; exit 8; }
BW=$(tr '\0' '\n' < /proc/$PID/environ 2>/dev/null | sed -n 's/^LTX_BUSY_WINDOWS=//p')
[ "$BW" = 0 ] || { step "packet 92a measures interpreter contention: launch the server with LTX_BUSY_WINDOWS=0 (found '$BW'); refusing"; exit 8; }
step "server pid $PID up, busy timers off"
step "rest 60 s after construction"
sleep 60
knob() { # name ms -> 0 applied, 10 refused, other error
  timeout 400 $PY -B $LANE/scripts/run-scheduler-knob.py $1 --ms $2 --graph $P/graphs/scheduler-knob.json --server-run $RUN
  local rc=$?
  cp $RUN/scheduler-knob-$1.json $OUT/ 2>/dev/null
  return $rc
}
restore_and_exit() { # rc message
  step "$2"
  knob f92a-restore-after-failure 5 || step "knob restore to 5 ms failed (the server restores 5 ms itself on a latched failure)"
  sync
  exit $1
}

arm f92a-warm pipe-samp2-tsh $WARM_N $WARM_BASE 900
[ $ARM_RC -eq 0 ] || { step "warm failed rc=$ARM_RC; server left up for review"; exit $ARM_RC; }
step "settle 30 s"
sleep 30
queue_empty || { step "queue not provably empty before the idle baseline; server left up"; exit 5; }
knob f92a-drain 5 || restore_and_exit 5 "knob refused before the idle baseline; server left UP"
step "idle baseline: 30 s with no request"
sleep 30
knob f92a-idle 5 || restore_and_exit 5 "knob refused at the idle baseline; server left UP"
sync
save "idle baseline"
WORST=0
for spec in $ARMS_PLAN; do
  name=${spec%%:*}; rest=${spec#*:}; ms=${rest%%:*}; base=${rest##*:}
  step "settle 30 s before arm $name"
  sleep 30
  queue_empty || restore_and_exit 5 "queue not provably empty before arm $name; server left UP"
  knob f92a-$name-knob $ms || restore_and_exit 5 "knob refused for arm $name ($ms ms); server left UP"
  arm f92a-$name pipe-samp2-tsh $ARM_N $base 2400 watch
  if [ $ARM_RC -eq 3 ]; then
    step "arm $name: ORACLE MISMATCH recorded (rc=3); continuing"
    WORST=3
  elif [ $ARM_RC -ne 0 ]; then
    restore_and_exit $ARM_RC "arm $name ended rc=$ARM_RC: server left UP for review"
  fi
done
step "settle 30 s"
sleep 30
knob f92a-restore 5 || restore_and_exit 5 "final knob to 5 ms refused; server left UP"
sync
save "final knob"
finish $WORST
