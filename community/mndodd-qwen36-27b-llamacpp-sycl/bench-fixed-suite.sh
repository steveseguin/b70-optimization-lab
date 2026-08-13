#!/usr/bin/env bash
set -euo pipefail

ENTRY_DIR=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
LAB_ROOT=$(CDPATH='' cd -- "$ENTRY_DIR/../.." && pwd)
BASE_URL=${BASE_URL:-http://127.0.0.1:18080}
MODEL=${MODEL:?Set MODEL to the same model identity exposed by the server}
OUT=${OUT:-/tmp/mndodd-qwen36-q8-realistic128.json}
API_MODE=${API_MODE:-completions}
HARNESS_SEED=${HARNESS_SEED:-1}
REQUEST_EXTRA_JSON=${REQUEST_EXTRA_JSON:-'{"cache_prompt":false,"seed":42,"temperature":0}'}

python3 "$LAB_ROOT/scripts/bench-openai-realistic-suite.py" \
    --base-url "$BASE_URL" \
    --model "$MODEL" \
    --api-mode "$API_MODE" \
    --suite "$LAB_ROOT/repro/qwen36-27b-autoround-int4-b70/realistic-suite-v1.json" \
    --max-tokens 128 \
    --metric-tokens 100 \
    --seed "$HARNESS_SEED" \
    --request-extra-json "$REQUEST_EXTRA_JSON" \
    --timeout 300 \
    --out "$OUT"

python3 - "$OUT" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    result = json.load(handle)
legacy = result["summary"]["tok_s_1_100_after_ttft"]["median"]
print(f"legacy_100_event_median={legacy:.12f}")
print(f"conventional_99_interval_median={legacy * 0.99:.12f}")
print(f"realistic_final_gate_passed={result['realistic_final_gate']['passed']}")
print(f"cached_tokens_all_zero={result['fresh_response_validity']['cached_tokens_all_zero']}")
PY
