#!/usr/bin/env bash
set -euo pipefail

PASSTHROUGH_ARGS=("$@")
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
set -a
source "$ROOT/configs/reap.env"
set +a

set +u
source /opt/intel/oneapi/compiler/2025.3/env/vars.sh >/dev/null 2>&1
set -u
USER_ENV_OVERRIDE_NAMES=(
  VLLM_XPU_USE_LLM_SCALER_MOE_MINIMAX_LOGITS
  VLLM_XPU_USE_LLM_SCALER_MOE_MINIMAX_LOGITS_WS
  VLLM_XPU_USE_LLM_SCALER_MOE_WS
  VLLM_XPU_COMPILE_ALLREDUCE_CUSTOM_OP
  VLLM_XPU_CUSTOM_ALLREDUCE_CLONE_INPUT
  VLLM_MINIMAX_MOE_OUTPUT_ALLREDUCE_INSIDE_CUSTOM_OP
  VLLM_MINIMAX_MOE_FULL_FORWARD_CUSTOM_OP
  VLLM_MINIMAX_MOE_FULL_FORWARD_CUSTOM_OP_MAX_TOKENS
  VLLM_MINIMAX_MOE_DELAY_ALLREDUCE
  VLLM_MINIMAX_MOE_FINAL_INPLACE_ALLREDUCE
  VLLM_MINIMAX_M2_ATTN_DELAY_ALLREDUCE
  VLLM_MINIMAX_M2_DIST_RESIDUAL_ALLREDUCE
  VLLM_MINIMAX_M2_CLONE_FINAL_HIDDEN
  VLLM_MINIMAX_QK_RMS_XPU_HELPER
  VLLM_MINIMAX_QK_RMS_XPU_HELPER_MAX_TOKENS
  VLLM_MINIMAX_QK_RMS_APPLY_TP_SCALE
  VLLM_MINIMAX_QK_RMS_POST_AR_APPLY_CUSTOM_OP
  VLLM_MINIMAX_POST_ATTN_NORM_MOE_CUSTOM_OP
  VLLM_MINIMAX_POST_ATTN_NORM_MOE_CUSTOM_OP_MAX_TOKENS
  VLLM_XPU_LLM_SCALER_MOE_CACHE_MINIMAX_LOGITS_OP
  VLLM_XPU_LLM_SCALER_MOE_MINIMAX_SKIP_REDUNDANT_CONTIGUOUS
  VLLM_XPU_EAGER_FOR_UNCOVERED_COMPILE_RANGES
)
declare -A USER_ENV_OVERRIDES=()
for name in "${USER_ENV_OVERRIDE_NAMES[@]}"; do
  if [ "${!name+x}" = x ]; then
    USER_ENV_OVERRIDES["$name"]="${!name}"
  fi
done
source /home/steve/llm-optimizations/repro/minimax-m27-b70-89tps-20260520/configs/promoted-env.sh
# Keep the repaired 192-expert logits WS path opt-in until this lane promotes it.
if [[ -v 'USER_ENV_OVERRIDES[VLLM_XPU_USE_LLM_SCALER_MOE_MINIMAX_LOGITS_WS]' ]]; then
  export VLLM_XPU_USE_LLM_SCALER_MOE_MINIMAX_LOGITS_WS="${USER_ENV_OVERRIDES[VLLM_XPU_USE_LLM_SCALER_MOE_MINIMAX_LOGITS_WS]}"
else
  export VLLM_XPU_USE_LLM_SCALER_MOE_MINIMAX_LOGITS_WS=0
fi
for name in "${USER_ENV_OVERRIDE_NAMES[@]}"; do
  if [[ "$name" != "VLLM_XPU_USE_LLM_SCALER_MOE_MINIMAX_LOGITS_WS" && -v "USER_ENV_OVERRIDES[$name]" ]]; then
    export "$name=${USER_ENV_OVERRIDES[$name]}"
  fi
done
# Short REAP prefill shapes corrupt under the compiled prefill wrapper; keep decode compiled.
export VLLM_XPU_SKIP_COMPILED_PREFILL=1

export OUTDIR="${OUTDIR:-$REAP_OUTDIR/decode}"
export TP="${TP:-4}"
export DTYPE="${DTYPE:-float16}"
export MAX_MODEL_LEN="${MAX_MODEL_LEN:-2048}"
export MAX_BATCHED_TOKENS="${MAX_BATCHED_TOKENS:-512}"
export MAX_NUM_SEQS="${MAX_NUM_SEQS:-1}"
export INPUT_LEN="${INPUT_LEN:-512}"
export OUTPUT_LEN="${OUTPUT_LEN:-1536}"
export NUM_PROMPTS="${NUM_PROMPTS:-1}"
export XPU_GRAPH="${XPU_GRAPH:-1}"
export USE_LLM_SCALER_MOE="${USE_LLM_SCALER_MOE:-1}"
export RUN_TIMEOUT="${RUN_TIMEOUT:-45m}"
export SHM_STALL_MAX_WARNINGS="${SHM_STALL_MAX_WARNINGS:-6}"
if [ "${#PASSTHROUGH_ARGS[@]}" -gt 0 ]; then
  export EXTRA_ARGS="${PASSTHROUGH_ARGS[*]}"
else
  export EXTRA_ARGS='--async-engine --block-size 256 --no-enable-prefix-caching --compilation-config {"use_inductor_graph_partition":true,"compile_sizes":[1],"cudagraph_mode":"PIECEWISE"}'
fi

exec /home/steve/llm-optimizations/scripts/bench-vllm-minimax-autoround-xpu.sh
