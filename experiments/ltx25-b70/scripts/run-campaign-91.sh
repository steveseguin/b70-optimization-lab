#!/bin/bash
# packet 91: decode capacity on the idle sampler card (notes/2026-10-03-packet-91-build.md).
#
#   bash run-campaign-91.sh
#
# One server (encoder-server-decode-91, timers on). Placement is selected per
# request by the graph arm, and no gate latches on a mode change:
#   1. warm (3, pipe-samp2-tsh)
#   2. cross-card decode probe: builds the xpu:1 VAE replicas and decodes the
#      ten fixtures' certified latents on xpu:3 and xpu:1 (byte-compared to
#      each other and the stored references). Until it passes, the replica
#      arm's requests are refused without latching anything.
#   3. control arm (30, pipe-samp2-tsh: decode on xpu:3, one worker, preview
#      on the writer thread)
#   4. replica arm (120, pipe-samp2-tsh-rep: even clips xpu:3, odd clips
#      xpu:1, two decode jobs in flight), only if the probe passed.
#
# - sync after each arm and after every 10 completed replica prompts.
# - fresh index bases (highest earlier: 207609 from 90c control).
# - receipts committed, not pushed.
# - stop ONLY on proven quiescence: a successful empty queue response AND a
#   done marker for every submitted sample, decode and preview-save job.
#   Any doubt leaves the server UP and exits non-zero; a failed stop exits 7.
#
# Exit codes: 0 all good; 3 oracle mismatch (server stopped); 1/2 arm
# error/timeout (server up); 4 FAULT (server up); 5 queue not provably empty
# (server up); 6 pipeline jobs not provably finished (server up); 7 stop
# failed; 8 pre-run refusal; 9 probe errored (replica arm skipped, server
# stopped if quiescent). A valid negative probe ("replica not exact" or
# "insufficient memory") skips the replica arm and is reported, exit 0.
#
# Launch the server first (see the 91 note). Do not edit while running.
set -u
# SUPERSEDED 2026-10-03 by run-campaign-91b.sh / prepared-encoder-decode-91b
# (review: replica work outside CAPTURE_LOCK, replicas kept after a failed
# probe, non-persistent buffers unverified, queued preview passed as a path,
# unguarded placement change). Packet 91 was never launched.
echo "run-campaign-91.sh is superseded by run-campaign-91b.sh; refusing" >&2; exit 8
R=/mnt/fast-ai/bench-results/ltx25-baseline-20260913
P=$R/prepared-encoder-decode-91
MANIFEST=d566fc1b5fa80b75dcb259d63e8aaabbffa2911cf84fb6817254a645d1673147
LANE=/home/steve/llm-optimizations/experiments/ltx25-b70
REPO=/home/steve/llm-optimizations
PY=/home/steve/.venvs/ltx25-baseline/bin/python
RUN_NAME=encoder-server-decode-91
RUN=$R/$RUN_NAME
OUT=$LANE/data/decode-91
WARM_BASE=208089; WARM_N=3
CTL_BASE=208189;  CTL_N=30
REP_BASE=208289;  REP_N=120
mkdir -p "$OUT"
step() { echo "=== $(date -u +%FT%TZ) $*"; }
save() { ( cd $REPO && git add "${OUT#$REPO/}" && git commit -q -m "LTX packet 91: $1 receipts

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
arm() { # name graph-arm count index-base [watch]
  step "$1: arm $2, $3 prompts, index base $4"
  local wpid=
  if [ "${5:-}" = watch ]; then rm -f "$SYNC_FLAG"; sync_watch $1 & wpid=$!; fi
  $PY -B $LANE/scripts/run-throughput-fixtures.py $1 --graph $P/graphs/graph-capture-all48-$2.json \
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
  || { step "server is not the 91 packet; refusing"; exit 8; }
pid_is_server $PID $TICKS || { step "server pid $PID does not match $RUN_NAME identity; refusing"; exit 8; }
BW=$(tr '\0' '\n' < /proc/$PID/environ 2>/dev/null | sed -n 's/^LTX_BUSY_WINDOWS=//p')
[ "$BW" = 0 ] && { step "packet 91 measures decode occupancy: launch without LTX_BUSY_WINDOWS=0; refusing"; exit 8; }
step "server pid $PID up, busy timers on"
step "rest 60 s after construction"
sleep 60
arm f91-warm pipe-samp2-tsh $WARM_N $WARM_BASE
[ $ARM_RC -eq 0 ] || { step "warm failed rc=$ARM_RC; server left up for review"; exit $ARM_RC; }
step "settle 30 s before the probe"
sleep 30
queue_empty || { step "queue not provably empty before the probe; server left up"; exit 5; }
step "cross-card decode probe"
$PY -B $LANE/scripts/run-decode-probe.py f91-probe --graph $P/graphs/decode-replica-probe.json --server-run $RUN
PROBE_RC=$?
cp $RUN/decode-probe-f91-probe.json $OUT/ 2>/dev/null
sync
save "probe (rc=$PROBE_RC)"
case $PROBE_RC in
  0)  step "probe: replica exact; replica arm admitted" ;;
  10) step "probe: valid negative outcome (see decode-probe-f91-probe.json); replica arm will be skipped" ;;
  *)  step "probe errored (rc=$PROBE_RC); replica arm will be skipped" ;;
esac
step "settle 30 s"
sleep 30
arm f91-ctl pipe-samp2-tsh $CTL_N $CTL_BASE
CTL_RC=$ARM_RC
if [ $CTL_RC -ne 0 ] && [ $CTL_RC -ne 3 ]; then step "control ended rc=$CTL_RC: server left UP for review"; exit $CTL_RC; fi
if [ $PROBE_RC -ne 0 ]; then
  [ $PROBE_RC -eq 10 ] && finish $CTL_RC
  finish 9
fi
step "settle 60 s between arms"
sleep 60
arm f91-rep pipe-samp2-tsh-rep $REP_N $REP_BASE watch
REP_RC=$ARM_RC
if [ $REP_RC -ne 0 ] && [ $REP_RC -ne 3 ]; then step "replica arm ended rc=$REP_RC: server left UP for review"; exit $REP_RC; fi
[ $CTL_RC -eq 3 ] && finish 3
finish $REP_RC
