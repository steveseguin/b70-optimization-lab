#!/usr/bin/env bash
set -euo pipefail

MODEL_DIR="${MODEL_DIR:?MODEL_DIR must be a HF repo id or local model path}"
GPU_INDEX="${GPU_INDEX:-0}"
PORT="${PORT:-19700}"
HOST="${HOST:-127.0.0.1}"
SERVED_MODEL_NAME="${SERVED_MODEL_NAME:-rapid-vllm-xpu-model}"
VLLM_VENV="${VLLM_VENV:-/home/steve/.venvs/vllm-xpu}"
HF_HOME="${HF_HOME:-/mnt/fast-ai/llm-cache/hf}"
TRANSFORMERS_CACHE="${TRANSFORMERS_CACHE:-$HF_HOME/transformers}"
MAX_MODEL_LEN="${MAX_MODEL_LEN:-4096}"
MAX_NUM_SEQS="${MAX_NUM_SEQS:-1}"
MAX_NUM_BATCHED_TOKENS="${MAX_NUM_BATCHED_TOKENS:-2048}"
GPU_MEMORY_UTILIZATION="${GPU_MEMORY_UTILIZATION:-0.95}"
TENSOR_PARALLEL_SIZE="${TENSOR_PARALLEL_SIZE:-1}"
TRUST_REMOTE_CODE="${TRUST_REMOTE_CODE:-1}"
ENABLE_PROMPT_TOKEN_DETAILS="${ENABLE_PROMPT_TOKEN_DETAILS:-1}"
ENABLE_PREFIX_CACHING="${ENABLE_PREFIX_CACHING:-0}"
DEFAULT_CHAT_TEMPLATE_KWARGS="${DEFAULT_CHAT_TEMPLATE_KWARGS:-}"
COMPILATION_CONFIG="${COMPILATION_CONFIG:-}"
SPECULATIVE_CONFIG="${SPECULATIVE_CONFIG:-}"
VLLM_EXTRA_ARGS="${VLLM_EXTRA_ARGS:-}"

if [[ -f /home/steve/.config/huggingface/token && -z "${HF_TOKEN:-}" ]]; then
  export HF_TOKEN
  HF_TOKEN="$(< /home/steve/.config/huggingface/token)"
fi

export HF_HOME TRANSFORMERS_CACHE
export HF_HUB_DISABLE_XET="${HF_HUB_DISABLE_XET:-1}"
export HF_HUB_ENABLE_HF_TRANSFER="${HF_HUB_ENABLE_HF_TRANSFER:-1}"
export ZE_AFFINITY_MASK="${ZE_AFFINITY_MASK:-$GPU_INDEX}"
export ONEAPI_DEVICE_SELECTOR="${ONEAPI_DEVICE_SELECTOR:-level_zero:0}"
export VLLM_NO_USAGE_STATS="${VLLM_NO_USAGE_STATS:-1}"
export LD_LIBRARY_PATH="$VLLM_VENV/lib:$VLLM_VENV/lib/python3.12/site-packages/torch/lib:${LD_LIBRARY_PATH:-}"

if [[ "${ENABLE_XPU_GRAPH:-0}" == "1" ]]; then
  export XPU_GRAPH="${XPU_GRAPH:-1}"
  export VLLM_XPU_ENABLE_XPU_GRAPH="${VLLM_XPU_ENABLE_XPU_GRAPH:-1}"
  export VLLM_XPU_FORCE_GRAPH_WITH_COMM="${VLLM_XPU_FORCE_GRAPH_WITH_COMM:-1}"
  export VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE="${VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE:-1}"
fi

echo "Rapid vLLM/XPU model"
echo "  model: $MODEL_DIR"
echo "  endpoint: http://$HOST:$PORT/v1"
echo "  gpu_index: $GPU_INDEX"
echo "  served_model_name: $SERVED_MODEL_NAME"
echo "  max_model_len: $MAX_MODEL_LEN"
echo "  max_num_batched_tokens: $MAX_NUM_BATCHED_TOKENS"
echo "  max_num_seqs: $MAX_NUM_SEQS"
echo "  tensor_parallel_size: $TENSOR_PARALLEL_SIZE"
echo "  compilation_config: ${COMPILATION_CONFIG:-<default>}"
echo "  speculative_config: ${SPECULATIVE_CONFIG:-<none>}"
echo "  enable_prefix_caching: $ENABLE_PREFIX_CACHING"
echo "  extra_args: ${VLLM_EXTRA_ARGS:-<none>}"
"$VLLM_VENV/bin/python" - <<'PY'
import sys
import torch
import vllm
print("  python:", sys.executable)
print("  torch:", torch.__version__)
print("  vllm:", getattr(vllm, "__version__", "unknown"), vllm.__file__)
PY

args=(
  serve "$MODEL_DIR"
  --host "$HOST"
  --port "$PORT"
  --served-model-name "$SERVED_MODEL_NAME"
  --tensor-parallel-size "$TENSOR_PARALLEL_SIZE"
  --max-model-len "$MAX_MODEL_LEN"
  --max-num-seqs "$MAX_NUM_SEQS"
  --max-num-batched-tokens "$MAX_NUM_BATCHED_TOKENS"
  --gpu-memory-utilization "$GPU_MEMORY_UTILIZATION"
)

if [[ "$TRUST_REMOTE_CODE" != "0" ]]; then
  args+=(--trust-remote-code)
fi
if [[ "$ENABLE_PROMPT_TOKEN_DETAILS" != "0" ]]; then
  args+=(--enable-prompt-tokens-details)
fi
if [[ "$ENABLE_PREFIX_CACHING" == "0" ]]; then
  args+=(--no-enable-prefix-caching)
else
  args+=(--enable-prefix-caching)
fi
if [[ -n "$DEFAULT_CHAT_TEMPLATE_KWARGS" ]]; then
  args+=(--default-chat-template-kwargs "$DEFAULT_CHAT_TEMPLATE_KWARGS")
fi
if [[ -n "$COMPILATION_CONFIG" ]]; then
  args+=(--compilation-config "$COMPILATION_CONFIG")
fi
if [[ -n "$SPECULATIVE_CONFIG" ]]; then
  args+=(--speculative-config "$SPECULATIVE_CONFIG")
fi
if [[ -n "$VLLM_EXTRA_ARGS" ]]; then
  read -r -a extra_args <<< "$VLLM_EXTRA_ARGS"
  args+=("${extra_args[@]}")
fi
unset VLLM_EXTRA_ARGS

exec "$VLLM_VENV/bin/vllm" "${args[@]}"
