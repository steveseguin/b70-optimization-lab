#!/bin/bash
# Packet 58 campaign: one server, four arms in rising risk order. No retries.
# 1 warm clip (pipe graph, boat oracle)  2 serial ten-fixture stream (graph-text)
# 3 three-stage pipe ten-fixture stream   4 pipelined-sampler ten-fixture stream
set -u
R=/mnt/fast-ai/bench-results/ltx25-baseline-20260913
P=$R/prepared-encoder-graph-capture-58
RUN=$R/encoder-server-graph-capture-58
LANE=/home/steve/llm-optimizations/experiments/ltx25-b70
PY=/home/steve/.venvs/ltx25-baseline/bin/python
OUT=$LANE/data/graph-capture-58
mkdir -p "$OUT"
step() { echo "=== $(date -u +%FT%TZ) $*"; }
step waiting for server health
for i in $(seq 1 360); do
  [ -f $R/FAULT.json ] && { step FAULT latched; exit 1; }
  curl -sf http://127.0.0.1:8188/queue >/dev/null 2>&1 && break
  sleep 5
done
curl -sf http://127.0.0.1:8188/queue >/dev/null || { step server never answered; exit 1; }
PID=$($PY -c "import json;print(json.load(open('$RUN/server-identity.json'))['pid'])")
step server pid $PID up
step "1 warm clip already passed on this server: g58-warm exact; skipping"
step 2 serial ten-fixture stream, graph-text arm
$PY -B $LANE/scripts/run-throughput-fixtures.py f58-ser --graph $P/graphs/graph-capture-all48-graph-text.json \
  --arm graph-text --server-run $RUN --count 12 --index-base 1000 --out $OUT || { step serial stream failed; exit 1; }
step 3 three-stage pipe ten-fixture stream
$PY -B $LANE/scripts/run-throughput-fixtures.py f58-pipe --graph $P/graphs/graph-capture-all48-pipe.json \
  --arm pipe --server-run $RUN --count 20 --index-base 2000 --out $OUT || { step pipe stream failed; exit 1; }
step 4 pipelined-sampler ten-fixture stream
$PY -B $LANE/scripts/run-throughput-fixtures.py f58-psamp --graph $P/graphs/graph-capture-all48-pipe-samp.json \
  --arm pipe-samp --server-run $RUN --count 20 --index-base 3000 --out $OUT || { step pipe-samp stream failed; exit 1; }
step campaign complete
