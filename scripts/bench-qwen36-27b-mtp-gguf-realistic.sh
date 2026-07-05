#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:19430}"
MODEL="${MODEL:-qwen36-27b-mtp-gguf-q4}"
SUITE="${SUITE:-repro/qwen36-27b-autoround-int4-b70/realistic-suite-v1.json}"
MAX_TOKENS="${MAX_TOKENS:-128}"
METRIC_TOKENS="${METRIC_TOKENS:-100}"
API_MODE="${API_MODE:-chat}"
OUT_DIR="${OUT_DIR:-data/qwen36-27b-mtp-gguf-q4-b70-baselines}"
LABEL="${LABEL:-llamacpp-mtp3-realistic128}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="${OUT:-$OUT_DIR/${LABEL}-$STAMP.json}"
REQUEST_EXTRA_JSON="${REQUEST_EXTRA_JSON:-{\"cache_prompt\":false}}"

mkdir -p "$OUT_DIR"

python3 scripts/bench-openai-realistic-suite.py \
  --base-url "$BASE_URL" \
  --model "$MODEL" \
  --api-mode "$API_MODE" \
  --suite "$SUITE" \
  --max-tokens "$MAX_TOKENS" \
  --metric-tokens "$METRIC_TOKENS" \
  --request-extra-json "$REQUEST_EXTRA_JSON" \
  --out "$OUT"

echo "$OUT"
