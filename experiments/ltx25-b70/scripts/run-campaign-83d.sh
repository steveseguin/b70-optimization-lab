#!/bin/bash
# packet 83 endurance run (83d): warm installs the shard, then 120 prompts on the sharded two-clip arm.
# then a 120-prompt endurance stream on the sharded arm. Commits and pushes after every arm because the host
# freezes silently and zeroes unflushed files. No retries.
set -u
R=/mnt/fast-ai/bench-results/ltx25-baseline-20260913
P=$R/prepared-encoder-graph-capture-83
RUN=$R/encoder-server-graph-capture-83d
LANE=/home/steve/llm-optimizations/experiments/ltx25-b70
REPO=/home/steve/llm-optimizations
PY=/home/steve/.venvs/ltx25-baseline/bin/python
OUT=$LANE/data/graph-capture-83d
mkdir -p "$OUT"
step() { echo "=== $(date -u +%FT%TZ) $*"; }
save() { sync; ( cd $REPO && git add experiments/ltx25-b70/data/graph-capture-83d && git commit -q -m "LTX packet 83: $1 receipts

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
step "warm: 3 fixture prompts on the sharded arm (installs the encoder shard before first placement; captures)"
arm f83d-warm pipe-samp2-tsh 3 140900
step "endurance: 120 prompts on the sharded two-clip arm, load lock under sustained sampling"
arm f83d-endure pipe-samp2-tsh 120 145200
step campaign complete
