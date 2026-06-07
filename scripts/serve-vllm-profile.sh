#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
profile="${VLLM_SLOT_PROFILE:-/etc/b70-vllm-slot/current.env}"

if [[ ! -f "$profile" ]]; then
  echo "Missing vLLM model-slot profile: $profile" >&2
  echo "Install/switch with: $repo_dir/scripts/switch-vllm-model-slot.sh switch minimax-m27-c1" >&2
  exit 1
fi

# Profiles are trusted local shell fragments so they can carry model-specific
# arrays such as VLLM_EXTRA_ARGS=(--limit-mm-per-prompt '{"image":4}').
source "$profile"

pause_file="${VLLM_SLOT_PAUSE_FILE:-/home/steve/llm-optimizations/.pause-vllm-model-slot}"
if [[ -f "$pause_file" ]]; then
  echo "vLLM model slot paused by $pause_file"
  exit 0
fi

VENV="${VENV:-/home/steve/.venvs/vllm-xpu}"
MODEL_DIR="${MODEL_DIR:-${MODEL:-}}"
if [[ -z "$MODEL_DIR" ]]; then
  echo "MODEL_DIR is not set by profile: $profile" >&2
  exit 1
fi
if [[ "$MODEL_DIR" = /* && ! -d "$MODEL_DIR" ]]; then
  cat >&2 <<EOF
Model directory is missing:
  $MODEL_DIR

Profile:
  $profile

If this profile is meant to use a Hugging Face ID directly, set MODEL_DIR to
that ID instead of an absolute path, or download the model to this path first.
EOF
  exit 1
fi
if [[ ! -x "$VENV/bin/vllm" ]]; then
  echo "vLLM executable is missing: $VENV/bin/vllm" >&2
  exit 1
fi

if [[ "${B70_SOURCE_ONEAPI:-0}" == "1" && -f /opt/intel/oneapi/compiler/2025.3/env/vars.sh ]]; then
  # shellcheck disable=SC1091
  source /opt/intel/oneapi/compiler/2025.3/env/vars.sh >/dev/null 2>&1 || true
fi

profile_env_exports=(
  HF_HOME
  TRANSFORMERS_CACHE
  VLLM_CACHE_ROOT
  ONEAPI_DEVICE_SELECTOR
  ZE_AFFINITY_MASK
  CCL_ATL_TRANSPORT
  CCL_TOPO_P2P_ACCESS
  CCL_TOPO_FABRIC_VERTEX_CONNECTION_CHECK
  VLLM_XPU_FP8_LINEAR_BF16_FALLBACK
  VLLM_XPU_BLOCK_FP8_REQUANT
)
for env_name in "${profile_env_exports[@]}"; do
  if [[ -v "$env_name" ]]; then
    export "$env_name"
  fi
done

# shellcheck disable=SC1091
source "$VENV/bin/activate"

if [[ -z "${B70_CCL_IFACE:-}" ]]; then
  B70_CCL_IFACE="$(ip route get 1.1.1.1 2>/dev/null | awk '{for (i=1; i<=NF; i++) if ($i=="dev") {print $(i+1); exit}}' || true)"
fi
if [[ -n "${B70_CCL_IFACE:-}" ]]; then
  export FI_TCP_IFACE="${FI_TCP_IFACE:-$B70_CCL_IFACE}"
  export CCL_KVS_IFACE="${CCL_KVS_IFACE:-$B70_CCL_IFACE}"
fi

export HF_HUB_DISABLE_XET="${HF_HUB_DISABLE_XET:-1}"
export VLLM_NO_USAGE_STATS="${VLLM_NO_USAGE_STATS:-1}"
export LD_LIBRARY_PATH="$VENV/lib:$VENV/lib/python3.12/site-packages/torch/lib:${LD_LIBRARY_PATH:-}"

args=(
  serve "$MODEL_DIR"
  --host "${VLLM_HOST:-127.0.0.1}"
  --port "${VLLM_PORT:-18080}"
)

if [[ "${VLLM_TRUST_REMOTE_CODE:-1}" == "1" ]]; then
  args+=(--trust-remote-code)
fi
if [[ -n "${VLLM_SERVED_MODEL_NAME:-}" ]]; then
  args+=(--served-model-name "$VLLM_SERVED_MODEL_NAME")
fi
if [[ -n "${VLLM_DTYPE:-}" ]]; then
  args+=(--dtype "$VLLM_DTYPE")
fi
if [[ -n "${VLLM_QUANTIZATION:-}" && "${VLLM_QUANTIZATION:-}" != "none" && "${VLLM_QUANTIZATION:-}" != "auto" ]]; then
  args+=(--quantization "$VLLM_QUANTIZATION")
fi
if [[ -n "${VLLM_TENSOR_PARALLEL_SIZE:-}" ]]; then
  args+=(--tensor-parallel-size "$VLLM_TENSOR_PARALLEL_SIZE")
fi
if [[ -n "${VLLM_PIPELINE_PARALLEL_SIZE:-}" ]]; then
  args+=(--pipeline-parallel-size "$VLLM_PIPELINE_PARALLEL_SIZE")
fi
if [[ -n "${VLLM_DISTRIBUTED_EXECUTOR_BACKEND:-}" ]]; then
  args+=(--distributed-executor-backend "$VLLM_DISTRIBUTED_EXECUTOR_BACKEND")
fi
if [[ -n "${VLLM_MAX_MODEL_LEN:-}" ]]; then
  args+=(--max-model-len "$VLLM_MAX_MODEL_LEN")
fi
if [[ -n "${VLLM_MAX_NUM_BATCHED_TOKENS:-}" ]]; then
  args+=(--max-num-batched-tokens "$VLLM_MAX_NUM_BATCHED_TOKENS")
fi
if [[ -n "${VLLM_MAX_NUM_SEQS:-}" ]]; then
  args+=(--max-num-seqs "$VLLM_MAX_NUM_SEQS")
fi
if [[ -n "${VLLM_GPU_MEMORY_UTILIZATION:-}" ]]; then
  args+=(--gpu-memory-utilization "$VLLM_GPU_MEMORY_UTILIZATION")
fi
if [[ -n "${VLLM_BLOCK_SIZE:-}" ]]; then
  args+=(--block-size "$VLLM_BLOCK_SIZE")
fi
if [[ -n "${VLLM_KV_CACHE_DTYPE:-}" ]]; then
  args+=(--kv-cache-dtype "$VLLM_KV_CACHE_DTYPE")
fi
if [[ -n "${VLLM_KV_OFFLOADING_SIZE:-}" ]]; then
  args+=(--kv-offloading-size "$VLLM_KV_OFFLOADING_SIZE")
fi
if [[ "${VLLM_NO_SCHEDULER_RESERVE_FULL_ISL:-0}" == "1" ]]; then
  args+=(--no-scheduler-reserve-full-isl)
fi
case "${VLLM_ENABLE_PREFIX_CACHING:-}" in
  0|false|False|no|No)
    args+=(--no-enable-prefix-caching)
    ;;
  1|true|True|yes|Yes)
    args+=(--enable-prefix-caching)
    ;;
esac
if [[ "${VLLM_LANGUAGE_MODEL_ONLY:-0}" == "1" ]]; then
  args+=(--language-model-only)
fi
if [[ -n "${VLLM_COMPILATION_CONFIG:-}" ]]; then
  args+=(--compilation-config "$VLLM_COMPILATION_CONFIG")
fi
if declare -p VLLM_EXTRA_ARGS >/dev/null 2>&1; then
  # shellcheck disable=SC2154
  args+=("${VLLM_EXTRA_ARGS[@]}")
fi

echo "Starting vLLM model slot: ${MODEL_SLOT_NAME:-unknown}"
echo "Model: $MODEL_DIR"
echo "Endpoint backend: http://${VLLM_HOST:-127.0.0.1}:${VLLM_PORT:-18080}"

exec "$VENV/bin/vllm" "${args[@]}"
