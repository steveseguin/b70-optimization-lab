#!/usr/bin/env bash
set -euo pipefail

EXTRA_ARGS=("$@")
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
set -a
source "$ROOT/configs/reap.env"
set +a

source "$VENV/bin/activate"
set +u
source /opt/intel/oneapi/compiler/2025.3/env/vars.sh >/dev/null 2>&1
set -u
USER_MINIMAX_LOGITS_WS="${VLLM_XPU_USE_LLM_SCALER_MOE_MINIMAX_LOGITS_WS:-}"
source /home/steve/llm-optimizations/repro/minimax-m27-b70-89tps-20260520/configs/promoted-env.sh
# Keep the repaired 192-expert logits WS path opt-in until this lane promotes it.
export VLLM_XPU_USE_LLM_SCALER_MOE_MINIMAX_LOGITS_WS="${USER_MINIMAX_LOGITS_WS:-0}"
# Short REAP prefill shapes corrupt under the compiled prefill wrapper; keep decode compiled.
export VLLM_XPU_SKIP_COMPILED_PREFILL=1
if [ "${CCL_IPC+x}" = x ]; then
  if [ "$CCL_IPC" = "default" ]; then
    unset CCL_ZE_IPC_EXCHANGE
  else
    export CCL_ZE_IPC_EXCHANGE="$CCL_IPC"
  fi
fi

mkdir -p "$REAP_OUTDIR/quality"

exec /home/steve/llm-optimizations/scripts/run-vllm-minimax-quality-check.py \
  --mode graph \
  --model "$MODEL" \
  --out "$REAP_OUTDIR/quality/quality-smoke-$(date -u +%Y%m%dT%H%M%SZ).json" \
  --max-tokens "${QUALITY_MAX_TOKENS:-512}" \
  --runs "${QUALITY_RUNS:-1}" \
  --tensor-parallel-size "${TP:-4}" \
  --dtype "${DTYPE:-float16}" \
  --max-model-len "${MAX_MODEL_LEN:-2048}" \
  --max-num-batched-tokens "${MAX_BATCHED_TOKENS:-512}" \
  --max-num-seqs "${MAX_NUM_SEQS:-1}" \
  --block-size 256 \
  --disable-prefix-caching \
  --vllm-cache-root "$VLLM_CACHE_ROOT" \
  --skip-compiled-prefill \
  "${EXTRA_ARGS[@]}"
