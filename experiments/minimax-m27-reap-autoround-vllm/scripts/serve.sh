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
USER_ATTN_DELAY_ALLREDUCE="${VLLM_MINIMAX_M2_ATTN_DELAY_ALLREDUCE:-}"
USER_QK_RMS_HELPER="${VLLM_MINIMAX_QK_RMS_XPU_HELPER:-}"
USER_QK_RMS_HELPER_MAX_TOKENS="${VLLM_MINIMAX_QK_RMS_XPU_HELPER_MAX_TOKENS:-}"
USER_QK_NORM_RESTORE_WEIGHT="${VLLM_MINIMAX_QK_NORM_RESTORE_WEIGHT:-}"
USER_QK_NORM_RESTORE_WEIGHT_MIN_TOKENS="${VLLM_MINIMAX_QK_NORM_RESTORE_WEIGHT_MIN_TOKENS:-}"
source /home/steve/llm-optimizations/repro/minimax-m27-b70-89tps-20260520/configs/promoted-env.sh
# Keep the repaired 192-expert logits WS path opt-in until this lane promotes it.
export VLLM_XPU_USE_LLM_SCALER_MOE_MINIMAX_LOGITS_WS="${USER_MINIMAX_LOGITS_WS:-0}"
# Mirror the quality harness defaults where needed; the older promoted env was
# tuned for a different MiniMax lane and can produce NaN logits through the
# OpenAI server when restore-weight is enabled.
export VLLM_MINIMAX_M2_ATTN_DELAY_ALLREDUCE="${USER_ATTN_DELAY_ALLREDUCE:-1}"
export VLLM_MINIMAX_QK_RMS_XPU_HELPER="${USER_QK_RMS_HELPER:-1}"
export VLLM_MINIMAX_QK_RMS_XPU_HELPER_MAX_TOKENS="${USER_QK_RMS_HELPER_MAX_TOKENS:-4}"
export VLLM_MINIMAX_QK_NORM_RESTORE_WEIGHT="${USER_QK_NORM_RESTORE_WEIGHT:-0}"
export VLLM_MINIMAX_QK_NORM_RESTORE_WEIGHT_MIN_TOKENS="${USER_QK_NORM_RESTORE_WEIGHT_MIN_TOKENS:-2}"
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

if [ -n "${VLLM_COMPILATION_CONFIG:-}" ]; then
  COMPILATION_CONFIG="$VLLM_COMPILATION_CONFIG"
else
  COMPILATION_CONFIG='{"use_inductor_graph_partition":true,"compile_sizes":[1],"cudagraph_mode":"PIECEWISE"}'
fi

FRONTEND_ARGS=()
ENABLE_AUTO_TOOL_CHOICE="${VLLM_ENABLE_AUTO_TOOL_CHOICE:-1}"
case "$ENABLE_AUTO_TOOL_CHOICE" in
  0|false|False|no|No)
    ;;
  *)
    FRONTEND_ARGS+=(--enable-auto-tool-choice)
    ;;
esac

if [ "${VLLM_TOOL_CALL_PARSER+x}" = x ]; then
  TOOL_CALL_PARSER="$VLLM_TOOL_CALL_PARSER"
else
  TOOL_CALL_PARSER="minimax_m2"
fi
if [ -n "$TOOL_CALL_PARSER" ] && [ "$TOOL_CALL_PARSER" != "none" ]; then
  FRONTEND_ARGS+=(--tool-call-parser "$TOOL_CALL_PARSER")
fi

if [ "${VLLM_REASONING_PARSER+x}" = x ]; then
  REASONING_PARSER="$VLLM_REASONING_PARSER"
else
  REASONING_PARSER="minimax_m2"
fi
if [ -n "$REASONING_PARSER" ] && [ "$REASONING_PARSER" != "none" ]; then
  FRONTEND_ARGS+=(--reasoning-parser "$REASONING_PARSER")
fi

if [ -n "${VLLM_GENERATION_CONFIG:-}" ]; then
  FRONTEND_ARGS+=(--generation-config "$VLLM_GENERATION_CONFIG")
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
  --stream-interval "${VLLM_STREAM_INTERVAL:-1}" \
  --gpu-memory-utilization "${VLLM_GPU_MEMORY_UTILIZATION:-0.95}" \
  --block-size 256 \
  --no-enable-prefix-caching \
  --compilation-config "$COMPILATION_CONFIG" \
  "${FRONTEND_ARGS[@]}" \
  "${EXTRA_ARGS[@]}"
