#!/bin/bash
# Packet 96 (prepared-encoder-batch-96): one sampler job carries B consecutive clips as one batch.
# The layout (LTX_SAMPLER_PLACEMENT), the number of sampler jobs in flight (LTX_SAMPLER_WORKERS) and the
# batch (LTX_SAMPLER_BATCH) are fixed per server launch; this runner takes all three:
#
#   bash run-campaign-96.sh <two-way|shard4-a|shard3-c> <1|2|3|4> <1|2|4> [<shared pool 0|1>]
#
# The 4th argument (default 0) must match the server's LTX_SAMPLER_SHARED_POOL: 1 captures every sampler
# block graph of a (card, worker) into one shared graph pool on one capture stream. Pooled runs have their
# own run names (suffix -p1), request prefixes, output dirs and index bases (300000 + ...).
#
# Launch (one server per combination; commands in notes/2026-10-04-packet-96-build.md):
#   env --default-signal=INT NEOReadDebugKeys=1 EnableDeferBacking=0 LTX_BUSY_WINDOWS=0 \
#       LTX_SAMPLER_PLACEMENT=<layout> LTX_SAMPLER_WORKERS=<W> LTX_SAMPLER_BATCH=<B> ...
# Like 95b, the server must run with NEOReadDebugKeys=1 EnableDeferBacking=0 (host-RAM shadow fix,
# notes/2026-10-04-host-ram-shadow-of-vram.md); the runner refuses otherwise and records both.
#
# Per server, in order (every client call under `timeout`; waits on pids and files):
#   1. text-window probe (serial)
#   2. B>1: memory plan (worker-headroom-96.py plan): the first worker's batch-B graphs must leave the
#      2 GiB floor on every card by the 95b-measured figures, else the combination is skipped (exit 18)
#      before anything is captured.
#   3. serial capture pass: per worker k, pin the next sampler job to worker k and send one prompt alone
#      (B>1: arm pipe-samp2-tsh-win-b<B>, the prompt ends its stream so the job is the clip plus B-1 fill
#      rows: the batch-B shapes of both stages). Before worker k >= 1 (B>1) or k >= 2 (B=1) captures,
#      worker-headroom-96.py live checks the floor plus that worker's estimate (exit 18 if short).
#      Then every worker must hold every block graph, all at batch B (coverage).
#   4. decode probe   5. freeze (coverage, batch-B signatures only, residents, 2 GiB floor)
#   6. post-freeze self-check: depth+3 prompts of the timed arm, selfcheck-94f.py must find no refusal
#   B=1 (control against the w93c references, the packet 95 path):
#   7. placement probe: 13 prompts, ten fixtures byte for byte against w93c
#   8. timed: 120 prompts of pipe-samp2-tsh-rep-wlean[-s1|-s3|-s4], against w93c
#   B=2/4:
#   7. reference arm (only if data/stability-01-batch<B>-prereg.json does not exist yet): the ten
#      fixtures in the fixed 'ref' arrangement, one job at a time (arm -b<B>-ref, depth B-1), not compared;
#      make-batch-oracle-96.py stores stability-01-b<B>-<fixture> and the prereg (exit 15 if refused).
#      If the references exist, they are checked to exist and this server must reproduce them.
#   8. proof arms: 'proof-neighbours' (other neighbours) and 'proof-slots' (other slots), same arm,
#      every clip byte-identical to its b<B> reference (check-batch-proof-96.py, exit 15 otherwise)
#   9. timed: 120 prompts of -b<B>-w<W> in the 'shift' order (batch composition varies), against b<B>
#  10. summary (reference set per arm, batch job seconds per batch and per clip, clips in flight, engine
#      busy per card, decode queue depth, context-sentry gate, closeness vs w93c); graceful stop on
#      proven quiescence (or idle-state after a failed arm).
#
# Index bases: 264000 + 1000 x (12 x layout + 3 x (W-1) + batch index), layout two-way/shard4-a/shard3-c =
# 0/1/2, batch 1/2/4 = 0/1/2. Capture pass base + 10 k, self-check +100, probe or reference +200,
# proof-neighbours +300, proof-slots +400, timed +500 (to +619).
#
# Exit codes as 95b (0 ok; 3 timed clips not exact; 4 fault latched; 5/6/7 the server could NOT be
# stopped safely and is still up; 8 preflight refused; 9 decode probe; 11 window probe; 13 interrupted;
# 14 summary/context-sentry gate; 15 references or proof failed; 16 capture/freeze refused; 17 self-check;
# 18 not enough memory, combination skipped; 12 an arm emitted the wrong clip sequence (a gap or a
# duplicate); 19 the timed arm's proof check rejected).
# 96r = run-campaign-96.sh with a repeat tag (run names and arm names end in -r<N> / r<N>, own index bases)
# and an optional timed-arm length, so a finished combination can be run again and run longer.
# Do not edit while running.
set -u
LAYOUT=${1:-}; WORKERS=${2:-}; BATCH=${3:-}; POOL=${4:-0}; REP=${5:-}; TIMED_ARG=${6:-120}; TIMED_BASE_ARG=${7:-}
case "$LAYOUT" in two-way) LI=0 ;; shard4-a) LI=1 ;; shard3-c) LI=2 ;; *) LI= ;; esac
case "$WORKERS" in 1|2|3|4) ;; *) LI= ;; esac
case "$BATCH" in 1) BI=0 ;; 2) BI=1 ;; 4) BI=2 ;; *) LI= ;; esac
case "$POOL" in 0) PSUF= ; PBASE=264000 ;; 1) PSUF=-p1 ; PBASE=300000 ;; *) LI= ;; esac
case "$REP" in 2|3|4) ;; *) LI= ;; esac
case "$TIMED_ARG" in *[!0-9]*|"") LI= ;; *) { [ "$TIMED_ARG" -ge 120 ] && [ "$TIMED_ARG" -le 9000 ]; } || LI= ;; esac
# The pipeline nodes accept clip_index up to 1,000,000 (ComfyUI rejects a larger literal before running the
# prompt; the first 96r run lost its timed arm that way). Short arms of repeats 2-4 stay below 736,000; the
# timed arm's base is given explicitly and must lie in 800,000 .. 1,000,000 - prompts.
case "$TIMED_BASE_ARG" in *[!0-9]*|"") LI= ;; *) { [ "$TIMED_BASE_ARG" -ge 800000 ] && [ $((TIMED_BASE_ARG + TIMED_ARG)) -le 1000000 ]; } || LI= ;; esac
[ -n "$LI" ] || { echo "usage: run-campaign-96r.sh <two-way|shard4-a|shard3-c> <1|2|3|4> <1|2|4> <0|1> <repeat 2-4> <timed prompts 120-9000> <timed index base 800000..>"; exit 8; }
IDX=$((12 * LI + 3 * (WORKERS - 1) + BI))
PLACEMENT=$LAYOUT
MODE=$LAYOUT-w$WORKERS-b$BATCH$PSUF-r$REP
TAG=$(echo $LAYOUT | tr -d -)w${WORKERS}b$BATCH${PSUF#-}r$REP
BASE=$((PBASE + 1000 * IDX + 100000 * REP))   # 96r: repeats live 100000 x repeat above the first runs
CAP_BASE=$BASE; SELF_BASE=$((BASE + 100)); PROBE_BASE=$((BASE + 200)); REF_BASE=$((BASE + 200))
PROOFN_BASE=$((BASE + 300)); PROOFS_BASE=$((BASE + 400))
# 96r: the timed arm's index base is the operator's 7th argument (unused block, checked above).
TIMED_BASE=$TIMED_BASE_ARG
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
R=/mnt/fast-ai/bench-results/ltx25-baseline-20260913
P=$R/prepared-encoder-batch-96
PY=/home/steve/.venvs/ltx25-baseline/bin/python
if [ $BATCH != 1 ]; then
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
MANIFEST=5822b050bdf5784ab62cc14e0b69f8c9612af26963e23b61605edd554eba049f
LANE=/home/steve/llm-optimizations/experiments/ltx25-b70
REPO=/home/steve/llm-optimizations
RUN_NAME=encoder-server-batch-96-$MODE
RUN=$R/$RUN_NAME
BASE_OUT=$LANE/data/batch-96
OUT=$BASE_OUT/$MODE
W93C=$LANE/data/stability-01-window-prereg.json
BPREREG=$LANE/data/stability-01-batch$BATCH-prereg.json
mkdir -p "$OUT"
step() { echo "=== $(date -u +%FT%TZ) [$MODE] $*"; }
save() { # commit message, [extra explicit repo-relative paths]
  local msg=$1; shift
  # Review finding 7: commit only these explicit paths, never whatever else is staged in the index.
  ( cd $REPO && git add -- "${OUT#$REPO/}" "$@" && git commit -q -m "LTX packet 96 ($MODE): $msg receipts

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" -- "${OUT#$REPO/}" "$@" ) >/dev/null 2>&1 && step "committed $msg" || step "commit of $msg failed (continuing)"
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
arm() { # name graph-arm count index-base client-timeout-s watch|- fixtures order [no-oracle]
  step "$1: arm $2, $3 prompts, index base $4, order $8${9:+, not compared}"
  local wpid= extra=()
  [ "${9:-}" = no-oracle ] && extra=(--no-oracle)
  ARMS_RUN="$ARMS_RUN $1"
  if [ "${6:-}" = watch ]; then rm -f "$SYNC_FLAG"; sync_watch $1 & wpid=$!; fi
  timeout $5 $PY -B $LANE/scripts/run-throughput-fixtures-96.py $1 --graph $P/graphs/graph-capture-all48-$2.json \
    --arm $2 --server-run $RUN --count $3 --index-base $4 --out $OUT --fixtures "$7" --order $8 --batch $BATCH "${extra[@]}"
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

missing_markers() { # done markers missing for jobs the server actually queued (batch-aware)
  timeout 120 $PY -B $LANE/scripts/missing-markers-96.py --root $R --run $RUN $ARMS_RUN || echo "marker-check-failed"
}

IDLE_N=0
pipeline_idle_once() { # 0 only if the queue is empty and the coverage node reports busy=0, running=0
  local name
  IDLE_N=$((IDLE_N + 1)); name=f96-$TAG-idle$IDLE_N
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
REF_RAN=0
summary_args() { # arms, pair and required proofs for the summary (pure; tested by test-packet96)
  # Review 2, finding 4: the reference arm is requested only if it ran on this server (REF_RAN=1);
  # on a second run the references already existed and the first proof arm is the sentry baseline.
  if [ $BATCH = 1 ]; then
    echo "--arm f96-$TAG-probe:placement-probe --arm f96-$TAG-timed:timed --pair f96-$TAG-probe:f96-$TAG-timed"
  elif [ "$REF_RAN" = 1 ]; then
    echo "--arm f96-$TAG-ref:reference --arm f96-$TAG-proofn:proof-neighbours --arm f96-$TAG-proofs:proof-slots --arm f96-$TAG-timed:timed --pair f96-$TAG-ref:f96-$TAG-timed --require-proof proof-neighbours.json --require-proof proof-slots.json --require-proof proof-timed.json"
  else
    echo "--arm f96-$TAG-proofn:proof-neighbours --arm f96-$TAG-proofs:proof-slots --arm f96-$TAG-timed:timed --pair f96-$TAG-proofn:f96-$TAG-timed --require-proof proof-neighbours.json --require-proof proof-slots.json --require-proof proof-timed.json"
  fi
}

summarize() { # the context-sentry gate (first exact pass vs timed arm): a failure fails the campaign (exit 14)
  timeout 300 $PY -B $LANE/scripts/summarize-campaign-96.py --run $RUN --out $OUT --batch $BATCH $(summary_args)
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
if [ $BATCH != 1 ]; then
  [ -n "${REF_N:-}" ] && [ -n "${TD:-}" ] && [ "$TIMED_K" -gt 0 ] || { step "could not derive the arm prompt counts from the packet graphs; refusing"; exit 8; }
  step "reference/proof arms: $REF_N prompts (sampler depth $REF_SD, decode depth $REF_DD) emit the $REF_K clips of each arrangement; timed: $TIMED_N prompts emit $TIMED_K clips"
fi
[ "$MANIFEST" != "__MANIFEST__" ] || { step "runner not pinned to a built packet; refusing"; exit 8; }
[ "$(sha256sum $P/manifest.json | cut -d' ' -f1)" = "$MANIFEST" ] || { step "packet manifest differs from the reviewed one; refusing"; exit 8; }
/home/steve/llm-optimizations/scripts/check-b70-runtime-pm.sh || { step "runtime PM unsafe; refusing to run"; exit 8; }
[ -f "$W93C" ] || { step "no $W93C (the w93c references, prompts and seeds); refusing"; exit 8; }
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
  || { step "server is not the packet 96 build; refusing"; exit 8; }
pid_is_server $PID $TICKS || { step "server pid $PID does not match $RUN_NAME identity; refusing"; exit 8; }
envval() { tr '\0' '\n' < /proc/$PID/environ 2>/dev/null | sed -n "s/^$1=//p"; }
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
[ "$NRD" = 1 ] && [ "$EDB" = 0 ] || { step "packet 96 needs NEOReadDebugKeys=1 EnableDeferBacking=0 on the server (found '$NRD' '$EDB'); refusing"; exit 8; }
mkdir -p $OUT
tr '\0' '\n' < /proc/$PID/environ | grep -E '^(NEOReadDebugKeys|EnableDeferBacking|ForceZeDeviceCanAccessPerReturnValue|SYCL_[A-Z0-9_]+|UR_[A-Z0-9_]+|ZE_[A-Z0-9_]+|ONEAPI_[A-Z0-9_]+|LTX_BUSY_WINDOWS|LTX_SAMPLER_[A-Z_]+)=' | sort > $OUT/runtime-environment.txt
SIGINT_IGN=$($PY -c "print(int(open('/proc/$PID/status').read().split('SigIgn:')[1].split()[0], 16) >> 1 & 1)")
[ "$SIGINT_IGN" = 0 ] || { step "the server ignores SIGINT (launch it with env --default-signal=INT); refusing"; exit 8; }
HEALTH=$($PY -c "import json;print('yes' if 'health_admission' in json.load(open('$RUN/server-identity.json')) else 'no')")
step "server pid $PID up, batch $BATCH, $WORKERS sampler jobs, shared pool $POOL, depth $DEPTH, busy timers off, SIGINT honoured, health admission: $HEALTH"
$PY -B $LANE/scripts/sample-gpu-engine-busy.py $PID $OUT/engine-busy.jsonl &
SAMPLER_PID=$!
step "engine-busy sampler pid $SAMPLER_PID (fdinfo only, no device access)"
step "rest 60 s after construction"
sleep 60

# ---- 1. text-window probe (serial) -----------------------------------------------------------
queue_empty || { step "queue not provably empty before the window probe"; finish 5; }
timeout 2400 $PY -B $LANE/scripts/run-text-window-probe.py f96-$TAG-wprobe --graph $P/graphs/text-window-probe.json --server-run $RUN
WPROBE_RC=$?
cp $RUN/text-window-probe-f96-$TAG-wprobe.json $OUT/ 2>/dev/null; sync
save "text-window probe (rc=$WPROBE_RC)"
[ $WPROBE_RC -eq 0 ] || { step "text-window probe did not qualify (rc=$WPROBE_RC)"; finish 11; }

# ---- 2. memory plan for batch-B graphs (nothing captured yet) ---------------------------------
if [ $BATCH != 1 ] || [ $POOL = 1 ]; then
  if ! $PY -B $LANE/scripts/worker-headroom-96.py plan $LAYOUT $WORKERS $BATCH $POOL --manifest $MANIFEST > $OUT/headroom-plan.json; then
    cat $OUT/headroom-plan.json
    step "batch-$BATCH graphs for one worker are predicted to break the 2 GiB floor under $LAYOUT: combination skipped (nothing captured)"
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
    timeout 120 $PY -B $LANE/scripts/run-capture-freeze-94.py f96-$TAG-room$k --graph $P/graphs/sampler-capture-coverage.json --server-run $RUN >/dev/null 2>&1
    cp $RUN/sampler-capture-coverage-f96-$TAG-room$k.json $OUT/ 2>/dev/null
    PREV=()   # review 2, finding 2: the previous worker's own before-reading, when there is one
    [ $((k - 1)) -ge $FIRST_LIVE ] && PREV=($RUN/sampler-capture-coverage-f96-$TAG-room$((k - 1)).json)
    if ! $PY -B $LANE/scripts/worker-headroom-96.py live $RUN/sampler-capture-coverage-f96-$TAG-room$k.json $LAYOUT $BATCH $POOL "${PREV[@]}" --manifest $MANIFEST > $OUT/headroom-w$k.json; then
      cat $OUT/headroom-w$k.json
      step "not enough memory for sampler worker $k at batch $BATCH under $LAYOUT: combination skipped (nothing captured for it)"
      save "memory floor: worker $k skipped"; finish 18
    fi
  fi
  timeout 120 $PY -B $LANE/scripts/run-sampler-pin-95.py f96-$TAG-pin$k $k --graph $P/graphs/sampler-pin.json --server-run $RUN
  [ $? -eq 0 ] || { step "pin to worker $k refused"; finish 16; }
  arm f96-$TAG-cap$k $CAP_ARM 1 $IDX_K 1800 - "$W93C" cycle no-oracle
  [ $ARM_RC -eq 0 ] || { step "capture-pass prompt $k ended rc=$ARM_RC"; finish $ARM_RC; }
  for i in $(seq 1 180); do [ -f $RUN/pipeline-done-sample-$IDX_K.json ] && break; sleep 5; done
  [ -f $RUN/pipeline-done-sample-$IDX_K.json ] || { step "sample job $IDX_K never finished"; finish 6; }
  sleep 5
done
queue_empty || { step "queue not provably empty after the capture pass"; finish 5; }
timeout 360 $PY -B $LANE/scripts/run-capture-freeze-94.py f96-$TAG-cover --graph $P/graphs/sampler-capture-coverage.json --server-run $RUN
COV_RC=$?
cp $RUN/sampler-capture-coverage-f96-$TAG-cover.json $OUT/ 2>/dev/null; sync
save "capture pass (coverage rc=$COV_RC)"
[ $COV_RC -eq 0 ] || { step "captures incomplete or not at batch $BATCH after one pinned prompt per worker: timed arms skipped"; finish 16; }
if [ $POOL = 1 ] && [ $WORKERS -ge 2 ]; then
  # Calibration for later pooled runs of this packet and layout: the last worker's measured pooled cost per
  # card (its room receipt, taken just before its capture, minus the coverage receipt just after the pass).
  LASTW=$((WORKERS - 1))
  if $PY -B $LANE/scripts/worker-headroom-96.py calibrate $OUT/sampler-capture-coverage-f96-$TAG-room$LASTW.json \
      $OUT/sampler-capture-coverage-f96-$TAG-cover.json $LAYOUT $BATCH $LASTW --manifest $MANIFEST --out $OUT/pool-calibration.json; then
    step "pool calibration written: $OUT/pool-calibration.json"
  else
    step "pool calibration could not be written (continuing; later runs fall back to the private-pool bound)"
  fi
  sync; save "pool calibration"
fi

# ---- 4. decode probe (serial) -----------------------------------------------------------------
step "settle 30 s"; sleep 30
queue_empty || { step "queue not provably empty before the decode probe"; finish 5; }
timeout 1500 $PY -B $LANE/scripts/run-decode-probe.py f96-$TAG-dprobe --graph $P/graphs/decode-replica-probe.json --server-run $RUN
DPROBE_RC=$?
cp $RUN/decode-probe-f96-$TAG-dprobe.json $OUT/ 2>/dev/null; sync
save "decode probe (rc=$DPROBE_RC)"
[ $DPROBE_RC -eq 0 ] || { step "decode probe did not pass (rc=$DPROBE_RC)"; finish 9; }

# ---- 5. the freeze ---------------------------------------------------------------------------
queue_empty || { step "queue not provably empty before the freeze"; finish 5; }
timeout 360 $PY -B $LANE/scripts/run-capture-freeze-94.py f96-$TAG-freeze --graph $P/graphs/sampler-capture-freeze.json --server-run $RUN
FREEZE_RC=$?
cp $RUN/sampler-capture-freeze-f96-$TAG-freeze.json $OUT/ 2>/dev/null; sync
save "freeze (rc=$FREEZE_RC)"
[ $FREEZE_RC -eq 0 ] || { step "freeze refused (rc=$FREEZE_RC; see the receipt): timed arms skipped"; finish 16; }

# ---- 6. post-freeze self-check through the exact timed path -------------------------------------
step "settle 15 s"; sleep 15
SELF_T0=$(date +%s)
if [ $BATCH = 1 ]; then
  arm f96-$TAG-self $TIMED_ARM $SELF_N $SELF_BASE 1800 - "$W93C" cycle
else
  arm f96-$TAG-self $TIMED_ARM $SELF_N $SELF_BASE 1800 - "$W93C" shift no-oracle
fi
SELF_RC=$ARM_RC
timeout 120 $PY -B $LANE/scripts/selfcheck-94f.py --root $R --run $RUN --prefix f96-$TAG-self --since $SELF_T0 > $OUT/selfcheck.json
SC_RC=$?
cat $OUT/selfcheck.json; sync; save "post-freeze self-check (arm rc=$SELF_RC, check rc=$SC_RC)"
{ [ $SELF_RC -eq 0 ] && [ $SC_RC -eq 0 ]; } || { step "post-freeze self-check FAILED (see selfcheck.json): timed arms skipped"; finish 17; }

if [ $BATCH = 1 ]; then
  # ---- B=1, 7. placement probe against w93c ----------------------------------------------------
  step "settle 30 s"; sleep 30
  arm f96-$TAG-probe pipe-samp2-tsh-win $PROBE_N $PROBE_BASE 1200 - "$W93C" cycle
  PROBE_RC=$ARM_RC
  EXACT=$($PY -c "import json;d=json.load(open('$OUT/f96-$TAG-probe-throughput.json'));r=[x for x in d['rows'] if not x['fill']];print(sum(1 for x in r if x['exact']), len({x['emitted_fixture'] for x in r if x['exact']}))" 2>/dev/null)
  step "placement probe: rc=$PROBE_RC, exact clips / fixtures: ${EXACT:-none}"
  { [ $PROBE_RC -eq 0 ] && [ "${EXACT##* }" = 10 ]; } || { step "batch 1 under $PLACEMENT is NOT byte-identical to the w93c references: timed arm refused"; finish 15; }
  # ---- B=1, 8. timed against w93c --------------------------------------------------------------
  step "settle 60 s"; sleep 60
  arm f96-$TAG-timed $TIMED_ARM $TIMED_N $TIMED_BASE 5400 watch "$W93C" cycle
  TIMED_RC=$ARM_RC
  [ $TIMED_RC -eq 0 ] || [ $TIMED_RC -eq 3 ] || { step "timed arm ended rc=$TIMED_RC"; finish $TIMED_RC; }
  finish $TIMED_RC
fi

# ---- B>1, 7. reference arm (only if the b<B> references do not exist yet) --------------------------
step "settle 30 s"; sleep 30
if [ -f "$BPREREG" ]; then
  step "batch-$BATCH references exist ($BPREREG): not regenerated; this server must reproduce them"
  $PY -c "
import json,sys
from pathlib import Path
d=json.load(open('$BPREREG')); R=Path('$R')
assert d['batch']==$BATCH and len(d['fixtures'])==10
for f in d['fixtures']:
    assert (R/'output/validation'/f['reference']/'tensors.safetensors').is_file(), f['reference']
    assert (R/'requests'/f['reference']/'history.json').is_file(), f['reference']
print('references present:', ', '.join(f['reference'] for f in d['fixtures']))" || { step "batch-$BATCH prereg exists but its references are incomplete; refusing"; finish 15; }
else
  arm f96-$TAG-ref $REF_ARM $REF_N $REF_BASE 1800 - "$W93C" ref no-oracle
  REF_RC=$ARM_RC
  REF_RAN=1
  [ $REF_RC -eq 0 ] || { step "reference arm ended rc=$REF_RC"; finish $REF_RC; }
  timeout 600 $PY -B $LANE/scripts/make-batch-oracle-96.py $OUT/f96-$TAG-ref-throughput.json --batch $BATCH \
    --run $RUN --manifest $MANIFEST --out $OUT --fixtures $W93C --prereg-out $BPREREG
  ORACLE_RC=$?
  sync; save "batch-$BATCH reference set (rc=$ORACLE_RC)" "${BPREREG#$REPO/}"
  [ $ORACLE_RC -eq 0 ] || { step "batch-$BATCH references refused (see batch$BATCH-reference-vs-w93c.json): proof and timed arms skipped"; finish 15; }
fi

# ---- B>1, 8. proof arms: other neighbours, other slots, byte-identical to b<B> ---------------------
step "settle 30 s"; sleep 30
arm f96-$TAG-proofn $REF_ARM $REF_N $PROOFN_BASE 1800 - "$BPREREG" proof-neighbours
PN_RC=$ARM_RC
$PY -B $LANE/scripts/check-batch-proof-96.py --prereg $BPREREG --arm $OUT/f96-$TAG-proofn-throughput.json --kind neighbours --expect-clips $REF_K --out $OUT/proof-neighbours.json >/dev/null
PNC_RC=$?
arm f96-$TAG-proofs $REF_ARM $REF_N $PROOFS_BASE 1800 - "$BPREREG" proof-slots
PS_RC=$ARM_RC
$PY -B $LANE/scripts/check-batch-proof-96.py --prereg $BPREREG --arm $OUT/f96-$TAG-proofs-throughput.json --kind slots --expect-clips $REF_K --out $OUT/proof-slots.json >/dev/null
PSC_RC=$?
sync; save "proof arms (neighbours rc=$PN_RC/$PNC_RC, slots rc=$PS_RC/$PSC_RC)"
{ [ $PN_RC -eq 0 ] && [ $PNC_RC -eq 0 ] && [ $PS_RC -eq 0 ] && [ $PSC_RC -eq 0 ]; } || \
  { step "a clip's bytes depended on its neighbours or its slot (or a proof arm failed): timed arm refused"; finish 15; }
step "proof arms passed: every clip byte-identical to its batch-$BATCH reference with other neighbours and other slots"

# ---- B>1, 9. timed arm against b<B> ---------------------------------------------------------------
step "settle 60 s"; sleep 60
arm f96-$TAG-timed $TIMED_ARM $TIMED_N $TIMED_BASE 5400 watch "$BPREREG" shift
TIMED_RC=$ARM_RC
$PY -B $LANE/scripts/check-batch-proof-96.py --prereg $BPREREG --arm $OUT/f96-$TAG-timed-throughput.json --kind timed --expect-clips $TIMED_K --out $OUT/proof-timed.json >/dev/null
PT_RC=$?
sync; save "timed proof check (rc=$PT_RC)"
[ $TIMED_RC -eq 0 ] || [ $TIMED_RC -eq 3 ] || { step "timed arm ended rc=$TIMED_RC"; finish $TIMED_RC; }
[ $TIMED_RC -eq 3 ] && finish 3
# Review finding 2: a rejected timed check fails the campaign even when every byte comparison passed.
[ $PT_RC -eq 0 ] || { step "timed arm proof check REJECTED (rc=$PT_RC; see proof-timed.json)"; finish 19; }
finish 0
