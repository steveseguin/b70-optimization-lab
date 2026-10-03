#!/bin/bash
# packet 92b: decode in its own process (notes/2026-10-03-packet-92b-build.md).
# Question: is per-process GPU runtime state the shared resource? If moving
# decode into a child process makes the sampler AND encode jobs >= 8 % faster
# at equal exactness, the process split continues; otherwise it stops.
#
#   bash run-campaign-92b.sh
#
# One server (encoder-server-decodeproc-92b) launched with LTX_BUSY_WINDOWS=0
# and LTX_DECODE_CHILD=1 (the server spawns the decode child at custom-node
# import, before it serves). Default switch interval only; no knob.
#   1. warm (3, pipe-samp2-tsh, in-process decode)
#   2. child probe: the child decodes the ten fixtures; refusal stops the child
#   3. control arm (40, pipe-samp2-tsh: in-process decode on xpu:3)
#   4. child arm (120, pipe-samp2-tsh-child: decode in the child), only if
#      the probe passed
#   5. proven-quiescence stop: queue empty + every done marker, then the
#      child is stopped cooperatively and must have exited, then one SIGINT
#      to the launcher.
#
# - sync after each arm and every 10 completed prompts of each arm.
# - fresh index bases (highest earlier: 209900 reserved by 92a/92p).
# - every client call bounded by `timeout`.
# - receipts committed, not pushed.
#
# Exit codes: 0 all good; 3 oracle mismatch (server stopped); 1/2/124 arm
# error/timeout (server up); 4 FAULT (server up); 5 queue not provably empty
# (server up); 6 jobs not provably finished (server up); 7 child or server
# stop failed; 8 pre-run refusal; 9 probe errored (child arm skipped).
#
# Launch the server first (see the 92b note). Do not edit while running.
set -u
R=/mnt/fast-ai/bench-results/ltx25-baseline-20260913
P=$R/prepared-encoder-decodeproc-92b
MANIFEST=988884d33df4bf9c35cfadb0edd331377940ec2d3bcf3e0c720183cac54e051f
LANE=/home/steve/llm-optimizations/experiments/ltx25-b70
REPO=/home/steve/llm-optimizations
PY=/home/steve/.venvs/ltx25-baseline/bin/python
RUN_NAME=encoder-server-decodeproc-92b
RUN=$R/$RUN_NAME
OUT=$LANE/data/decodeproc-92b
WARM_BASE=210089; WARM_N=3
CTL_BASE=210189;  CTL_N=40
CHILD_BASE=210289; CHILD_N=120
mkdir -p "$OUT"
step() { echo "=== $(date -u +%FT%TZ) $*"; }
save() { ( cd $REPO && git add "${OUT#$REPO/}" && git commit -q -m "LTX packet 92b: $1 receipts

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
  step "quiescence proven; cooperative stop of the decode child first"
  timeout 300 $PY -B $LANE/scripts/run-decode-child-op.py f92b-child-stop --op stop \
    --graph $P/graphs/decode-child-stop.json --server-run $RUN
  local crc=$?
  cp $RUN/decode-child-stop-f92b-child-stop.json $OUT/ 2>/dev/null
  if [ $crc -ne 0 ]; then step "decode child did NOT exit (rc=$crc): server left UP"; return 7; fi
  if [ -n "${CHILD_PID:-}" ] && [ -e /proc/$CHILD_PID ] && \
     tr '\0' ' ' < /proc/$CHILD_PID/cmdline 2>/dev/null | grep -q ltx_decode_child.py; then
    step "decode child pid $CHILD_PID still present after its stop receipt: server left UP"; return 7
  fi
  step "decode child exited; graceful stop: one SIGINT to launcher pid $PID"
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
  || { step "server is not the 92b packet; refusing"; exit 8; }
pid_is_server $PID $TICKS || { step "server pid $PID does not match $RUN_NAME identity; refusing"; exit 8; }
BW=$(tr '\0' '\n' < /proc/$PID/environ 2>/dev/null | sed -n 's/^LTX_BUSY_WINDOWS=//p')
[ "$BW" = 0 ] || { step "packet 92b is a speed comparison: launch the server with LTX_BUSY_WINDOWS=0 (found '$BW'); refusing"; exit 8; }
DC=$(tr '\0' '\n' < /proc/$PID/environ 2>/dev/null | sed -n 's/^LTX_DECODE_CHILD=//p')
[ "$DC" = 1 ] || { step "launch the server with LTX_DECODE_CHILD=1 (found '$DC'); refusing"; exit 8; }
[ -f $RUN/decode-child-startup.json ] || { step "no decode-child startup receipt; refusing"; exit 8; }
CHILD_PID=$($PY -c "import json;s=json.load(open('$RUN/decode-child-startup.json')).get('state') or {};print(s.get('pid') or '')")
CHILD_ERR=$($PY -c "import json;s=json.load(open('$RUN/decode-child-startup.json'));print((s.get('state') or {}).get('error') or s.get('error') or '')")
cp $RUN/decode-child-startup.json $OUT/ 2>/dev/null
[ -n "$CHILD_ERR" ] && step "decode child failed to start ($CHILD_ERR); the probe will record child-unavailable"
step "server pid $PID up, busy timers off, decode child pid ${CHILD_PID:-none}"
step "rest 60 s after construction"
sleep 60
arm f92b-warm pipe-samp2-tsh $WARM_N $WARM_BASE 900
[ $ARM_RC -eq 0 ] || { step "warm failed rc=$ARM_RC; server left up for review"; exit $ARM_RC; }
step "settle 30 s before the child probe"
sleep 30
queue_empty || { step "queue not provably empty before the probe; server left up"; exit 5; }
step "decode-child probe"
timeout 1500 $PY -B $LANE/scripts/run-decode-child-op.py f92b-probe --op probe \
  --graph $P/graphs/decode-child-probe.json --server-run $RUN
PROBE_RC=$?
cp $RUN/decode-child-probe-f92b-probe.json $OUT/ 2>/dev/null
sync
save "child probe (rc=$PROBE_RC)"
case $PROBE_RC in
  0)  step "probe: child exact; child arm admitted" ;;
  10) step "probe: valid negative outcome (see decode-child-probe-f92b-probe.json); child stopped, child arm skipped" ;;
  *)  step "probe errored (rc=$PROBE_RC); child arm skipped" ;;
esac
step "settle 30 s"
sleep 30
arm f92b-ctl pipe-samp2-tsh $CTL_N $CTL_BASE 2400
CTL_RC=$ARM_RC
if [ $CTL_RC -ne 0 ] && [ $CTL_RC -ne 3 ]; then step "control ended rc=$CTL_RC: server left UP for review"; exit $CTL_RC; fi
if [ $PROBE_RC -ne 0 ]; then
  [ $PROBE_RC -eq 10 ] && finish $CTL_RC
  finish 9
fi
step "settle 60 s between arms"
sleep 60
arm f92b-child pipe-samp2-tsh-child $CHILD_N $CHILD_BASE 3600 watch
CHILD_RC=$ARM_RC
if [ $CHILD_RC -ne 0 ] && [ $CHILD_RC -ne 3 ]; then step "child arm ended rc=$CHILD_RC: server left UP for review"; exit $CHILD_RC; fi
[ $CTL_RC -eq 3 ] && finish 3
finish $CHILD_RC
