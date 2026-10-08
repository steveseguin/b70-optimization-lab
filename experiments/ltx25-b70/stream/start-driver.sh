#!/bin/bash
# Start the stream driver in Phase B only (warm-up already done on this server). Appends to the shared manifest.
set -u
W=/home/steve/ltx-stream/s97-stream01
cd /home/steve/llm-optimizations/experiments/ltx25-b70/stream
exec /home/steve/.venvs/ltx25-baseline/bin/python -B ltx_stream_driver.py --skip-warmup --work-dir $W \
  --manifest $W/manifest.jsonl --state $W/driver-state.json --sink-stats $W/sink-stats.json --in-flight 4 --max-ahead-seconds 300
