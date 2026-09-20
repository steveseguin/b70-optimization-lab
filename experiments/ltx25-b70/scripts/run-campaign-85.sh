#!/bin/bash
# packet 85 (fusion on the two-clip sharded arm): warm installs the 23/25 shard, fuses the
# qualifying projection groups (the gate proves each bit-for-bit at install), captures the
# fused blocks, then a 30-prompt oracle arm. Control is f84-tsh on server 84 (same boot;
# same-boot server-to-server noise measured at 0.03% across 83c/83e). Commits after every arm.
set -u
R=/mnt/fast-ai/bench-results/ltx25-baseline-20260913
P=$R/prepared-encoder-graph-capture-85
RUN=$R/encoder-server-graph-capture-85
LANE=/home/steve/llm-optimizations/experiments/ltx25-b70
REPO=/home/steve/llm-optimizations
PY=/home/steve/.venvs/ltx25-baseline/bin/python
OUT=$LANE/data/graph-capture-85
mkdir -p "$OUT"
step() { echo "=== $(date -u +%FT%TZ) $*"; }
save() { sync; ( cd $REPO && git add experiments/ltx25-b70/data/graph-capture-85 && git commit -q -m "LTX packet 85: $1 receipts

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
step "warm: 3 fixture prompts on the fused sharded arm (shard, fusion proofs, capture)"
arm f85-warm pipe-fuse2-tsh 3 180900
step "tsh: 30 prompts on the fused sharded arm (oracle gate + timing vs f84-tsh control)"
arm f85-tsh pipe-fuse2-tsh 30 181000
step "endurance: 120 prompts on the fused sharded arm"
arm f85-endure pipe-fuse2-tsh 120 185200
step campaign complete
