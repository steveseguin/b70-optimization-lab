#!/bin/bash
# packet 84 (23/25 split + cross-stage fingerprints): warm installs the shard and captures,
# then a 30-prompt sharded two-clip arm against the oracles, then the 120-prompt endurance.
# Commits and pushes after every arm because the host freezes silently and zeroes unflushed
# files. No retries.
set -u
R=/mnt/fast-ai/bench-results/ltx25-baseline-20260913
P=$R/prepared-encoder-graph-capture-84
RUN=$R/encoder-server-graph-capture-84
LANE=/home/steve/llm-optimizations/experiments/ltx25-b70
REPO=/home/steve/llm-optimizations
PY=/home/steve/.venvs/ltx25-baseline/bin/python
OUT=$LANE/data/graph-capture-84
mkdir -p "$OUT"
step() { echo "=== $(date -u +%FT%TZ) $*"; }
save() { sync; ( cd $REPO && git add experiments/ltx25-b70/data/graph-capture-84 && git commit -q -m "LTX packet 84: $1 receipts

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
step "warm: 3 fixture prompts on the sharded arm (installs the 23/25 shard; captures)"
arm f84-warm pipe-samp2-tsh 3 170900
step "tsh: 30 prompts on the sharded two-clip arm (oracle gate + first timing)"
arm f84-tsh pipe-samp2-tsh 30 171000
step "endurance: 120 prompts on the sharded two-clip arm (instrumented; bird-clip watch)"
arm f84-endure pipe-samp2-tsh 120 175200
step campaign complete
