#!/usr/bin/env bash
# Client for MU_MODE=serve_run with the exact prefix cache on: how reliably does the model recall codes from a long
# context, by length? One ledger per form, read once at growing lengths; ten different six-code questions per length
# (60 codes spread over the whole text), each served from the cache except its own last tokens. At 120,000 tokens the
# first question is asked again cold (own cache namespace) and compared token for token.
# Needs BASE_URL, MODEL_NAME, OUT_DIR. notes/2026-10-05-context-window-prereg.md
set -u
S=$(cd "$(dirname "$0")/.." && pwd)
PY=${PY:-$HOME/.venvs/vllm-xpu/bin/python}
LENGTHS=${RECALL_LENGTHS:-60000,120000,160000,200000,230000,250000}
for style in prose ledger; do
  curl -sf -m 10 "$BASE_URL/health" >/dev/null || { echo "server gone before $style"; exit 3; }
  "$PY" "$S/qwen38-fp8-long-context-probe.py" --base-url "$BASE_URL" --model "$MODEL_NAME" --api chat --style "$style" \
    --one-ledger --lengths "$LENGTHS" --question-sets "${RECALL_SETS:-10}" --cold-check "${RECALL_COLD:-120000}" \
    --out "$OUT_DIR/recall-$style.json" 2>&1 | tee "$OUT_DIR/recall-$style.log"
done
