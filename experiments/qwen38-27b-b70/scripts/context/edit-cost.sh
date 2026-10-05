#!/usr/bin/env bash
# Client for MU_MODE=serve_run with the exact prefix cache on: what an edit at different places of a long context
# costs (wait for the first token, tokens served from the cache). Needs BASE_URL, MODEL_NAME, OUT_DIR.
set -u
S=$(cd "$(dirname "$0")/.." && pwd)
PY=${PY:-$HOME/.venvs/vllm-xpu/bin/python}
"$PY" "$S/qwen38-fp8-edit-cost-probe.py" --base-url "$BASE_URL" --model "$MODEL_NAME" --lengths "${EDIT_LENGTHS:-30000,120000,200000}" \
  --out "$OUT_DIR/edit-cost.json" 2>&1 | tee "$OUT_DIR/edit-cost.log"
