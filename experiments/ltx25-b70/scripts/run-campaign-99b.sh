#!/bin/bash
# Packet 99b: current-upstream plus explicit RoPE compatibility batch-1 control; lifecycle and oracle inherited from packet 98.
# Usage: two-way 2 1 1 xpu:2 256x256 <repeat1-5> 120
# Original w93c graphs/references/proofs only; no larger sizes or new references.
# Requires LTX_OUTPUT_SIZE, NEOReadDebugKeys=1 EnableDeferBacking=0.
# Requires externally preregistered LTX_PACKET_MANIFEST_SHA256; never derive it from the packet.
# B1/W2 control only. Short indices99,000,000+1000*(repeat-1);
# timed99,500,000+10000*(repeat-1). Disjoint from packets98/99 and planned100 (<98,040,120).
# 120prompt bound and repeats1-5 retain nonoverlapping index intervals.
# This script contains future campaign actions; building/testing it never executes them.
set -u
# Deliberately narrow successor admission. No larger shape or changed batch quality.
[ "$#" = 8 ] && [ "$1 $2 $3 $4 $5 $6 $8" = "two-way 2 1 1 xpu:2 256x256 120" ] || {
  echo "packet99b admits only: two-way 2 1 1 xpu:2 256x256 <repeat1-5> 120"; exit 8;
}
LAYOUT=${1:-}; WORKERS=${2:-}; BATCH=${3:-}; POOL=${4:-}; SPEC=${5:-}; SIZE=${6:-}; REP=${7:-1}; TIMED_ARG=${8:-120}
case "$LAYOUT" in two-way) LI=0 ;; shard4-a) LI=1 ;; shard3-c) LI=2 ;; *) LI= ;; esac
case "$WORKERS" in 1|2|3|4) ;; *) LI= ;; esac
case "$BATCH" in 1) BI=0 ;; 2) BI=1 ;; 4) BI=2 ;; *) LI= ;; esac
case "$POOL" in 0) PSUF= ;; 1) PSUF=-p1 ;; *) LI= ;; esac
case "$SPEC" in xpu:1) SI=0; NREP=1 ;; xpu:2) SI=1; NREP=1 ;; xpu:1,xpu:2) SI=2; NREP=2 ;; xpu:2,xpu:1) SI=3; NREP=2 ;; *) LI= ;; esac
case "$SIZE" in 256x256) ZI=0 ;; 512x320) ZI=1 ;; 640x384) ZI=2 ;; *) LI= ;; esac
case "$REP" in 1) RSUF= ;; 2|3|4|5) RSUF=-r$REP ;; *) LI= ;; esac
case "$TIMED_ARG" in *[!0-9]*|"") LI= ;; *) { [ "$TIMED_ARG" -ge 120 ] && [ "$TIMED_ARG" -le 9000 ]; } || LI= ;; esac
[ -n "$LI" ] || { echo "usage: run-campaign-98.sh <two-way|shard4-a|shard3-c> <1|2|3|4> <1|2|4> <0|1> <xpu:1|xpu:2|xpu:1,xpu:2|xpu:2,xpu:1> <256x256|512x320|640x384> [repeat 1-5] [timed prompts 120-9000]"; exit 8; }
IDX=$((12 * LI + 3 * (WORKERS - 1) + BI))
PLACEMENT=$LAYOUT
DSUF=-d$(echo "$SPEC" | tr -d ':,')
MODE=$LAYOUT-w$WORKERS-b$BATCH$PSUF$DSUF-s$SIZE$RSUF
TAG=$(echo $LAYOUT | tr -d -)w${WORKERS}b$BATCH${PSUF#-}${DSUF#-}s${SIZE}${RSUF#-}
COMBO=$((IDX + 36 * (POOL + 2 * (SI + 4 * (ZI + 3 * (REP - 1))))))
BASE=$((99000000 + 1000 * (REP - 1)))
CAP_BASE=$BASE; SELF_BASE=$((BASE + 100)); PROBE_BASE=$((BASE + 200)); REF_BASE=$((BASE + 200))
PROOFN_BASE=$((BASE + 300)); PROOFS_BASE=$((BASE + 400))
TIMED_BASE=$((99500000 + 10000 * (REP - 1)))
# Packet 98: every literal clip index must stay within the nodes' ceiling (ltx_pipeline.CLIP_INDEX_MAX).
[ $((TIMED_BASE + TIMED_ARG)) -le 100000000 ] || { echo "index base above the clip_index ceiling"; exit 8; }
TIMED_N=$TIMED_ARG; PROBE_N=13
if [ $BATCH = 1 ]; then
  DEPTH=$WORKERS
  case $WORKERS in 2) TIMED_ARM=pipe-samp2-tsh-rep-wlean ;; *) TIMED_ARM=pipe-samp2-tsh-rep-wlean-s$WORKERS ;; esac
  CAP_ARM=pipe-samp2-tsh-win
  SELF_N=$((WORKERS + 4))
else
  DEPTH=$(( (WORKERS + 1) * BATCH - 1 ))
  TIMED_ARM=pipe-samp2-tsh-rep-wlean-b$BATCH-w$WORKERS
  REF_ARM=pipe-samp2-tsh-rep-wlean-b$BATCH-ref
  CAP_ARM=pipe-samp2-tsh-win-b$BATCH
  SELF_N=$((DEPTH + 4))   # sampler depth + decode depth 2 + two emitted clips
fi
if [ "$SIZE" != 256x256 ]; then
  CAP_ARM=$CAP_ARM-speed-s$SIZE
  TIMED_ARM=$TIMED_ARM-speed-s$SIZE
  PROBE_N=$((DEPTH + 12))
fi
R=/mnt/fast-ai/bench-results/ltx25-baseline-20260913
P=$R/prepared-encoder-upstream-99b
PY=/home/steve/.venvs/ltx25-baseline/bin/python
if [ $BATCH != 1 ] && [ "$SIZE" = 256x256 ]; then
  # Review finding 3: prompt i emits clip i - sampler depth - decode depth, so an arm that must emit the K
  # clips of the arrangement needs K + both depths prompts. Both depths are read from the packet's own
  # reference-arm graph (not hard-coded); the sampler depth must be the serial depth B-1.
  read REF_K REF_N REF_SD REF_DD < <($PY -B -c "
import json, sys
sys.path.insert(0, '/home/steve/llm-optimizations/experiments/ltx25-b70/scripts')
import ltx_sampler_batch as b
g = json.load(open('$P/graphs/graph-capture-all48-$REF_ARM.json'))
sd, dd = g['428']['inputs']['depth'], g['426']['inputs']['depth']
assert sd == b.serial_depth($BATCH), sd
k = len(b.ORDERS[$BATCH]['ref'])
print(k, k + sd + dd, sd, dd)" 2>/dev/null)
  TD=$($PY -B -c "import json;g=json.load(open('$P/graphs/graph-capture-all48-$TIMED_ARM.json'));print(g['426']['inputs']['depth'])" 2>/dev/null)
  TIMED_K=$(( TIMED_N - DEPTH - ${TD:-0} ))
fi
MANIFEST=${LTX_PACKET_MANIFEST_SHA256:-}
# The manifest binds this immutable runner. Supply its expected digest explicitly
# to avoid embedding the manifest's own digest in the file it hashes.
[[ "$MANIFEST" =~ ^[0-9a-f]{64}$ ]] || { echo "runner not pinned to a built packet; refusing"; exit 8; }
LANE=/home/steve/llm-optimizations/experiments/ltx25-b70
REPO=/home/steve/llm-optimizations
RUN_NAME=encoder-server-upstream-99b-$MODE
RUN=$R/$RUN_NAME
BASE_OUT=$LANE/data/upstream-99b
OUT=$BASE_OUT/$MODE
W93C=$LANE/data/stability-01-window-prereg.json
BPREREG=$LANE/data/stability-01-batch$BATCH-prereg.json
[ ! -e "$OUT" ] && [ ! -L "$OUT" ] || { echo "existing output directory refused: $OUT"; exit 8; }
mkdir -p "$BASE_OUT" && mkdir "$OUT" || { echo "could not exclusively create output directory: $OUT"; exit 8; }
step() { echo "=== $(date -u +%FT%TZ) [$MODE] $*"; }
save() { # commit message, [extra explicit repo-relative paths]
  local msg=$1; shift
  # Review finding 7: commit only these explicit paths, never whatever else is staged in the index.
  ( cd $REPO && git add -- "${OUT#$REPO/}" "$@" && git commit -q -m "LTX packet 99b ($MODE): $msg receipts" -- "${OUT#$REPO/}" "$@" ) >/dev/null 2>&1 && step "committed $msg" || step "commit of $msg failed (continuing)"
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
DRAIN_S=300   # quiescence 1/2 waits this long for an empty queue; a failed or expired arm raises it
arm_timeouts() { # prompts -> "client outer" seconds: client 1800 + 2.5 s per prompt, outer = client + 300
  local c=$((1800 + (5 * $1 + 1) / 2))
  echo "$c $((c + 300))"
}
arm() { # name graph-arm count index-base auto(timeouts derive from count) watch|- fixtures order [no-oracle]
  local ct ot
  read ct ot < <(arm_timeouts $3)
  step "$1: arm $2, $3 prompts, index base $4, order $8${9:+, not compared}, client timeout ${ct} s (outer ${ot} s)"
  local wpid= extra=()
  [ "${9:-}" = no-oracle ] && extra=(--no-oracle)
  ARMS_RUN="$ARMS_RUN $1"
  if [ "${6:-}" = watch ]; then rm -f "$SYNC_FLAG"; sync_watch $1 & wpid=$!; fi
  timeout $ot $PY -B $LANE/scripts/run-throughput-fixtures-98.py $1 --graph $P/graphs/graph-capture-all48-$2.json \
    --arm $2 --server-run $RUN --count $3 --index-base $4 --out $OUT --fixtures "$7" --order $8 --batch $BATCH \
    --timeout $ct --size "$SIZE" "${extra[@]}"
  ARM_RC=$?
  # An arm that failed or expired may leave queued prompts in the server: let the quiescence stop wait up to a
  # whole arm's worth (2.5 s per prompt + 1800 s) for the queue to drain instead of abandoning a busy server.
  if [ $ARM_RC -ne 0 ] && [ $ct -gt $DRAIN_S ]; then DRAIN_S=$ct; fi
  if [ -n "$wpid" ]; then touch "$SYNC_FLAG" || kill $wpid; wait $wpid; rm -f "$SYNC_FLAG"; fi
  sync
  step "$1 finished rc=$ARM_RC; synced"
  if [ $ARM_RC -ne 0 ]; then
    failed_jobs && step "$1: the failed pipeline job(s) above explain rc=$ARM_RC"
    save "$1 (rc=$ARM_RC)"
  else
    save "$1"
  fi
}

pid_is_server() { # pid ticks: the launcher we verified, not a reused pid
  [ -r /proc/$1/cmdline ] || return 1
  tr '\0' ' ' < /proc/$1/cmdline | grep -q -- "serve-encoder.py .*--run-name $RUN_NAME " || \
    tr '\0' ' ' < /proc/$1/cmdline | grep -q -- "serve-encoder.py .*--run-name $RUN_NAME\$" || return 1
  [ "$($PY -B -c "import sys;print(open('/proc/$1/stat').read().split(') ')[1].split()[19])")" = "$2" ]
}

queue_empty() { # 0 only when a queue request succeeded and showed nothing running or pending
  local q
  q=$(curl -sf -m 10 http://127.0.0.1:8188/queue) || return 1
  echo "$q" | $PY -B -c "import json,sys
d=json.load(sys.stdin)
sys.exit(0 if d.get('queue_running') == [] and d.get('queue_pending') == [] else 1)"
}

missing_markers() { # done markers missing for jobs the server actually queued (batch-aware)
  timeout 120 $PY -B $LANE/scripts/missing-markers-96.py --root $R --run $RUN $ARMS_RUN || echo "marker-check-failed"
}

FAILED_SEEN=0
MONITOR_FAILED=0
failed_jobs() { # 0 (and prints each failed job's last traceback lines) when pipeline-failed-*.json receipts exist
  local out rc
  out=$(timeout 60 $PY -B $LANE/scripts/check-failed-jobs-97.py --run $RUN "$@" 2>&1)
  rc=$?
  [ $rc -eq 0 ] && return 1
  if [ $rc -ne 3 ]; then   # helper timeout (124), crash or usage error: failure detection is NOT working
    MONITOR_FAILED=1
    step "FAILED-JOB MONITOR BROKE (check-failed-jobs-97.py rc=$rc): $(echo "$out" | tail -2 | tr '\n' ' ')"
    return 2
  fi
  FAILED_SEEN=1
  echo "$out" | while IFS= read -r line; do step "$line"; done
  return 0
}

IDLE_N=0
pipeline_idle_once() { # 0 only if the queue is empty and the coverage node reports busy=0, running=0
  local name
  IDLE_N=$((IDLE_N + 1)); name=f99b-$TAG-idle$IDLE_N
  queue_empty || return 1
  timeout 120 $PY -B $LANE/scripts/run-capture-freeze-94.py $name --graph $P/graphs/sampler-capture-coverage.json --server-run $RUN >/dev/null 2>&1
  $PY -B -c "import json,sys;d=json.load(open('$RUN/sampler-capture-coverage-$name.json'));sys.exit(0 if d.get('pipeline_busy')==0 and d.get('pipeline_running')==0 else 1)" 2>/dev/null || return 1
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
  step "quiescence 1/2: waiting for a successful, empty queue response (up to $DRAIN_S s)"
  local ok=0 i missing fj
  for i in $(seq 1 $(( (DRAIN_S + 9) / 10 ))); do
    queue_empty && { ok=1; break; }
    [ -f $R/FAULT.json ] && { step "FAULT latched while draining: server left up for incident review"; return 4; }
    sleep 10
  done
  [ $ok = 1 ] || { step "queue never PROVABLY empty (request failed or work pending): server left UP"; return 5; }
  step "quiescence 2/2: waiting for done markers of every submitted sample/decode/save job (up to 10 min)"
  for i in $(seq 1 60); do
    missing=$(missing_markers | wc -l)
    [ "$missing" = 0 ] && break
    # Packet 98: a failed job never writes its done marker; its receipt says so at once.
    failed_jobs; fj=$?
    [ $fj -eq 0 ] && { step "failed pipeline job receipts found: not waiting for their done markers"; break; }
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

decode_placement_check() { # every emitted clip of these arms decoded on its rotation slot's card (packet 98)
  timeout 120 $PY -B $LANE/scripts/check-decode-placement-97.py --root $R --run $RUN --replicas $SPEC "$@" > $OUT/decode-placement.json
  local rc=$?
  sync; save "decode placement check (rc=$rc)"
  [ $rc -eq 0 ] && { step "decode placement: every emitted clip decoded on the card of its slot ($SPEC)"; return 0; }
  cat $OUT/decode-placement.json
  step "DECODE PLACEMENT CHECK FAILED (rc=$rc): a clip was decoded off its rotation card, or none was checked"
  return 1
}

SUMMARY_RC=0
REF_RAN=0
summary_args() { # arms, pair and required proofs for the summary (pure; tested by test-packet96)
  # Review 2, finding 4: the reference arm is requested only if it ran on this server (REF_RAN=1);
  # on a second run the references already existed and the first proof arm is the sentry baseline.
  if [ "$SIZE" != 256x256 ]; then
    echo "--arm f99b-$TAG-probe:speed-probe --arm f99b-$TAG-timed:timed-speed --pair f99b-$TAG-probe:f99b-$TAG-timed"
  elif [ $BATCH = 1 ]; then
    echo "--arm f99b-$TAG-probe:placement-probe --arm f99b-$TAG-timed:timed --pair f99b-$TAG-probe:f99b-$TAG-timed"
  elif [ "$REF_RAN" = 1 ]; then
    echo "--arm f99b-$TAG-ref:reference --arm f99b-$TAG-proofn:proof-neighbours --arm f99b-$TAG-proofs:proof-slots --arm f99b-$TAG-timed:timed --pair f99b-$TAG-ref:f99b-$TAG-timed --require-proof proof-neighbours.json --require-proof proof-slots.json --require-proof proof-timed.json"
  else
    echo "--arm f99b-$TAG-proofn:proof-neighbours --arm f99b-$TAG-proofs:proof-slots --arm f99b-$TAG-timed:timed --pair f99b-$TAG-proofn:f99b-$TAG-timed --require-proof proof-neighbours.json --require-proof proof-slots.json --require-proof proof-timed.json"
  fi
}

summarize() { # the context-sentry gate (first exact pass vs timed arm): a failure fails the campaign (exit 14)
  timeout 300 $PY -B $LANE/scripts/summarize-campaign-98.py --run $RUN --out $OUT --batch $BATCH $(summary_args)
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
    for i in $(seq 1 10); do [ -e /proc/$SAMPLER_PID ] || break; sleep 1; done
    [ -e /proc/$SAMPLER_PID ] && kill $SAMPLER_PID 2>/dev/null
    wait $SAMPLER_PID 2>/dev/null
  fi
  summarize
  sync
  save "summary (rc=$rc, stop rc=$stop_rc)"
  [ $rc -eq 0 ] && [ $SUMMARY_RC -ne 0 ] && rc=14
  [ $rc -eq 0 ] && [ $FAILED_SEEN = 1 ] && rc=20
  [ $rc -eq 0 ] && [ $MONITOR_FAILED = 1 ] && rc=22
  if [ $stop_rc -ne 0 ]; then
    step "campaign finished (rc=$rc) but the server is STILL UP: it could not be stopped safely (stop rc=$stop_rc)"
    exit $stop_rc
  fi
  step "campaign complete (rc=$rc), server stopped and gone"
  exit $rc
}

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
if [ $BATCH != 1 ] && [ "$SIZE" = 256x256 ]; then
  [ -n "${REF_N:-}" ] && [ -n "${TD:-}" ] && [ "$TIMED_K" -gt 0 ] || { step "could not derive the arm prompt counts from the packet graphs; refusing"; exit 8; }
  step "reference/proof arms: $REF_N prompts (sampler depth $REF_SD, decode depth $REF_DD) emit the $REF_K clips of each arrangement; timed: $TIMED_N prompts emit $TIMED_K clips"
fi
[ "$MANIFEST" != "__MANIFEST__" ] || { step "runner not pinned to a built packet; refusing"; exit 8; }
[ "$(sha256sum $P/manifest.json | cut -d' ' -f1)" = "$MANIFEST" ] || { step "packet manifest differs from the reviewed one; refusing"; exit 8; }
/home/steve/llm-optimizations/scripts/check-b70-runtime-pm.sh || { step "runtime PM unsafe; refusing to run"; exit 8; }
[ -f "$W93C" ] || { step "no $W93C (the w93c references, prompts and seeds); refusing"; exit 8; }
[ "$SIZE" != 256x256 ] || [ $BATCH = 1 ] || [ -f "$BPREREG" ] || { step "no $BPREREG: packet 98 never makes batch references (run packet 96's reference arm first); refusing"; exit 8; }
step "waiting for server health"
for i in $(seq 1 360); do
  [ -f $R/FAULT.json ] && { step FAULT latched; exit 4; }
  curl -sf -m 10 http://127.0.0.1:8188/queue >/dev/null 2>&1 && break
  sleep 5
done
curl -sf -m 10 http://127.0.0.1:8188/queue >/dev/null || { step server never answered; exit 8; }
[ -f $RUN/server-identity.json ] || { step "no $RUN/server-identity.json: the server on 8188 is not $RUN_NAME; refusing"; exit 8; }
PID=$($PY -B -c "import json;print(json.load(open('$RUN/server-identity.json'))['pid'])")
TICKS=$($PY -B -c "import json;print(json.load(open('$RUN/server-identity.json'))['proc_start_ticks'])")
[ "$($PY -B -c "import json;print(json.load(open('$RUN/server-identity.json'))['source_packet_manifest_sha256'])")" = "$MANIFEST" ] \
  || { step "server is not the packet 99b build; refusing"; exit 8; }
pid_is_server $PID $TICKS || { step "server pid $PID does not match $RUN_NAME identity; refusing"; exit 8; }
envval() { tr '\0' '\n' < /proc/$PID/environ 2>/dev/null | sed -n "s/^$1=//p"; }
OSIZE=$(envval LTX_OUTPUT_SIZE)
[ "$OSIZE" = "$SIZE" ] || { step "server must explicitly set LTX_OUTPUT_SIZE=$SIZE (found '$OSIZE'); refusing"; exit 8; }
BW=$(envval LTX_BUSY_WINDOWS)
[ "$BW" = 0 ] || { step "packet 96 is a speed comparison: launch the server with LTX_BUSY_WINDOWS=0 (found '$BW'); refusing"; exit 8; }
PL=$(envval LTX_SAMPLER_PLACEMENT)
[ "${PL:-two-way}" = "$PLACEMENT" ] || { step "server placement is '${PL:-two-way}', this run needs '$PLACEMENT'; refusing"; exit 8; }
SW=$(envval LTX_SAMPLER_WORKERS)
[ "${SW:-2}" = "$WORKERS" ] || { step "server has ${SW:-2} sampler workers, this run needs $WORKERS; refusing"; exit 8; }
SB=$(envval LTX_SAMPLER_BATCH)
[ "${SB:-1}" = "$BATCH" ] || { step "server sampler batch is ${SB:-1}, this run needs $BATCH; refusing"; exit 8; }
SP=$(envval LTX_SAMPLER_SHARED_POOL)
[ "${SP:-0}" = "$POOL" ] || { step "server shared graph pool is ${SP:-0}, this run needs $POOL; refusing"; exit 8; }
NRD=$(envval NEOReadDebugKeys); EDB=$(envval EnableDeferBacking)
[ "$NRD" = 1 ] && [ "$EDB" = 0 ] || { step "packet 98 needs NEOReadDebugKeys=1 EnableDeferBacking=0 on the server (found '$NRD' '$EDB'); refusing"; exit 8; }
DRD=$(envval LTX_DECODE_REPLICA_DEVICE); DRN=$(envval LTX_DECODE_REPLICAS)
if [ $NREP = 1 ]; then
  [ "${DRD:-xpu:1}" = "$SPEC" ] && [ "${DRN:-1}" = 1 ] || { step "server decode replica is '${DRD:-xpu:1}' x ${DRN:-1}, this run needs $SPEC x 1; refusing"; exit 8; }
else
  [ "$DRD" = "$SPEC" ] && [ "$DRN" = 2 ] || { step "server decode replicas are '$DRD' x '$DRN', this run needs $SPEC x 2; refusing"; exit 8; }
fi
mkdir -p $OUT
tr '\0' '\n' < /proc/$PID/environ | grep -E '^(NEOReadDebugKeys|EnableDeferBacking|ForceZeDeviceCanAccessPerReturnValue|SYCL_[A-Z0-9_]+|UR_[A-Z0-9_]+|ZE_[A-Z0-9_]+|ONEAPI_[A-Z0-9_]+|LTX_OUTPUT_SIZE|LTX_BUSY_WINDOWS|LTX_SAMPLER_[A-Z_]+|LTX_DECODE_[A-Z_]+)=' | sort > $OUT/runtime-environment.txt
SIGINT_IGN=$($PY -B -c "print(int(open('/proc/$PID/status').read().split('SigIgn:')[1].split()[0], 16) >> 1 & 1)")
[ "$SIGINT_IGN" = 0 ] || { step "the server ignores SIGINT (launch it with env --default-signal=INT); refusing"; exit 8; }
HEALTH=$($PY -B -c "import json;print('yes' if 'health_admission' in json.load(open('$RUN/server-identity.json')) else 'no')")
[ "$HEALTH" = yes ] || { step "server lacks health admission; refusing"; exit 8; }
step "server pid $PID up, batch $BATCH, $WORKERS sampler jobs, shared pool $POOL, decode replica(s) $SPEC, depth $DEPTH, busy timers off, SIGINT honoured, health admission: $HEALTH"
$PY -B $LANE/scripts/sample-gpu-engine-busy.py $PID $OUT/engine-busy.jsonl &
SAMPLER_PID=$!
step "engine-busy sampler pid $SAMPLER_PID (fdinfo only, no device access)"
step "rest 60 s after construction"
sleep 60

# ---- 1. text-window probe (serial) -----------------------------------------------------------
queue_empty || { step "queue not provably empty before the window probe"; finish 5; }
timeout 2400 $PY -B $LANE/scripts/run-text-window-probe.py f99b-$TAG-wprobe --graph $P/graphs/text-window-probe.json --server-run $RUN
WPROBE_RC=$?
cp $RUN/text-window-probe-f99b-$TAG-wprobe.json $OUT/ 2>/dev/null; sync
save "text-window probe (rc=$WPROBE_RC)"
[ $WPROBE_RC -eq 0 ] || { step "text-window probe did not qualify (rc=$WPROBE_RC)"; finish 11; }

# ---- 2. memory plan for batch-B graphs (nothing captured yet) ---------------------------------
if [ "$SIZE" != 256x256 ] || [ $BATCH != 1 ] || [ $POOL = 1 ]; then
  if ! $PY -B $LANE/scripts/worker-headroom-98.py plan $LAYOUT $WORKERS $BATCH $POOL --size $SIZE --replicas $SPEC --manifest $MANIFEST --calibration-root $BASE_OUT > $OUT/headroom-plan.json; then
    cat $OUT/headroom-plan.json
    step "batch-$BATCH graphs for one worker are predicted to break the 2 GiB floor under $LAYOUT, or a replica card $SPEC lacks the probe's room: combination skipped (nothing captured)"
    save "memory plan: skipped"; finish 18
  fi
  cat $OUT/headroom-plan.json
fi

# ---- 3. serial capture pass: one pinned prompt per sampler worker ------------------------------
FIRST_LIVE=2; { [ $BATCH != 1 ] || [ $POOL = 1 ]; } && FIRST_LIVE=1
for k in $(seq 0 $((WORKERS - 1))); do
  IDX_K=$((CAP_BASE + 10 * k))
  queue_empty || { step "queue not provably empty in the capture pass"; finish 5; }
  if [ $k -ge $FIRST_LIVE ]; then
    timeout 120 $PY -B $LANE/scripts/run-capture-freeze-94.py f99b-$TAG-room$k --graph $P/graphs/sampler-capture-coverage.json --server-run $RUN >/dev/null 2>&1
    cp $RUN/sampler-capture-coverage-f99b-$TAG-room$k.json $OUT/ 2>/dev/null
    PREV=()   # review 2, finding 2: the previous worker's own before-reading, when there is one
    [ $((k - 1)) -ge $FIRST_LIVE ] && PREV=($RUN/sampler-capture-coverage-f99b-$TAG-room$((k - 1)).json)
    if ! $PY -B $LANE/scripts/worker-headroom-98.py live $RUN/sampler-capture-coverage-f99b-$TAG-room$k.json $LAYOUT $BATCH $POOL "${PREV[@]}" --size $SIZE --replicas $SPEC --manifest $MANIFEST --calibration-root $BASE_OUT > $OUT/headroom-w$k.json; then
      cat $OUT/headroom-w$k.json
      step "not enough memory for sampler worker $k at batch $BATCH under $LAYOUT: combination skipped (nothing captured for it)"
      save "memory floor: worker $k skipped"; finish 18
    fi
  fi
  timeout 120 $PY -B $LANE/scripts/run-sampler-pin-95.py f99b-$TAG-pin$k $k --graph $P/graphs/sampler-pin.json --server-run $RUN
  [ $? -eq 0 ] || { step "pin to worker $k refused"; finish 16; }
  arm f99b-$TAG-cap$k $CAP_ARM 1 $IDX_K auto - "$W93C" cycle no-oracle
  [ $ARM_RC -eq 0 ] || { step "capture-pass prompt $k ended rc=$ARM_RC"; finish $ARM_RC; }
  for i in $(seq 1 180); do
    [ -f $RUN/pipeline-done-sample-$IDX_K.json ] && break
    # Packet 98: a failed capture job (any stage) leaves pipeline-failed-*.json; stop at once with its traceback.
    failed_jobs; fj=$?
    [ $fj -eq 0 ] && { step "capture-pass prompt $k: a pipeline job failed (receipt above)"; finish 20; }
    [ $fj -eq 2 ] && { step "capture-pass prompt $k: failed-job monitoring is not working; stopping"; finish 22; }
    sleep 5
  done
  if [ ! -f $RUN/pipeline-done-sample-$IDX_K.json ]; then
    failed_jobs; fj=$?
    [ $fj -eq 0 ] && finish 20
    [ $fj -eq 2 ] && finish 22
    step "sample job $IDX_K never finished"; finish 6
  fi
  sleep 5
done
queue_empty || { step "queue not provably empty after the capture pass"; finish 5; }
timeout 360 $PY -B $LANE/scripts/run-capture-freeze-94.py f99b-$TAG-cover --graph $P/graphs/sampler-capture-coverage.json --server-run $RUN
COV_RC=$?
cp $RUN/sampler-capture-coverage-f99b-$TAG-cover.json $OUT/ 2>/dev/null; sync
save "capture pass (coverage rc=$COV_RC)"
[ $COV_RC -eq 0 ] || { step "captures incomplete or not at batch $BATCH after one pinned prompt per worker: timed arms skipped"; finish 16; }
if [ $POOL = 1 ] && [ $WORKERS -ge 2 ]; then
  # Calibration for later pooled runs of this packet and layout: the last worker's measured pooled cost per
  # card (its room receipt, taken just before its capture, minus the coverage receipt just after the pass).
  LASTW=$((WORKERS - 1))
  if $PY -B $LANE/scripts/worker-headroom-98.py calibrate $OUT/sampler-capture-coverage-f99b-$TAG-room$LASTW.json \
      $OUT/sampler-capture-coverage-f99b-$TAG-cover.json $LAYOUT $BATCH $LASTW --size $SIZE --manifest $MANIFEST --out $OUT/pool-calibration.json; then
    step "pool calibration written: $OUT/pool-calibration.json"
  else
    step "pool calibration could not be written (continuing; later runs fall back to the private-pool bound)"
  fi
  sync; save "pool calibration"
fi

# ---- 4. decode probe (serial) -----------------------------------------------------------------
step "settle 30 s"; sleep 30
queue_empty || { step "queue not provably empty before the decode probe"; finish 5; }
timeout 1500 $PY -B $LANE/scripts/run-decode-probe-98.py f99b-$TAG-dprobe --graph $P/graphs/decode-replica-probe.json --server-run $RUN --expect-replicas $SPEC --size $SIZE
DPROBE_RC=$?
cp $RUN/decode-probe-f99b-$TAG-dprobe.json $OUT/ 2>/dev/null; sync
save "decode probe (rc=$DPROBE_RC)"
[ $DPROBE_RC -eq 0 ] || { step "decode probe did not pass (rc=$DPROBE_RC)"; finish "$($PY -B $LANE/scripts/receipt-exit-98.py "$RUN/decode-probe-f99b-$TAG-dprobe.json" 9)"; }

# ---- 5. the freeze ---------------------------------------------------------------------------
queue_empty || { step "queue not provably empty before the freeze"; finish 5; }
timeout 360 $PY -B $LANE/scripts/run-capture-freeze-94.py f99b-$TAG-freeze --graph $P/graphs/sampler-capture-freeze.json --server-run $RUN
FREEZE_RC=$?
cp $RUN/sampler-capture-freeze-f99b-$TAG-freeze.json $OUT/ 2>/dev/null; sync
save "freeze (rc=$FREEZE_RC)"
[ $FREEZE_RC -eq 0 ] || { step "freeze refused (rc=$FREEZE_RC; see the receipt): timed arms skipped"; finish "$($PY -B $LANE/scripts/receipt-exit-98.py "$RUN/sampler-capture-freeze-f99b-$TAG-freeze.json" 16)"; }

# ---- 6. post-freeze self-check through the exact timed path -------------------------------------
step "settle 15 s"; sleep 15
SELF_T0=$(date +%s)
if [ "$SIZE" != 256x256 ]; then
  arm f99b-$TAG-self $TIMED_ARM $SELF_N $SELF_BASE auto - "$W93C" shift no-oracle
elif [ $BATCH = 1 ]; then
  arm f99b-$TAG-self $TIMED_ARM $SELF_N $SELF_BASE auto - "$W93C" cycle
else
  arm f99b-$TAG-self $TIMED_ARM $SELF_N $SELF_BASE auto - "$W93C" shift no-oracle
fi
SELF_RC=$ARM_RC
timeout 120 $PY -B $LANE/scripts/selfcheck-94f.py --root $R --run $RUN --prefix f99b-$TAG-self --since $SELF_T0 > $OUT/selfcheck.json
SC_RC=$?
cat $OUT/selfcheck.json; sync; save "post-freeze self-check (arm rc=$SELF_RC, check rc=$SC_RC)"
{ [ $SELF_RC -eq 0 ] && [ $SC_RC -eq 0 ]; } || { step "post-freeze self-check FAILED (see selfcheck.json): timed arms skipped"; finish 17; }

if [ "$SIZE" != 256x256 ]; then
  step "speed only at $SIZE: no saved output references or batch-oracle claims"
  arm f99b-$TAG-probe $TIMED_ARM $PROBE_N $PROBE_BASE auto - "$W93C" cycle no-oracle
  [ $ARM_RC -eq 0 ] || finish $ARM_RC
  step "settle 60 s"; sleep 60
  arm f99b-$TAG-timed $TIMED_ARM $TIMED_N $TIMED_BASE auto watch "$W93C" shift no-oracle
  TIMED_RC=$ARM_RC
  [ $TIMED_RC -eq 0 ] || finish $TIMED_RC
  decode_placement_check f99b-$TAG-self f99b-$TAG-probe f99b-$TAG-timed || finish 21
  finish 0
fi

if [ $BATCH = 1 ]; then
  # ---- B=1, 7. placement probe against w93c ----------------------------------------------------
  step "settle 30 s"; sleep 30
  arm f99b-$TAG-probe pipe-samp2-tsh-win $PROBE_N $PROBE_BASE auto - "$W93C" cycle
  PROBE_RC=$ARM_RC
  EXACT=$($PY -B -c "import json;d=json.load(open('$OUT/f99b-$TAG-probe-throughput.json'));r=[x for x in d['rows'] if not x['fill']];print(sum(1 for x in r if x['exact']), len({x['emitted_fixture'] for x in r if x['exact']}))" 2>/dev/null)
  step "placement probe: rc=$PROBE_RC, exact clips / fixtures: ${EXACT:-none}"
  { [ $PROBE_RC -eq 0 ] && [ "${EXACT##* }" = 10 ]; } || { step "batch 1 under $PLACEMENT is NOT byte-identical to the w93c references: timed arm refused"; finish 15; }
  # ---- B=1, 8. timed against w93c --------------------------------------------------------------
  step "settle 60 s"; sleep 60
  arm f99b-$TAG-timed $TIMED_ARM $TIMED_N $TIMED_BASE auto watch "$W93C" cycle
  TIMED_RC=$ARM_RC
  [ $TIMED_RC -eq 0 ] || [ $TIMED_RC -eq 3 ] || { step "timed arm ended rc=$TIMED_RC"; finish $TIMED_RC; }
  decode_placement_check f99b-$TAG-self f99b-$TAG-probe f99b-$TAG-timed || finish 21
  finish $TIMED_RC
fi

# ---- B>1, 7. reference arm (only if the b<B> references do not exist yet) --------------------------
step "settle 30 s"; sleep 30
if [ -f "$BPREREG" ]; then
  step "batch-$BATCH references exist ($BPREREG): not regenerated; this server must reproduce them"
  $PY -B -c "
import json,sys
from pathlib import Path
d=json.load(open('$BPREREG')); R=Path('$R')
assert d['batch']==$BATCH and len(d['fixtures'])==10
for f in d['fixtures']:
    assert (R/'output/validation'/f['reference']/'tensors.safetensors').is_file(), f['reference']
    assert (R/'requests'/f['reference']/'history.json').is_file(), f['reference']
print('references present:', ', '.join(f['reference'] for f in d['fixtures']))" || { step "batch-$BATCH prereg exists but its references are incomplete; refusing"; finish 15; }
else
  # Packet 98 makes no references: decode placement cannot change sampler output.
  step "no $BPREREG: packet 98 never makes batch references (run packet 96's reference arm first); refusing"
  finish 15
fi

# ---- B>1, 8. proof arms: other neighbours, other slots, byte-identical to b<B> ---------------------
step "settle 30 s"; sleep 30
arm f99b-$TAG-proofn $REF_ARM $REF_N $PROOFN_BASE auto - "$BPREREG" proof-neighbours
PN_RC=$ARM_RC
$PY -B $LANE/scripts/check-batch-proof-96.py --prereg $BPREREG --arm $OUT/f99b-$TAG-proofn-throughput.json --kind neighbours --expect-clips $REF_K --out $OUT/proof-neighbours.json >/dev/null
PNC_RC=$?
arm f99b-$TAG-proofs $REF_ARM $REF_N $PROOFS_BASE auto - "$BPREREG" proof-slots
PS_RC=$ARM_RC
$PY -B $LANE/scripts/check-batch-proof-96.py --prereg $BPREREG --arm $OUT/f99b-$TAG-proofs-throughput.json --kind slots --expect-clips $REF_K --out $OUT/proof-slots.json >/dev/null
PSC_RC=$?
sync; save "proof arms (neighbours rc=$PN_RC/$PNC_RC, slots rc=$PS_RC/$PSC_RC)"
{ [ $PN_RC -eq 0 ] && [ $PNC_RC -eq 0 ] && [ $PS_RC -eq 0 ] && [ $PSC_RC -eq 0 ]; } || \
  { step "a clip's bytes depended on its neighbours or its slot (or a proof arm failed): timed arm refused"; finish 15; }
step "proof arms passed: every clip byte-identical to its batch-$BATCH reference with other neighbours and other slots"

# ---- B>1, 9. timed arm against b<B> ---------------------------------------------------------------
step "settle 60 s"; sleep 60
arm f99b-$TAG-timed $TIMED_ARM $TIMED_N $TIMED_BASE auto watch "$BPREREG" shift
TIMED_RC=$ARM_RC
$PY -B $LANE/scripts/check-batch-proof-96.py --prereg $BPREREG --arm $OUT/f99b-$TAG-timed-throughput.json --kind timed --expect-clips $TIMED_K --out $OUT/proof-timed.json >/dev/null
PT_RC=$?
sync; save "timed proof check (rc=$PT_RC)"
[ $TIMED_RC -eq 0 ] || [ $TIMED_RC -eq 3 ] || { step "timed arm ended rc=$TIMED_RC"; finish $TIMED_RC; }
[ $TIMED_RC -eq 3 ] && finish 3
decode_placement_check f99b-$TAG-self f99b-$TAG-proofn f99b-$TAG-proofs f99b-$TAG-timed || finish 21
# Review finding 2: a rejected timed check fails the campaign even when every byte comparison passed.
[ $PT_RC -eq 0 ] || { step "timed arm proof check REJECTED (rc=$PT_RC; see proof-timed.json)"; finish 19; }
finish 0
