#!/bin/bash
# Packet 62 campaign: one server; phase-timed upsampler, captured upsampler, save-behind, pipe control. No retries.
# The upsampler gate now restores itself when arms switch its mode.
# pipe-samp is retired.
set -u
R=/mnt/fast-ai/bench-results/ltx25-baseline-20260913
P=$R/prepared-encoder-graph-capture-62
RUN=$R/encoder-server-graph-capture-62
LANE=/home/steve/llm-optimizations/experiments/ltx25-b70
PY=/home/steve/.venvs/ltx25-baseline/bin/python
OUT=$LANE/data/graph-capture-62
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
$PY -B $LANE/scripts/run-graph-capture-clip.py g62-warm --pid $PID --server-run $RUN --out $OUT \
  --graph $P/graphs/graph-capture-all48-pipe.json --mode graph --clip-index 900 || { step warm failed; exit 1; }
step 2 phase-timed upsampler, pipe-upphase arm, 12 prompts
$PY -B $LANE/scripts/run-throughput-fixtures.py f62-phase --graph $P/graphs/graph-capture-all48-pipe-upphase.json \
  --arm pipe-upphase --server-run $RUN --count 12 --index-base 1000 --out $OUT || { step phase stream failed; exit 1; }
step 3 captured upsampler, pipe-up arm, 20 prompts
$PY -B $LANE/scripts/run-throughput-fixtures.py f62-up --graph $P/graphs/graph-capture-all48-pipe-up.json \
  --arm pipe-up --server-run $RUN --count 20 --index-base 2000 --out $OUT || { step pipe-up stream failed; exit 1; }
step 4 captured upsampler plus save-behind, pipe-up-save arm, 20 prompts
$PY -B $LANE/scripts/run-throughput-fixtures.py f62-upsave --graph $P/graphs/graph-capture-all48-pipe-up-save.json \
  --arm pipe-up-save --server-run $RUN --count 20 --index-base 3000 --out $OUT || { step pipe-up-save stream failed; exit 1; }
step 5 pipe control after the candidates, 12 prompts
$PY -B $LANE/scripts/run-throughput-fixtures.py f62-pipe --graph $P/graphs/graph-capture-all48-pipe.json \
  --arm pipe --server-run $RUN --count 12 --index-base 4000 --out $OUT || { step pipe control failed; exit 1; }
step campaign complete
