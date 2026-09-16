#!/bin/bash
# Packet 61 campaign: one server, upsampler gate arms in rising risk order. No retries.
# 1 warm clip (pipe graph, boat oracle)  2 pipe-uptime: eager upsampler timing, 12 fixtures
# 3 pipe-up: captured upsampler, 20 fixtures  4 pipe control, 12 fixtures. pipe-samp is retired.
set -u
R=/mnt/fast-ai/bench-results/ltx25-baseline-20260913
P=$R/prepared-encoder-graph-capture-61
RUN=$R/encoder-server-graph-capture-61
LANE=/home/steve/llm-optimizations/experiments/ltx25-b70
PY=/home/steve/.venvs/ltx25-baseline/bin/python
OUT=$LANE/data/graph-capture-61
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
step 1 warm clip on the pipe graph
$PY -B $LANE/scripts/run-graph-capture-clip.py g61-warm --pid $PID --server-run $RUN --out $OUT \
  --graph $P/graphs/graph-capture-all48-pipe.json --mode graph --clip-index 900 || { step warm failed; exit 1; }
step 2 upsampler eager timing, pipe-uptime arm, 12 prompts
$PY -B $LANE/scripts/run-throughput-fixtures.py f61-uptime --graph $P/graphs/graph-capture-all48-pipe-uptime.json \
  --arm pipe-uptime --server-run $RUN --count 12 --index-base 1000 --out $OUT || { step uptime stream failed; exit 1; }
step 3 upsampler graph capture, pipe-up arm, 20 prompts
$PY -B $LANE/scripts/run-throughput-fixtures.py f61-up --graph $P/graphs/graph-capture-all48-pipe-up.json \
  --arm pipe-up --server-run $RUN --count 20 --index-base 2000 --out $OUT || { step pipe-up stream failed; exit 1; }
step 4 pipe control after the candidate, 12 prompts
$PY -B $LANE/scripts/run-throughput-fixtures.py f61-pipe --graph $P/graphs/graph-capture-all48-pipe.json \
  --arm pipe --server-run $RUN --count 12 --index-base 3000 --out $OUT || { step pipe control failed; exit 1; }
step campaign complete
