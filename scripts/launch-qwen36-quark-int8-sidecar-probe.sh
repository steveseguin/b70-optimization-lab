#!/usr/bin/env bash
set -euo pipefail

# Isolated descriptor-probe launcher for the guarded oneDNN MoE sidecar.
# This does not modify the normal vllm_xpu_kernels package. It creates a small
# overlay package containing only the rebuilt _xpu_C module, then lets Python
# load the remaining package files from the source checkout.

MODEL_PATH="${MODEL_PATH:-/mnt/fast-ai/llm-cache/hf/models--nameistoken--Qwen3.6-35B-A3B-Quark-W8A8-INT8/snapshots/cced56592e8c8935f8220836b4baa04dfd389118}"
SERVED_MODEL_NAME="${SERVED_MODEL_NAME:-qwen36-35b-a3b-fp8}"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-18081}"
TAG="${TAG:-sidecar-probe-20260612}"
LOG_PATH="${LOG_PATH:-/tmp/qwen36-quark-int8-tp4-${TAG}.log}"

VLLM_SRC="${VLLM_SRC:-/home/steve/src/vllm}"
KERNELS_SRC="${KERNELS_SRC:-/home/steve/src/vllm-xpu-kernels}"
SIDECAR_BUILD_DIR="${SIDECAR_BUILD_DIR:-$KERNELS_SRC/build/qwen36-sidecar-probe-sycl8-20260613}"
OVERLAY_DIR="${OVERLAY_DIR:-/tmp/qwen36-vllm-xpu-sidecar-overlay-${TAG}}"
ONEAPI_SETVARS="${ONEAPI_SETVARS:-}"

if [[ ! -f "$SIDECAR_BUILD_DIR/_xpu_C.abi3.so" ]]; then
  echo "Missing rebuilt sidecar module: $SIDECAR_BUILD_DIR/_xpu_C.abi3.so" >&2
  exit 1
fi

if [[ -n "$ONEAPI_SETVARS" && -f "$ONEAPI_SETVARS" ]]; then
  # shellcheck disable=SC1090
  set +u
  source "$ONEAPI_SETVARS" >/tmp/oneapi-setvars-qwen36-sidecar-probe.log 2>&1 || true
  set -u
fi

rm -rf "$OVERLAY_DIR"
mkdir -p "$OVERLAY_DIR/vllm_xpu_kernels"
ln -sf "$SIDECAR_BUILD_DIR/_xpu_C.abi3.so" \
  "$OVERLAY_DIR/vllm_xpu_kernels/_xpu_C.abi3.so"
cat >"$OVERLAY_DIR/vllm_xpu_kernels/__init__.py" <<PY
from pkgutil import extend_path
__path__ = extend_path(__path__, __name__)
__path__.append("$KERNELS_SRC/vllm_xpu_kernels")
PY

DEFAULT_CACHE_ROOT="/mnt/fast-ai/vllm-cache-exp/qwen36-35b-a3b-quark-int8-tp4-${TAG}"
export HF_HOME="${HF_HOME:-/mnt/fast-ai/llm-cache/hf}"
export HUGGINGFACE_HUB_CACHE="${HUGGINGFACE_HUB_CACHE:-/mnt/fast-ai/llm-cache/hf}"
export TORCHINDUCTOR_CACHE_DIR="${TORCHINDUCTOR_CACHE_DIR:-${DEFAULT_CACHE_ROOT}/torchinductor}"
export VLLM_CACHE_ROOT="${VLLM_CACHE_ROOT:-${DEFAULT_CACHE_ROOT}/vllm}"

export PYTHONPATH="$OVERLAY_DIR:$VLLM_SRC:$KERNELS_SRC${PYTHONPATH:+:$PYTHONPATH}"
export LD_LIBRARY_PATH="$SIDECAR_BUILD_DIR:$KERNELS_SRC/vllm_xpu_kernels:/home/steve/.venvs/vllm-xpu/lib:/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"

export VLLM_USE_V1=1
export VLLM_TARGET_DEVICE=xpu
export VLLM_ALLOW_LONG_MAX_MODEL_LEN=1
export XPU_GRAPH="${XPU_GRAPH:-0}"
export VLLM_XPU_ENABLE_XPU_GRAPH="${VLLM_XPU_ENABLE_XPU_GRAPH:-0}"
export VLLM_XPU_FORCE_GRAPH_WITH_COMM="${VLLM_XPU_FORCE_GRAPH_WITH_COMM:-0}"
export VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE="${VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE:-0}"
export VLLM_XPU_USE_CUSTOM_OP_COLLECTIVES=1
export VLLM_XPU_COMPILE_ALLREDUCE_CUSTOM_OP=1
export VLLM_XPU_CUSTOM_ALLREDUCE_GRAPH_CLONE_INPUT=1
export VLLM_XPU_CUSTOM_ALLREDUCE_CLONE_INPUT=1
export VLLM_XPU_QUARK_W8A8_MOE=1
export VLLM_XPU_FORCE_QUARK_REPACK=0
export VLLM_XPU_GDN_REUSE_QKVZ_BA_QUANT=clone

export VLLM_XPU_MOE_ONEDNN_SIDECAR_PROBE="${VLLM_XPU_MOE_ONEDNN_SIDECAR_PROBE:-1}"
export VLLM_XPU_MOE_ONEDNN_SIDECAR_DRY_DESCRIPTORS="${VLLM_XPU_MOE_ONEDNN_SIDECAR_DRY_DESCRIPTORS:-1}"
export VLLM_XPU_MOE_ONEDNN_SIDECAR_OFFSETS="${VLLM_XPU_MOE_ONEDNN_SIDECAR_OFFSETS:-1}"
export VLLM_XPU_MOE_ONEDNN_SIDECAR_MAX_CALLS="${VLLM_XPU_MOE_ONEDNN_SIDECAR_MAX_CALLS:-1}"
export VLLM_XPU_MOE_ONEDNN_SIDECAR_RANK="${VLLM_XPU_MOE_ONEDNN_SIDECAR_RANK:-0}"
export VLLM_XPU_MOE_ONEDNN_SIDECAR_LAYER_REGEX="${VLLM_XPU_MOE_ONEDNN_SIDECAR_LAYER_REGEX:-layers\\.9\\.}"
DEFAULT_SIDECAR_LOG="/tmp/qwen36-onednn-sidecar-probe-${TAG}-{pid}.jsonl"
export VLLM_XPU_MOE_ONEDNN_SIDECAR_LOG="${VLLM_XPU_MOE_ONEDNN_SIDECAR_LOG:-$DEFAULT_SIDECAR_LOG}"

export ONEAPI_DEVICE_SELECTOR=level_zero:0,1,2,3
export ZE_AFFINITY_MASK=0,1,2,3
export CCL_ATL_TRANSPORT=ofi
export CCL_TOPO_P2P_ACCESS=1
export FI_TCP_IFACE="${FI_TCP_IFACE:-eth1}"
export CCL_KVS_IFACE="${CCL_KVS_IFACE:-eth1}"

unset CCL_ZE_IPC_EXCHANGE
unset CCL_WORKER_COUNT
unset VLLM_XPU_GDN_SKIP_DECODE_CONV_TMP
unset VLLM_XPU_DEDUP_INT8_QUANT

source /home/steve/.venvs/vllm-xpu/bin/activate

EXTRA_ARGS=()
if [[ "${ENFORCE_EAGER:-1}" != "0" ]]; then
  EXTRA_ARGS+=("--enforce-eager")
fi
if [[ -n "${COMPILATION_CONFIG:-}" ]]; then
  EXTRA_ARGS+=("--compilation-config" "$COMPILATION_CONFIG")
fi
if [[ -n "${VLLM_EXTRA_ARGS:-}" ]]; then
  # shellcheck disable=SC2206
  EXTRA_ARGS+=(${VLLM_EXTRA_ARGS})
fi

exec /home/steve/.venvs/vllm-xpu/bin/vllm serve "$MODEL_PATH" \
  --host "$HOST" \
  --port "$PORT" \
  --trust-remote-code \
  --served-model-name "$SERVED_MODEL_NAME" \
  --dtype auto \
  --quantization quark \
  --tensor-parallel-size 4 \
  --pipeline-parallel-size 1 \
  --distributed-executor-backend mp \
  --max-model-len 32768 \
  --max-num-batched-tokens 8192 \
  --max-num-seqs 48 \
  --gpu-memory-utilization 0.95 \
  --kv-cache-dtype auto \
  --no-enable-prefix-caching \
  --language-model-only \
  --generation-config vllm \
  "${EXTRA_ARGS[@]}" \
  >"$LOG_PATH" 2>&1
