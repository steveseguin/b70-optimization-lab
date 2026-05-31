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

if [ ! -d "$MODEL" ]; then
  echo "Model directory is missing: $MODEL" >&2
  exit 1
fi

exec vllm serve "$MODEL" \
  --host "${VLLM_HOST:-0.0.0.0}" \
  --port "${VLLM_PORT:-18082}" \
  --trust-remote-code \
  --dtype float16 \
  --tensor-parallel-size 4 \
  --distributed-executor-backend mp \
  --max-model-len "${VLLM_MAX_MODEL_LEN:-32768}" \
  --max-num-batched-tokens "${VLLM_MAX_NUM_BATCHED_TOKENS:-512}" \
  --max-num-seqs "${VLLM_MAX_NUM_SEQS:-1}" \
  --gpu-memory-utilization "${VLLM_GPU_MEMORY_UTILIZATION:-0.95}" \
  --block-size 256 \
  --no-enable-prefix-caching \
  --enable-auto-tool-choice \
  --tool-call-parser "${VLLM_TOOL_CALL_PARSER:-minimax_m2}" \
  --reasoning-parser "${VLLM_REASONING_PARSER:-minimax_m2}" \
  --compilation-config '{"use_inductor_graph_partition":true,"compile_sizes":[1],"cudagraph_mode":"PIECEWISE"}' \
  "${EXTRA_ARGS[@]}"
