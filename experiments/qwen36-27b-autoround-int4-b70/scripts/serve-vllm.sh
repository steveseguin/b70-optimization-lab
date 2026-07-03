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
export ONEAPI_DEVICE_SELECTOR="${ONEAPI_DEVICE_SELECTOR:-level_zero:$GPU_INDEX}"
export ZE_AFFINITY_MASK="${ZE_AFFINITY_MASK:-$GPU_INDEX}"
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
  --reasoning-parser qwen3
)

if [[ "$QWEN36_27B_DEFAULT_ENABLE_THINKING" == "0" ]]; then
  args+=(--default-chat-template-kwargs '{"enable_thinking": false}')
fi

if [[ "$QWEN36_27B_ENABLE_MTP" != "0" ]]; then
  args+=(--speculative-config "{\"method\":\"qwen3_next_mtp\",\"num_speculative_tokens\":$NUM_SPECULATIVE_TOKENS}")
fi

exec "$QWEN36_27B_AR_VENV/bin/vllm" "${args[@]}"
