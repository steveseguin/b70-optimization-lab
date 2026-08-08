#!/usr/bin/env bash
# Benchmark qwen36-27b (INT4, sym_int4, fp8 KV, MTP) on localhost:8001 (GPU 0)
# Same methodology as bench-qwen36-35b-int4-b2-8002.sh — one run per model.
set -euo pipefail

BASE_DIR="$(cd "$(dirname "$0")" && pwd)"
RESULTS_DIR="$BASE_DIR/results"
mkdir -p "$RESULTS_DIR"

TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
RESULT_JSON="$RESULTS_DIR/bench-qwen36-27b-int4-b2-${TIMESTAMP}.json"
RESULT_CSV="$RESULTS_DIR/bench-qwen36-27b-int4-b2-${TIMESTAMP}.csv"

echo "=== llama-benchy: qwen36-27b (INT4 b2, 1 GPU) ==="
echo "Base URL: http://localhost:8001/v1"
echo "Results:  $RESULT_JSON  $RESULT_CSV"
echo ""

# Activate venv
source "$BASE_DIR/.venv/bin/activate"

# Run once with JSON (most detailed data)
llama-benchy \
  --base-url http://localhost:8001/v1 \
  --model qwen36-27b \
  --latency-mode generation \
  --depth 0 4096 8192 16384 32768 \
  --pp 2048 \
  --tg 1024 \
  --runs 5 \
  --format json \
  --save-result "$RESULT_JSON"

# Convert JSON to CSV (correct key: benchmarks, not results)
python3 -c "
import json, csv, sys
with open('$RESULT_JSON') as f:
    data = json.load(f)
rows = data.get('benchmarks', data.get('results', []))
if rows:
    writer = csv.writer(sys.stdout)
    writer.writerow(rows[0].keys())
    for row in rows:
        writer.writerow(row.values())
else:
    print('No results found in JSON', file=sys.stderr)
    sys.exit(1)
" > "$RESULT_CSV"

echo ""
echo "=== DONE ==="
echo "JSON results: $RESULT_JSON"
echo "CSV results:  $RESULT_CSV"