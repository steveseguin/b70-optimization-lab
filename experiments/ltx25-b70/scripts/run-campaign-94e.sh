#!/bin/bash
# 94e: the same campaign as run-campaign-94d.sh on the same packet (prepared-encoder-shard4-94d), with fresh request names (f94e-*),
# run names (encoder-server-shard4-94e-<mode>) and index bases (236000+), for the first boot on kernel 7.0.0-39. The 94d control
# attempt of 2026-10-04 14:53 UTC was stopped for the reboot after its window probe and burned the f94d-ctl names.
# Packet 94d (prepared-encoder-shard4-94d; supersedes 94, 94b and 94c): spread the transformer's 48 blocks
# over more cards. The placement is fixed when a server first loads the model, so each placement
# gets its own server launch and this runner takes the placement as its argument:
#
#   bash run-campaign-94e.sh control     (two-way 23/25, the baseline layout)   run 1
#   bash run-campaign-94e.sh shard3-c    (20/20/8 over xpu:0/1/2)               run 2
#   bash run-campaign-94e.sh shard4-a    (18/18/8/4 over xpu:0/1/2/3)           run 3
#
# The operator launches each server first (exact commands in notes/2026-10-04-packet-94-build.md):
#   env --default-signal=INT LTX_BUSY_WINDOWS=0 LTX_SAMPLER_PLACEMENT=<placement> ... --health-receipt <r>
#
# Per server, in order (every client call under `timeout`, waits on pids and files):
#   Dependency order (what installs what, who needs it):
#   1. text-window probe (serial): loader 420 loads the components; text gate 425 installs the
#      sharded graph encoder and two encode workers; captures the 1024 and window encoder graphs.
#      Needs nothing. Every window request later needs its pass.
#   2. SERIAL CAPTURE PASS (window prompts, so it needs 1): installs the resident fast path (431)
#      and the graph-capture gate (422), loads the transformer shards and the upsampler,
#      captures every sampler graph: one prompt at a time (fresh index base each, so no lookahead, no
#      encode-ahead, no decode-behind), waiting for its sample job to finish, then a coverage
#      check (graph sampler-capture-coverage, changes nothing); repeated (at most 8 prompts)
#      until every sampler block signature is captured on both sampler workers.
#      Before the freeze the server refuses any sampler request that is not alone.
#   3. decode probe (serial; needs the fast path's load lock from 2): first loads both VAEs wholly
#      onto xpu:3 in an explicit step (the capture pass decodes nothing, so they are still on their
#      offload device), then builds the VAE replica on xpu:1 (a load, so before the freeze).
#   4. freeze (needs 2 and 3): coverage again, every expected model resident on its card,
#      every card >= 2 GiB free; records the resident set; from then on no capture and no load.
#   5. PLACEMENT PROBE: 13 pipelined prompts of pipe-samp2-tsh-win, byte for byte against the
#      w93c references (all ten fixtures). Anything but 10/10 exact refuses the timed arms.
#   6. timed: pipe-samp2-tsh-rep-wlean, control 40 / candidates 80, against the w93c references
#   7. candidates only: fastest exact arm so far and faster than the control -> 160 more
#   8. summary (context-sentry gate probe vs timed, engine busy per card); graceful stop.
#
# Index bases (spaced by 300): control 236000/236300/236600; shard3-c 236900/237200/237500/237800;
# shard4-a 238100/238400/238700/239000 (capture pass/probe/timed/extra; the capture pass uses
# base, base+10, ... base+70).
#
# Exit codes: 0 all good; 3 an oracle mismatch in the timed arm; 1/2 arm error/timeout; 4 FAULT
# (server left up for incident review); 5 queue not provably empty; 6 jobs not provably finished;
# 7 stop failed; 8 pre-run refusal; 9 decode probe failed; 11 window probe negative; 13 runner
# interrupted (stop attempted); 14 context-sentry gate or summary failed; 15 placement probe not
# exact (timed arms refused); 16 freeze refused (memory floor, or captures incomplete after 8).
# Codes 5/6/7 mean the server could NOT be stopped safely and is still up.
# Do not edit while running.
set -u
MODE=${1:-}
case "$MODE" in
  control)  PLACEMENT=two-way;  TAG=ctl; CAP_BASE=236000; PROBE_BASE=236300; TIMED_BASE=236600; TIMED_N=40; EXTRA_BASE= ;;
  shard3-c) PLACEMENT=shard3-c; TAG=s3c; CAP_BASE=236900; PROBE_BASE=237200; TIMED_BASE=237500; TIMED_N=80; EXTRA_BASE=237800 ;;
  shard4-a) PLACEMENT=shard4-a; TAG=s4a; CAP_BASE=238100; PROBE_BASE=238400; TIMED_BASE=238700; TIMED_N=80; EXTRA_BASE=239000 ;;
  *) echo "usage: run-campaign-94e.sh control|shard3-c|shard4-a"; exit 8 ;;
esac
CAP_MAX=8; PROBE_N=13; EXTRA_N=160
R=/mnt/fast-ai/bench-results/ltx25-baseline-20260913
P=$R/prepared-encoder-shard4-94d
MANIFEST=cf13cd11b22f9e36b39747ba46dd90ed80c94ab139b5732501cec47ef46fccf3
LANE=/home/steve/llm-optimizations/experiments/ltx25-b70
REPO=/home/steve/llm-optimizations
PY=/home/steve/.venvs/ltx25-baseline/bin/python
RUN_NAME=encoder-server-shard4-94e-$MODE
RUN=$R/$RUN_NAME
BASE_OUT=$LANE/data/shard4-94e
OUT=$BASE_OUT/$MODE
PREREG=$LANE/data/stability-01-window-prereg.json
mkdir -p "$OUT"
step() { echo "=== $(date -u +%FT%TZ) [$MODE] $*"; }
save() {
  ( cd $REPO && git add "${OUT#$REPO/}" && git commit -q -m "LTX packet 94d ($MODE): $1 receipts

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

SUMMARY_RC=0
summarize() { # the context-sentry gate (probe pass vs timed arm): a failure fails the campaign (exit 14)
  local arms="--arm f94e-$TAG-probe:placement-probe --arm f94e-$TAG-timed:timed --arm f94e-$TAG-extra:extra"
  timeout 300 $PY -B $LANE/scripts/summarize-campaign-93.py --run $RUN --out $OUT $arms \
    --pair f94e-$TAG-probe:f94e-$TAG-timed
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
  || { step "server is not the packet 94d build; refusing"; exit 8; }
pid_is_server $PID $TICKS || { step "server pid $PID does not match $RUN_NAME identity; refusing"; exit 8; }
BW=$(tr '\0' '\n' < /proc/$PID/environ 2>/dev/null | sed -n 's/^LTX_BUSY_WINDOWS=//p')
[ "$BW" = 0 ] || { step "packet 94d is a speed comparison: launch the server with LTX_BUSY_WINDOWS=0 (found '$BW'); refusing"; exit 8; }
PL=$(tr '\0' '\n' < /proc/$PID/environ 2>/dev/null | sed -n 's/^LTX_SAMPLER_PLACEMENT=//p')
[ "${PL:-two-way}" = "$PLACEMENT" ] || { step "server placement is '${PL:-two-way}', this run needs '$PLACEMENT'; refusing"; exit 8; }
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
timeout 2400 $PY -B $LANE/scripts/run-text-window-probe.py f94e-$TAG-wprobe --graph $P/graphs/text-window-probe.json --server-run $RUN
WPROBE_RC=$?
cp $RUN/text-window-probe-f94e-$TAG-wprobe.json $OUT/ 2>/dev/null; sync
save "text-window probe (rc=$WPROBE_RC)"
[ $WPROBE_RC -eq 0 ] || { step "text-window probe did not qualify (rc=$WPROBE_RC)"; finish 11; }

# ---- 2. serial capture pass until both sampler workers hold every graph -------------------------
COVERED=0
for k in $(seq 0 $((CAP_MAX - 1))); do
  IDX=$((CAP_BASE + 10 * k))
  queue_empty || { step "queue not provably empty in the capture pass"; finish 5; }
  arm f94e-$TAG-cap$k pipe-samp2-tsh-win 1 $IDX 1800 - "$PREREG"
  [ $ARM_RC -eq 0 ] || { step "capture-pass prompt $k ended rc=$ARM_RC"; finish $ARM_RC; }
  for i in $(seq 1 180); do [ -f $RUN/pipeline-done-sample-$IDX.json ] && break; sleep 5; done
  [ -f $RUN/pipeline-done-sample-$IDX.json ] || { step "sample job $IDX never finished"; finish 6; }
  sleep 5
  queue_empty || { step "queue not provably empty after capture prompt $k"; finish 5; }
  timeout 360 $PY -B $LANE/scripts/run-capture-freeze-94.py f94e-$TAG-cover$k --graph $P/graphs/sampler-capture-coverage.json --server-run $RUN
  COV_RC=$?
  cp $RUN/sampler-capture-coverage-f94e-$TAG-cover$k.json $OUT/ 2>/dev/null
  step "coverage after capture prompt $k: rc=$COV_RC"
  [ $COV_RC -eq 0 ] && { COVERED=1; break; }
done
sync; save "capture pass (covered=$COVERED)"
[ $COVERED = 1 ] || { step "captures still incomplete after $CAP_MAX serial prompts: timed arms skipped"; finish 16; }

# ---- 3. decode probe (serial; needs the fast path installed by the capture pass) ---------------
step "settle 30 s"; sleep 30
queue_empty || { step "queue not provably empty before the decode probe"; finish 5; }
timeout 1500 $PY -B $LANE/scripts/run-decode-probe.py f94e-$TAG-dprobe --graph $P/graphs/decode-replica-probe.json --server-run $RUN
DPROBE_RC=$?
cp $RUN/decode-probe-f94e-$TAG-dprobe.json $OUT/ 2>/dev/null; sync
save "decode probe (rc=$DPROBE_RC)"
[ $DPROBE_RC -eq 0 ] || { step "decode probe did not pass (rc=$DPROBE_RC)"; finish 9; }

# ---- 4. the freeze: coverage, expected residents, 2 GiB floor; then no capture and no load -------
queue_empty || { step "queue not provably empty before the freeze"; finish 5; }
timeout 360 $PY -B $LANE/scripts/run-capture-freeze-94.py f94e-$TAG-freeze --graph $P/graphs/sampler-capture-freeze.json --server-run $RUN
FREEZE_RC=$?
cp $RUN/sampler-capture-freeze-f94e-$TAG-freeze.json $OUT/ 2>/dev/null; sync
save "freeze (rc=$FREEZE_RC)"
[ $FREEZE_RC -eq 0 ] || { step "freeze refused (rc=$FREEZE_RC; see the receipt): timed arms skipped"; finish 16; }

# ---- 5. placement probe: ten fixtures byte for byte against the w93c references ----------------
step "settle 30 s"; sleep 30
arm f94e-$TAG-probe pipe-samp2-tsh-win $PROBE_N $PROBE_BASE 1200 - "$PREREG"
PROBE_RC=$ARM_RC
EXACT=$($PY -c "import json;d=json.load(open('$OUT/f94e-$TAG-probe-throughput.json'));r=[x for x in d['rows'] if not x['fill']];print(sum(1 for x in r if x['exact']), len({x['emitted_fixture'] for x in r if x['exact']}))" 2>/dev/null)
step "placement probe: rc=$PROBE_RC, exact clips / fixtures: ${EXACT:-none}"
{ [ $PROBE_RC -eq 0 ] && [ "${EXACT##* }" = 10 ]; } || { step "placement $PLACEMENT is NOT byte-identical to the references: timed arms refused"; finish 15; }

# ---- 6. timed arm, 7. extra prompts for the best candidate --------------------------------------
step "settle 60 s"; sleep 60
arm f94e-$TAG-timed pipe-samp2-tsh-rep-wlean $TIMED_N $TIMED_BASE 3000 watch "$PREREG"
TIMED_RC=$ARM_RC
[ $TIMED_RC -eq 0 ] || [ $TIMED_RC -eq 3 ] || { step "timed arm ended rc=$TIMED_RC"; finish $TIMED_RC; }
if [ -n "$EXTRA_BASE" ] && [ $TIMED_RC -eq 0 ]; then
  if $PY -B $LANE/scripts/decide-94.py $BASE_OUT $MODE; then
    step "settle 60 s"; sleep 60
    arm f94e-$TAG-extra pipe-samp2-tsh-rep-wlean $EXTRA_N $EXTRA_BASE 5400 watch "$PREREG"
    [ $ARM_RC -eq 0 ] || [ $ARM_RC -eq 3 ] || { step "extra arm ended rc=$ARM_RC"; finish $ARM_RC; }
    [ $ARM_RC -eq 3 ] && TIMED_RC=3
  fi
fi
finish $TIMED_RC
