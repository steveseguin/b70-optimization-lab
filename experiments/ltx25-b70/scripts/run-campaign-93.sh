#!/bin/bash
# Packet 93 (prepared-encoder-window-93): lean conditioning (exact by construction) and the
# suffix-window text encoder (CHANGES OUTPUT AT ROUNDING LEVEL; owner decision pending),
# on ONE server. Build note: notes/2026-10-04-packet-93-build.md.
#
# The operator launches the server first (exact command in the note), with
#   env --default-signal=INT LTX_BUSY_WINDOWS=0 ... serve-encoder.py ... --health-receipt <receipt>
# then starts this runner:
#   bash run-campaign-93.sh
#
# Order on the one server (every client call under `timeout`; waits are on pids and files,
# never on log wording):
#   1. warm 3 (pipe-samp2-tsh)                                         index base 216000
#   2. cross-card decode probe (replica placement must be exact)
#   3. control 40 (pipe-samp2-tsh-rep), existing references            216200
#   4. lean 40 (pipe-samp2-tsh-rep-lean), existing references          216400
#      (exact by construction; the context-hash sentry compares 3 and 4)
#   5. text-window qualification probe (determinism on both encode workers and a repeat,
#      capture proof per bucket, closeness to the 1024 encode within 1e-3)
#   6. two window oracle passes, 13 prompts each (pipe-samp2-tsh-win: the control placement,
#      three fill prompts, so all ten fixtures are emitted)             216600, 216800
#      -> make-window-oracle-93.py: pass 1 == pass 2 on all four tensors per fixture, else
#         the windowed identity is rejected; accepted -> new references stability-01-w93-*
#   7. windowed+lean 120 (pipe-samp2-tsh-rep-wlean) against the NEW references   217000
#   8. summary -> data/window-93/summary.json; graceful stop on proven quiescence.
# A failed or negative probe skips the dependent arms and still stops cleanly.
#
# Exit codes: 0 all good; 3 an oracle mismatch in an arm that must be exact; 1/2 arm
# error/timeout; 4 FAULT latched (server left up for incident review); 5 queue not provably
# empty; 6 pipeline jobs not provably finished; 7 stop failed / pid not the server;
# 8 pre-run refusal; 9 decode probe failed (all replica arms skipped); 11 window probe
# negative or errored (window arms skipped); 12 window oracle rejected (windowed arm skipped).
# Codes 5/6/7 mean the server could NOT be stopped safely and is still up.
# Do not edit while running.
set -u
R=/mnt/fast-ai/bench-results/ltx25-baseline-20260913
P=$R/prepared-encoder-window-93
MANIFEST=997b2913dc612211ee6aa797376e6082e9d929c1b2a45c4cce554de013859efd
LANE=/home/steve/llm-optimizations/experiments/ltx25-b70
REPO=/home/steve/llm-optimizations
PY=/home/steve/.venvs/ltx25-baseline/bin/python
RUN_NAME=encoder-server-window-93
RUN=$R/$RUN_NAME
OUT=$LANE/data/window-93
WINDOW_PREREG=$LANE/data/stability-01-window-prereg.json
WARM_BASE=216000;  WARM_N=3
CTL_BASE=216200;   CTL_N=40
LEAN_BASE=216400;  LEAN_N=40
OR1_BASE=216600;   OR_N=13
OR2_BASE=216800
WLEAN_BASE=217000; WLEAN_N=120
mkdir -p "$OUT"
step() { echo "=== $(date -u +%FT%TZ) $*"; }
save() {
  local paths="${OUT#$REPO/}"
  [ -f "$WINDOW_PREREG" ] && paths="$paths ${WINDOW_PREREG#$REPO/}"
  ( cd $REPO && git add $paths && git commit -q -m "LTX packet 93: $1 receipts

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>" ) >/dev/null 2>&1 && step "committed $1" || step "commit of $1 failed (continuing)"
}

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
ARMS_RUN=""   # "base:n" pairs whose jobs must all have done markers
arm() { # name graph-arm count index-base client-timeout-s watch|- [fixtures]
  step "$1: arm $2, $3 prompts, index base $4"
  local wpid= fx=()
  [ -n "${7:-}" ] && fx=(--fixtures "$7")
  if [ "${6:-}" = watch ]; then rm -f "$SYNC_FLAG"; sync_watch $1 & wpid=$!; fi
  timeout $5 $PY -B $LANE/scripts/run-throughput-fixtures.py $1 --graph $P/graphs/graph-capture-all48-$2.json \
    --arm $2 --server-run $RUN --count $3 --index-base $4 --out $OUT "${fx[@]}"
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
  # Sampler depth 2: prompt i submits sample job base+i and, from i >= 2, the decode job
  # base+i-2 (whatever the decode depth), whose preview the writer saves.
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
  step "server process $PID is gone"
  return 0
}

summarize() {
  timeout 300 $PY -B $LANE/scripts/summarize-campaign-93.py --run $RUN --out $OUT \
    --arm f93-ctl:control --arm f93-lean:lean --arm f93-or1:window-oracle-pass-1 \
    --arm f93-or2:window-oracle-pass-2 --arm f93-wlean:window+lean \
    --pair f93-ctl:f93-lean --pair f93-or1:f93-wlean || step "summary failed (rc=$?)"
}

finish() { # final rc
  local rc=$1 stop_rc i
  stop_when_proven
  stop_rc=$?
  if [ -n "${SAMPLER_PID:-}" ]; then
    # The engine sampler exits by itself once the server pid is gone; give it a moment.
    for i in $(seq 1 10); do [ -e /proc/$SAMPLER_PID ] || break; sleep 1; done
    [ -e /proc/$SAMPLER_PID ] && kill $SAMPLER_PID 2>/dev/null
    wait $SAMPLER_PID 2>/dev/null
  fi
  summarize
  sync
  save "summary (rc=$rc, stop rc=$stop_rc)"
  if [ $stop_rc -ne 0 ]; then
    step "campaign finished (rc=$rc) but the server was NOT stopped (stop rc=$stop_rc)"
    exit $stop_rc
  fi
  step "campaign complete (rc=$rc), server stopped and gone"
  exit $rc
}

# ---- preflight ----------------------------------------------------------------------------------
[ "$MANIFEST" != "__MANIFEST__" ] || { step "runner not pinned to a built packet; refusing"; exit 8; }
[ "$(sha256sum $P/manifest.json | cut -d' ' -f1)" = "$MANIFEST" ] || { step "packet manifest differs from the reviewed one; refusing"; exit 8; }
/home/steve/llm-optimizations/scripts/check-b70-runtime-pm.sh || { step "runtime PM unsafe; refusing to run"; exit 8; }
[ ! -e "$WINDOW_PREREG" ] || { step "$WINDOW_PREREG already exists (an earlier oracle); refusing"; exit 8; }
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
  || { step "server is not the packet 93 build; refusing"; exit 8; }
pid_is_server $PID $TICKS || { step "server pid $PID does not match $RUN_NAME identity; refusing"; exit 8; }
BW=$(tr '\0' '\n' < /proc/$PID/environ 2>/dev/null | sed -n 's/^LTX_BUSY_WINDOWS=//p')
[ "$BW" = 0 ] || { step "packet 93 is a speed comparison: launch the server with LTX_BUSY_WINDOWS=0 (found '$BW'); refusing"; exit 8; }
SIGINT_IGN=$($PY -c "print(int(open('/proc/$PID/status').read().split('SigIgn:')[1].split()[0], 16) >> 1 & 1)")
[ "$SIGINT_IGN" = 0 ] || { step "the server ignores SIGINT (launch it with env --default-signal=INT); refusing"; exit 8; }
HEALTH=$($PY -c "import json;print('yes' if 'health_admission' in json.load(open('$RUN/server-identity.json')) else 'no')")
step "server pid $PID up, busy timers off, SIGINT honoured, same-boot health admission: $HEALTH"
$PY -B $LANE/scripts/sample-gpu-engine-busy.py $PID $OUT/engine-busy.jsonl &
SAMPLER_PID=$!
step "engine-busy sampler pid $SAMPLER_PID (fdinfo only, no device access)"
step "rest 60 s after construction"
sleep 60

# ---- 1. warm, 2. decode probe ---------------------------------------------------------------------
arm f93-warm pipe-samp2-tsh $WARM_N $WARM_BASE 900 -
[ $ARM_RC -eq 0 ] || { step "warm failed rc=$ARM_RC"; finish $ARM_RC; }
step "settle 30 s before the decode probe"
sleep 30
queue_empty || { step "queue not provably empty before the decode probe"; finish 5; }
step "cross-card decode probe"
timeout 1500 $PY -B $LANE/scripts/run-decode-probe.py f93-dprobe --graph $P/graphs/decode-replica-probe.json --server-run $RUN
DPROBE_RC=$?
cp $RUN/decode-probe-f93-dprobe.json $OUT/ 2>/dev/null
sync
save "decode probe (rc=$DPROBE_RC)"
[ $DPROBE_RC -eq 0 ] || { step "decode probe did not pass (rc=$DPROBE_RC): every arm uses the replica placement; skipping all"; finish 9; }
step "settle 30 s"
sleep 30

# ---- 3. control, 4. lean --------------------------------------------------------------------------
arm f93-ctl pipe-samp2-tsh-rep $CTL_N $CTL_BASE 1800 -
CTL_RC=$ARM_RC
[ $CTL_RC -eq 0 ] || [ $CTL_RC -eq 3 ] || { step "control ended rc=$CTL_RC"; finish $CTL_RC; }
step "settle 60 s between arms"
sleep 60
arm f93-lean pipe-samp2-tsh-rep-lean $LEAN_N $LEAN_BASE 1800 -
LEAN_RC=$ARM_RC
[ $LEAN_RC -eq 0 ] || [ $LEAN_RC -eq 3 ] || { step "lean ended rc=$LEAN_RC"; finish $LEAN_RC; }
EXACT_RC=0
{ [ $CTL_RC -eq 3 ] || [ $LEAN_RC -eq 3 ]; } && EXACT_RC=3

# ---- 5. window probe ------------------------------------------------------------------------------
step "settle 30 s before the text-window probe"
sleep 30
queue_empty || { step "queue not provably empty before the window probe"; finish 5; }
step "text-window qualification probe (window CHANGES OUTPUT AT ROUNDING LEVEL; owner decision pending)"
timeout 1800 $PY -B $LANE/scripts/run-text-window-probe.py f93-wprobe --graph $P/graphs/text-window-probe.json --server-run $RUN
WPROBE_RC=$?
cp $RUN/text-window-probe-f93-wprobe.json $OUT/ 2>/dev/null
sync
save "text-window probe (rc=$WPROBE_RC)"
if [ $WPROBE_RC -ne 0 ]; then
  step "text-window probe did not qualify (rc=$WPROBE_RC): window arms skipped"
  [ $EXACT_RC -ne 0 ] && finish $EXACT_RC
  finish 11
fi

# ---- 6. two window oracle passes (compared with the 1024 references only for the record: rc 3 expected)
step "settle 30 s"
sleep 30
arm f93-or1 pipe-samp2-tsh-win $OR_N $OR1_BASE 1200 -
[ $ARM_RC -eq 0 ] || [ $ARM_RC -eq 3 ] || { step "oracle pass 1 ended rc=$ARM_RC"; finish $ARM_RC; }
step "settle 30 s"
sleep 30
arm f93-or2 pipe-samp2-tsh-win $OR_N $OR2_BASE 1200 -
[ $ARM_RC -eq 0 ] || [ $ARM_RC -eq 3 ] || { step "oracle pass 2 ended rc=$ARM_RC"; finish $ARM_RC; }
step "window oracle: pass 1 vs pass 2, new references, distance to the 1024 oracle"
timeout 900 $PY -B $LANE/scripts/make-window-oracle-93.py $OUT/f93-or1-throughput.json $OUT/f93-or2-throughput.json --out $OUT
ORACLE_RC=$?
sync
save "window oracle (rc=$ORACLE_RC)"
if [ $ORACLE_RC -ne 0 ]; then
  step "window oracle not accepted (rc=$ORACLE_RC): windowed arm skipped"
  [ $EXACT_RC -ne 0 ] && finish $EXACT_RC
  finish 12
fi

# ---- 7. windowed + lean against the NEW references -------------------------------------------------
step "settle 60 s"
sleep 60
arm f93-wlean pipe-samp2-tsh-rep-wlean $WLEAN_N $WLEAN_BASE 3600 watch "$WINDOW_PREREG"
WLEAN_RC=$ARM_RC
[ $WLEAN_RC -eq 0 ] || [ $WLEAN_RC -eq 3 ] || { step "windowed+lean ended rc=$WLEAN_RC"; finish $WLEAN_RC; }
[ $EXACT_RC -ne 0 ] && finish $EXACT_RC
finish $WLEAN_RC
