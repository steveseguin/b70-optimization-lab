#!/bin/bash
# Packet 95 (prepared-encoder-workers-95): more sampler clips in flight. The transformer layout
# (LTX_SAMPLER_PLACEMENT) and the number of sampler workers (LTX_SAMPLER_WORKERS) are fixed per
# server launch; this runner takes both:
#
#   bash run-campaign-95.sh <two-way|shard3-c|shard4-a> <2|3|4>
#
# Operator order: two-way 2 (control), two-way 3, shard4-a 3, shard4-a 4, shard3-c 3; each on its
# own server launch (commands in notes/2026-10-04-packet-95-build.md):
#   env --default-signal=INT LTX_BUSY_WINDOWS=0 LTX_SAMPLER_PLACEMENT=<layout> LTX_SAMPLER_WORKERS=<N> ...
#
# Per server, in order (every client call under `timeout`; waits on pids and files):
#   1. text-window probe (serial; loads the components, captures the encoder graphs)
#   2. serial capture pass: for each sampler worker k = 0..N-1, pin the next sampler job to worker k
#      (graph sampler-pin), send one prompt alone, wait for its sample job. Before worker k >= 2
#      captures, worker-headroom-95.py checks that every card has the 2 GiB floor plus that
#      worker's estimated graph memory; if not, the combination is skipped cleanly (exit 18)
#      before anything is captured. Then every worker must hold every block graph (coverage).
#   3. decode probe (serial; VAEs loaded explicitly onto xpu:3, replica built on xpu:1)
#   4. freeze (coverage for N workers, expected residents, 2 GiB floor); then no capture, no load
#   5. post-freeze self-check: N+4 prompts of the timed arm (two clips emitted: one native, one
#      replica decode), selfcheck-94f.py must find no refusal (exit 17)
#   6. placement probe: 13 prompts, ten fixtures byte for byte against the w93c references
#   7. timed: 120 prompts of the window+lean replica arm with sampler depth N
#      (pipe-samp2-tsh-rep-wlean, -s3, -s4), against the w93c references
#   8. summary (clips in flight observed, engine busy per card, sampler job median, context-sentry
#      gate probe vs timed); graceful stop on proven quiescence (or idle-state after a failed arm).
#
# Index bases: 244000 + 1000 x combination index (two-way 2/3: 0/1, shard4-a 3/4: 2/3, shard3-c 3: 4,
# two-way 4: 5, shard3-c 2/4: 6/7, shard4-a 2: 8); capture pass base+10k, self-check base+200,
# placement probe base+400, timed base+600.
#
# Exit codes as 94f, plus 18: not enough memory for another sampler worker (combination skipped).
# Codes 5/6/7 mean the server could NOT be stopped safely and is still up.
# Do not edit while running.
set -u
LAYOUT=${1:-}; WORKERS=${2:-}
case "$LAYOUT:$WORKERS" in
  two-way:2) IDX=0 ;; two-way:3) IDX=1 ;; shard4-a:3) IDX=2 ;; shard4-a:4) IDX=3 ;; shard3-c:3) IDX=4 ;;
  two-way:4) IDX=5 ;; shard3-c:2) IDX=6 ;; shard3-c:4) IDX=7 ;; shard4-a:2) IDX=8 ;;
  *) echo "usage: run-campaign-95.sh <two-way|shard3-c|shard4-a> <2|3|4>"; exit 8 ;;
esac
PLACEMENT=$LAYOUT
MODE=$LAYOUT-w$WORKERS
TAG=$(echo $LAYOUT | tr -d -)w$WORKERS
BASE=$((244000 + 1000 * IDX))
CAP_BASE=$BASE; SELF_BASE=$((BASE + 200)); PROBE_BASE=$((BASE + 400)); TIMED_BASE=$((BASE + 600))
TIMED_N=120; PROBE_N=13; SELF_N=$((WORKERS + 4))
case $WORKERS in 2) TIMED_ARM=pipe-samp2-tsh-rep-wlean ;; *) TIMED_ARM=pipe-samp2-tsh-rep-wlean-s$WORKERS ;; esac
R=/mnt/fast-ai/bench-results/ltx25-baseline-20260913
P=$R/prepared-encoder-workers-95
MANIFEST=97c1b4172f66d009af7c88b0b3f0241d24df937ce56a43c27cee6b226b81a32d
LANE=/home/steve/llm-optimizations/experiments/ltx25-b70
REPO=/home/steve/llm-optimizations
PY=/home/steve/.venvs/ltx25-baseline/bin/python
RUN_NAME=encoder-server-workers-95-$MODE
RUN=$R/$RUN_NAME
BASE_OUT=$LANE/data/workers-95
OUT=$BASE_OUT/$MODE
PREREG=$LANE/data/stability-01-window-prereg.json
mkdir -p "$OUT"
step() { echo "=== $(date -u +%FT%TZ) [$MODE] $*"; }
save() {
  ( cd $REPO && git add "${OUT#$REPO/}" && git commit -q -m "LTX packet 95 ($MODE): $1 receipts

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
ARMS_RUN=""   # arm prefixes; their actually-submitted jobs must all have done markers
arm() { # name graph-arm count index-base client-timeout-s watch|- [fixtures]
  step "$1: arm $2, $3 prompts, index base $4"
  local wpid= fx=()
  [ -n "${7:-}" ] && fx=(--fixtures "$7")
  # 94b: registered BEFORE the client starts, so an interrupted arm is still awaited at the stop
  # (missing-markers-93b.py expects only what the client actually submitted).
  ARMS_RUN="$ARMS_RUN $1"
  if [ "${6:-}" = watch ]; then rm -f "$SYNC_FLAG"; sync_watch $1 & wpid=$!; fi
  timeout $5 $PY -B $LANE/scripts/run-throughput-fixtures.py $1 --graph $P/graphs/graph-capture-all48-$2.json \
    --arm $2 --server-run $RUN --count $3 --index-base $4 --out $OUT "${fx[@]}"
  ARM_RC=$?
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

missing_markers() { # done markers missing for jobs the server actually queued (93b)
  timeout 120 $PY -B $LANE/scripts/missing-markers-93b.py --root $R --run $RUN $ARMS_RUN || echo "marker-check-failed"
}

IDLE_N=0
pipeline_idle_once() { # 0 only if the queue is empty and the coverage node reports busy=0, running=0
  local name rc
  IDLE_N=$((IDLE_N + 1)); name=f95-$TAG-idle$IDLE_N
  queue_empty || return 1
  timeout 120 $PY -B $LANE/scripts/run-capture-freeze-94.py $name --graph $P/graphs/sampler-capture-coverage.json --server-run $RUN >/dev/null 2>&1
  $PY -c "import json,sys;d=json.load(open('$RUN/sampler-capture-coverage-$name.json'));sys.exit(0 if d.get('pipeline_busy')==0 and d.get('pipeline_running')==0 else 1)" 2>/dev/null || return 1
  queue_empty
}

pipeline_idle_stable() { # three idle readings over 30 s
  pipeline_idle_once || return 1
  sleep 15
  pipeline_idle_once || return 1
  sleep 15
  pipeline_idle_once
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
    step "$missing pipeline jobs have no done marker (still running or failed)"
    missing_markers | head -10
    if pipeline_idle_stable; then
      step "no job queued, unfinished or executing in any stage, stable for 30 s: the missing markers belong to failed jobs"
    else
      step "pipeline idleness not established: server left UP"
      return 6
    fi
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

SUMMARY_RC=0
summarize() { # the context-sentry gate (probe pass vs timed arm): a failure fails the campaign (exit 14)
  local arms="--arm f95-$TAG-probe:placement-probe --arm f95-$TAG-timed:timed"
  timeout 300 $PY -B $LANE/scripts/summarize-campaign-93.py --run $RUN --out $OUT $arms \
    --pair f95-$TAG-probe:f95-$TAG-timed
  SUMMARY_RC=$?
  [ $SUMMARY_RC -eq 0 ] || step "SUMMARY / CONTEXT-SENTRY GATE FAILED (rc=$SUMMARY_RC)"
}

FINISHING=0
finish() { # final rc; runs at most once
  local rc=$1 stop_rc i
  [ $FINISHING = 1 ] && return
  FINISHING=1
  trap - INT TERM
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
  [ $rc -eq 0 ] && [ $SUMMARY_RC -ne 0 ] && rc=14
  if [ $stop_rc -ne 0 ]; then
    step "campaign finished (rc=$rc) but the server is STILL UP: it could not be stopped safely (stop rc=$stop_rc)"
    exit $stop_rc
  fi
  step "campaign complete (rc=$rc), server stopped and gone"
  exit $rc
}

# 93b: an interrupted runner still attempts the proven-quiescence stop, once, never a kill.
on_signal() { step "runner interrupted by SIG$1"; if [ -n "${PID:-}" ]; then finish 13; fi; exit 13; }
on_exit() {
  local rc=$?
  if [ $FINISHING = 0 ] && [ -n "${PID:-}" ]; then
    step "runner exiting (rc=$rc) without its stop step: attempting the proven-quiescence stop once"
    finish $([ $rc -eq 0 ] && echo 13 || echo $rc)
  fi
}
trap 'on_signal INT' INT
trap 'on_signal TERM' TERM
trap on_exit EXIT

# ---- preflight ----------------------------------------------------------------------------------
[ "$MANIFEST" != "__MANIFEST__" ] || { step "runner not pinned to a built packet; refusing"; exit 8; }
[ "$(sha256sum $P/manifest.json | cut -d' ' -f1)" = "$MANIFEST" ] || { step "packet manifest differs from the reviewed one; refusing"; exit 8; }
/home/steve/llm-optimizations/scripts/check-b70-runtime-pm.sh || { step "runtime PM unsafe; refusing to run"; exit 8; }
[ -f "$PREREG" ] || { step "no $PREREG (the w93c references); refusing"; exit 8; }
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
  || { step "server is not the packet 95 build; refusing"; exit 8; }
pid_is_server $PID $TICKS || { step "server pid $PID does not match $RUN_NAME identity; refusing"; exit 8; }
BW=$(tr '\0' '\n' < /proc/$PID/environ 2>/dev/null | sed -n 's/^LTX_BUSY_WINDOWS=//p')
[ "$BW" = 0 ] || { step "packet 95 is a speed comparison: launch the server with LTX_BUSY_WINDOWS=0 (found '$BW'); refusing"; exit 8; }
PL=$(tr '\0' '\n' < /proc/$PID/environ 2>/dev/null | sed -n 's/^LTX_SAMPLER_PLACEMENT=//p')
[ "${PL:-two-way}" = "$PLACEMENT" ] || { step "server placement is '${PL:-two-way}', this run needs '$PLACEMENT'; refusing"; exit 8; }
SW=$(tr '\0' '\n' < /proc/$PID/environ 2>/dev/null | sed -n 's/^LTX_SAMPLER_WORKERS=//p')
[ "${SW:-2}" = "$WORKERS" ] || { step "server has ${SW:-2} sampler workers, this run needs $WORKERS; refusing"; exit 8; }
SIGINT_IGN=$($PY -c "print(int(open('/proc/$PID/status').read().split('SigIgn:')[1].split()[0], 16) >> 1 & 1)")
[ "$SIGINT_IGN" = 0 ] || { step "the server ignores SIGINT (launch it with env --default-signal=INT); refusing"; exit 8; }
HEALTH=$($PY -c "import json;print('yes' if 'health_admission' in json.load(open('$RUN/server-identity.json')) else 'no')")
step "server pid $PID up, busy timers off, SIGINT honoured, same-boot health admission: $HEALTH"
$PY -B $LANE/scripts/sample-gpu-engine-busy.py $PID $OUT/engine-busy.jsonl &
SAMPLER_PID=$!
step "engine-busy sampler pid $SAMPLER_PID (fdinfo only, no device access)"
step "rest 60 s after construction"
sleep 60

# ---- 1. text-window probe (serial) -----------------------------------------------------------
queue_empty || { step "queue not provably empty before the window probe"; finish 5; }
timeout 2400 $PY -B $LANE/scripts/run-text-window-probe.py f95-$TAG-wprobe --graph $P/graphs/text-window-probe.json --server-run $RUN
WPROBE_RC=$?
cp $RUN/text-window-probe-f95-$TAG-wprobe.json $OUT/ 2>/dev/null; sync
save "text-window probe (rc=$WPROBE_RC)"
[ $WPROBE_RC -eq 0 ] || { step "text-window probe did not qualify (rc=$WPROBE_RC)"; finish 11; }

# ---- 2. serial capture pass: one pinned prompt per sampler worker ------------------------------
for k in $(seq 0 $((WORKERS - 1))); do
  IDX_K=$((CAP_BASE + 10 * k))
  queue_empty || { step "queue not provably empty in the capture pass"; finish 5; }
  if [ $k -ge 2 ]; then
    timeout 120 $PY -B $LANE/scripts/run-capture-freeze-94.py f95-$TAG-room$k --graph $P/graphs/sampler-capture-coverage.json --server-run $RUN >/dev/null 2>&1
    cp $RUN/sampler-capture-coverage-f95-$TAG-room$k.json $OUT/ 2>/dev/null
    if ! $PY -B $LANE/scripts/worker-headroom-95.py $RUN/sampler-capture-coverage-f95-$TAG-room$k.json $LAYOUT > $OUT/headroom-w$k.json; then
      cat $OUT/headroom-w$k.json
      step "not enough memory for sampler worker $k under $LAYOUT: combination skipped (nothing captured for it)"
      save "memory floor: worker $k skipped"; finish 18
    fi
  fi
  timeout 120 $PY -B $LANE/scripts/run-sampler-pin-95.py f95-$TAG-pin$k $k --graph $P/graphs/sampler-pin.json --server-run $RUN
  [ $? -eq 0 ] || { step "pin to worker $k refused"; finish 16; }
  arm f95-$TAG-cap$k pipe-samp2-tsh-win 1 $IDX_K 1800 - "$PREREG"
  [ $ARM_RC -eq 0 ] || { step "capture-pass prompt $k ended rc=$ARM_RC"; finish $ARM_RC; }
  for i in $(seq 1 180); do [ -f $RUN/pipeline-done-sample-$IDX_K.json ] && break; sleep 5; done
  [ -f $RUN/pipeline-done-sample-$IDX_K.json ] || { step "sample job $IDX_K never finished"; finish 6; }
  sleep 5
done
queue_empty || { step "queue not provably empty after the capture pass"; finish 5; }
timeout 360 $PY -B $LANE/scripts/run-capture-freeze-94.py f95-$TAG-cover --graph $P/graphs/sampler-capture-coverage.json --server-run $RUN
COV_RC=$?
cp $RUN/sampler-capture-coverage-f95-$TAG-cover.json $OUT/ 2>/dev/null; sync
save "capture pass (coverage rc=$COV_RC)"
[ $COV_RC -eq 0 ] || { step "captures incomplete after one pinned prompt per worker: timed arms skipped"; finish 16; }

# ---- 3. decode probe (serial; needs the fast path installed by the capture pass) ---------------
step "settle 30 s"; sleep 30
queue_empty || { step "queue not provably empty before the decode probe"; finish 5; }
timeout 1500 $PY -B $LANE/scripts/run-decode-probe.py f95-$TAG-dprobe --graph $P/graphs/decode-replica-probe.json --server-run $RUN
DPROBE_RC=$?
cp $RUN/decode-probe-f95-$TAG-dprobe.json $OUT/ 2>/dev/null; sync
save "decode probe (rc=$DPROBE_RC)"
[ $DPROBE_RC -eq 0 ] || { step "decode probe did not pass (rc=$DPROBE_RC)"; finish 9; }

# ---- 4. the freeze: coverage, expected residents, 2 GiB floor; then no capture and no load -------
queue_empty || { step "queue not provably empty before the freeze"; finish 5; }
timeout 360 $PY -B $LANE/scripts/run-capture-freeze-94.py f95-$TAG-freeze --graph $P/graphs/sampler-capture-freeze.json --server-run $RUN
FREEZE_RC=$?
cp $RUN/sampler-capture-freeze-f95-$TAG-freeze.json $OUT/ 2>/dev/null; sync
save "freeze (rc=$FREEZE_RC)"
[ $FREEZE_RC -eq 0 ] || { step "freeze refused (rc=$FREEZE_RC; see the receipt): timed arms skipped"; finish 16; }

# ---- 5. post-freeze self-check through the exact timed path --------------------------------------
step "settle 15 s"; sleep 15
SELF_T0=$(date +%s)
arm f95-$TAG-self $TIMED_ARM $SELF_N $SELF_BASE 1800 - "$PREREG"
SELF_RC=$ARM_RC
timeout 120 $PY -B $LANE/scripts/selfcheck-94f.py --root $R --run $RUN --prefix f95-$TAG-self --since $SELF_T0 > $OUT/selfcheck.json
SC_RC=$?
cat $OUT/selfcheck.json; sync; save "post-freeze self-check (arm rc=$SELF_RC, check rc=$SC_RC)"
{ [ $SELF_RC -eq 0 ] && [ $SC_RC -eq 0 ]; } || { step "post-freeze self-check FAILED (see selfcheck.json): timed arms skipped"; finish 17; }

# ---- 6. placement probe: ten fixtures byte for byte against the w93c references ----------------
step "settle 30 s"; sleep 30
arm f95-$TAG-probe pipe-samp2-tsh-win $PROBE_N $PROBE_BASE 1200 - "$PREREG"
PROBE_RC=$ARM_RC
EXACT=$($PY -c "import json;d=json.load(open('$OUT/f95-$TAG-probe-throughput.json'));r=[x for x in d['rows'] if not x['fill']];print(sum(1 for x in r if x['exact']), len({x['emitted_fixture'] for x in r if x['exact']}))" 2>/dev/null)
step "placement probe: rc=$PROBE_RC, exact clips / fixtures: ${EXACT:-none}"
{ [ $PROBE_RC -eq 0 ] && [ "${EXACT##* }" = 10 ]; } || { step "placement $PLACEMENT is NOT byte-identical to the references: timed arms refused"; finish 15; }

# ---- 7. timed arm ------------------------------------------------------------------------------
step "settle 60 s"; sleep 60
arm f95-$TAG-timed $TIMED_ARM $TIMED_N $TIMED_BASE 5400 watch "$PREREG"
TIMED_RC=$ARM_RC
[ $TIMED_RC -eq 0 ] || [ $TIMED_RC -eq 3 ] || { step "timed arm ended rc=$TIMED_RC"; finish $TIMED_RC; }
finish $TIMED_RC
