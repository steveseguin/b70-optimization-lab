#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
# shellcheck source=../configs/qwen36-27b-autoround.env
source "$repo_dir/experiments/qwen36-27b-autoround-int4-b70/configs/qwen36-27b-autoround.env"

snapshot_dir="$HF_HOME/hub/models--Intel--Qwen3.6-27B-int4-AutoRound/snapshots/$QWEN36_27B_AR_REVISION"
MODEL_DIR="${MODEL_DIR:-}"
if [[ -z "$MODEL_DIR" ]]; then
  if [[ -d "$snapshot_dir" ]]; then
    MODEL_DIR="$snapshot_dir"
  else
    MODEL_DIR="$QWEN36_27B_AR_REPO"
  fi
fi

if [[ -f /home/steve/.config/huggingface/token && -z "${HF_TOKEN:-}" ]]; then
  export HF_TOKEN
  HF_TOKEN="$(< /home/steve/.config/huggingface/token)"
fi

export HF_HOME TRANSFORMERS_CACHE HF_HUB_DISABLE_XET HF_HUB_ENABLE_HF_TRANSFER
export ZE_AFFINITY_MASK="${ZE_AFFINITY_MASK:-$GPU_INDEX}"
# ZE_AFFINITY_MASK narrows visibility to one physical GPU. Inside that masked
# view, the visible XPU is logical index 0; using level_zero:$GPU_INDEX makes
# torch see zero devices for GPU_INDEX > 0.
export ONEAPI_DEVICE_SELECTOR="${ONEAPI_DEVICE_SELECTOR:-level_zero:0}"
export VLLM_NO_USAGE_STATS="${VLLM_NO_USAGE_STATS:-1}"
export LD_LIBRARY_PATH="$QWEN36_27B_AR_VENV/lib:$QWEN36_27B_AR_VENV/lib/python3.12/site-packages/torch/lib:${LD_LIBRARY_PATH:-}"

if [[ "$QWEN36_27B_ENABLE_XPU_GRAPH" == "1" ]]; then
  export XPU_GRAPH="${XPU_GRAPH:-1}"
  export VLLM_XPU_ENABLE_XPU_GRAPH="${VLLM_XPU_ENABLE_XPU_GRAPH:-1}"
  export VLLM_XPU_FORCE_GRAPH_WITH_COMM="${VLLM_XPU_FORCE_GRAPH_WITH_COMM:-1}"
  export VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE="${VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE:-1}"
fi

echo "Qwen3.6 27B AutoRound vLLM/XPU"
echo "  model: $MODEL_DIR"
echo "  endpoint: http://$HOST:$PORT/v1"
echo "  gpu: $GPU_INDEX"
echo "  max_model_len: $MAX_MODEL_LEN"
echo "  mtp: $QWEN36_27B_ENABLE_MTP tokens=$NUM_SPECULATIVE_TOKENS"
echo "  default_enable_thinking: $QWEN36_27B_DEFAULT_ENABLE_THINKING"
echo "  reasoning_parser: ${QWEN36_27B_REASONING_PARSER:-<none>}"
echo "  prompt_token_details: $QWEN36_27B_ENABLE_PROMPT_TOKEN_DETAILS"
echo "  compilation_config: ${COMPILATION_CONFIG:-<default>}"
echo "  promote_accepted_spec_state: ${VLLM_XPU_GDN_PROMOTE_ACCEPTED_SPEC_STATE:-0}"
echo "  nonspec_postprocess_accepted_state: ${VLLM_XPU_GDN_NONSPEC_POSTPROCESS_ACCEPTED_STATE:-1}"
echo "  extra_args: ${VLLM_EXTRA_ARGS:-<none>}"
"$QWEN36_27B_AR_VENV/bin/python" - <<'PY'
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
  --trust-remote-code
  --served-model-name "$SERVED_MODEL_NAME"
  --tensor-parallel-size 1
  --max-model-len "$MAX_MODEL_LEN"
  --max-num-seqs "$MAX_NUM_SEQS"
  --max-num-batched-tokens "$MAX_NUM_BATCHED_TOKENS"
  --gpu-memory-utilization "$GPU_MEMORY_UTILIZATION"
)

if [[ -n "${QWEN36_27B_REASONING_PARSER:-}" ]]; then
  args+=(--reasoning-parser "$QWEN36_27B_REASONING_PARSER")
fi

if [[ "$QWEN36_27B_DEFAULT_ENABLE_THINKING" == "0" ]]; then
  args+=(--default-chat-template-kwargs '{"enable_thinking": false}')
fi

if [[ "$QWEN36_27B_ENABLE_PROMPT_TOKEN_DETAILS" != "0" ]]; then
  args+=(--enable-prompt-tokens-details)
fi

if [[ -n "${COMPILATION_CONFIG:-}" ]]; then
  args+=(--compilation-config "$COMPILATION_CONFIG")
fi

if [[ "$QWEN36_27B_ENABLE_MTP" != "0" ]]; then
  args+=(--speculative-config "{\"method\":\"qwen3_next_mtp\",\"num_speculative_tokens\":$NUM_SPECULATIVE_TOKENS}")
fi

if [[ -n "${VLLM_EXTRA_ARGS:-}" ]]; then
  # Simple scalar flag passthrough for controlled sweeps. For arguments with
  # embedded whitespace, add them explicitly above as array elements.
  read -r -a extra_args <<< "$VLLM_EXTRA_ARGS"
  args+=("${extra_args[@]}")
fi
unset VLLM_EXTRA_ARGS

exec "$QWEN36_27B_AR_VENV/bin/vllm" "${args[@]}"
