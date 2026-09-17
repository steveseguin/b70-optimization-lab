#!/bin/bash
# Packet 63 campaign: one server; forward timing, resident fast path (timed, then on),
# save-behind rerun, pipe control. Commits and pushes after every arm because the host
# freezes silently and zeroes unflushed files. No retries.
set -u
R=/mnt/fast-ai/bench-results/ltx25-baseline-20260913
P=$R/prepared-encoder-graph-capture-68
RUN=$R/encoder-server-graph-capture-68
LANE=/home/steve/llm-optimizations/experiments/ltx25-b70
REPO=/home/steve/llm-optimizations
PY=/home/steve/.venvs/ltx25-baseline/bin/python
OUT=$LANE/data/graph-capture-68
mkdir -p "$OUT"
step() { echo "=== $(date -u +%FT%TZ) $*"; }
save() { sync; ( cd $REPO && git add experiments/ltx25-b70/data/graph-capture-68 && git commit -q -m "LTX packet 68: $1 receipts

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>" && git push -q origin main ) >/dev/null 2>&1 && step "committed $1" || step "commit of $1 failed (continuing)"; }
arm() { # name graph-arm count index-base
  step "$1: arm $2, $3 prompts"
  $PY -B $LANE/scripts/run-throughput-fixtures.py $1 --graph $P/graphs/graph-capture-all48-$2.json \
    --arm $2 --server-run $RUN --count $3 --index-base $4 --out $OUT || { step "$1 failed"; save "$1 (failed)"; exit 1; }
  save "$1"
}
/home/steve/llm-optimizations/scripts/check-b70-runtime-pm.sh || { step "runtime PM unsafe; refusing to run"; exit 1; }
step waiting for server health
for i in $(seq 1 360); do
  [ -f $R/FAULT.json ] && { step FAULT latched; exit 1; }
  curl -sf http://127.0.0.1:8188/queue >/dev/null 2>&1 && break
  sleep 5
done
curl -sf http://127.0.0.1:8188/queue >/dev/null || { step server never answered; exit 1; }
PID=$($PY -c "import json;print(json.load(open('$RUN/server-identity.json'))['pid'])")
step server pid $PID up
step 1 warm clip on the pipe graph
$PY -B $LANE/scripts/run-graph-capture-clip.py g68-warm --pid $PID --server-run $RUN --out $OUT \
  --graph $P/graphs/graph-capture-all48-pipe.json --mode graph --clip-index 900 || { step warm failed; exit 1; }
save warm
arm f68-proof pipe-batchproof 2 1000
step campaign complete
