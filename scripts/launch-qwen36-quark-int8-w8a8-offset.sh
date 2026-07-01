#!/usr/bin/env bash
set -euo pipefail

# Narrow W8A8 offset diagnostic launcher.
#
# This preserves the accepted TP4 graph/runtime flags, but overlays a stable
# vllm-xpu-kernels build that exports
# cutlass_grouped_gemm_w8a8_int8_offsets_interface and enables only the
# VLLM_XPU_W8A8_USE_OFFSETS path. It must not use the sidecar-probe build.

MODEL_PATH="${MODEL_PATH:-/mnt/fast-ai/llm-cache/hf/models--nameistoken--Qwen3.6-35B-A3B-Quark-W8A8-INT8/snapshots/cced56592e8c8935f8220836b4baa04dfd389118}"
SERVED_MODEL_NAME="${SERVED_MODEL_NAME:-qwen36-35b-a3b-fp8}"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-18080}"
TAG="${TAG:-w8a8-offset-20260612cw}"
LOG_PATH="${LOG_PATH:-/tmp/qwen36-quark-int8-tp4-${TAG}.log}"

MAX_MODEL_LEN="${MAX_MODEL_LEN:-32768}"
MAX_NUM_BATCHED_TOKENS="${MAX_NUM_BATCHED_TOKENS:-8192}"
MAX_NUM_SEQS="${MAX_NUM_SEQS:-48}"
GPU_MEMORY_UTILIZATION="${GPU_MEMORY_UTILIZATION:-0.95}"
if [[ -z "${COMPILATION_CONFIG:-}" ]]; then
  COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE"}'
fi

VLLM_SRC="${VLLM_SRC:-/home/steve/src/vllm}"
KERNELS_SRC="${KERNELS_SRC:-/home/steve/src/vllm-xpu-kernels}"
OFFSET_BUILD_LIB="${OFFSET_BUILD_LIB:-$KERNELS_SRC/build/lib.linux-x86_64-cpython-312/vllm_xpu_kernels}"
OVERLAY_DIR="${OVERLAY_DIR:-/tmp/qwen36-vllm-xpu-w8a8-offset-overlay-${TAG}}"

if [[ ! -f "$OFFSET_BUILD_LIB/_xpu_C.abi3.so" ]]; then
  echo "Missing offset-capable module: $OFFSET_BUILD_LIB/_xpu_C.abi3.so" >&2
  exit 1
fi
if [[ ! -f "$OFFSET_BUILD_LIB/libgrouped_gemm_xe_2.so" ]]; then
  echo "Missing grouped GEMM dependency: $OFFSET_BUILD_LIB/libgrouped_gemm_xe_2.so" >&2
  exit 1
fi
if [[ ! -f "$OFFSET_BUILD_LIB/libgrouped_gemm_xe_default.so" ]]; then
  echo "Missing grouped GEMM dependency: $OFFSET_BUILD_LIB/libgrouped_gemm_xe_default.so" >&2
  exit 1
fi

rm -rf "$OVERLAY_DIR"
mkdir -p "$OVERLAY_DIR/vllm_xpu_kernels"
ln -sf "$OFFSET_BUILD_LIB/_xpu_C.abi3.so" \
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
export LD_LIBRARY_PATH="$OFFSET_BUILD_LIB:$KERNELS_SRC/vllm_xpu_kernels:/home/steve/.venvs/vllm-xpu/lib:/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"

export VLLM_USE_V1=1
export VLLM_TARGET_DEVICE=xpu
export VLLM_ALLOW_LONG_MAX_MODEL_LEN=1
export XPU_GRAPH="${XPU_GRAPH:-1}"
export VLLM_XPU_ENABLE_XPU_GRAPH="${VLLM_XPU_ENABLE_XPU_GRAPH:-1}"
export VLLM_XPU_FORCE_GRAPH_WITH_COMM="${VLLM_XPU_FORCE_GRAPH_WITH_COMM:-1}"
export VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE="${VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE:-1}"
export VLLM_XPU_USE_CUSTOM_OP_COLLECTIVES=1
export VLLM_XPU_COMPILE_ALLREDUCE_CUSTOM_OP=1
export VLLM_XPU_CUSTOM_ALLREDUCE_GRAPH_CLONE_INPUT=1
export VLLM_XPU_CUSTOM_ALLREDUCE_CLONE_INPUT=1
export VLLM_XPU_QUARK_W8A8_MOE=1
export VLLM_XPU_FORCE_QUARK_REPACK=0
export VLLM_XPU_GDN_REUSE_QKVZ_BA_QUANT=clone
export VLLM_XPU_W8A8_USE_OFFSETS=1

export ONEAPI_DEVICE_SELECTOR="${ONEAPI_DEVICE_SELECTOR:-level_zero:0,1,2,3}"
export ZE_AFFINITY_MASK="${ZE_AFFINITY_MASK:-0,1,2,3}"
export CCL_ATL_TRANSPORT=ofi
export CCL_TOPO_P2P_ACCESS=1
export FI_TCP_IFACE="${FI_TCP_IFACE:-eth1}"
export CCL_KVS_IFACE="${CCL_KVS_IFACE:-eth1}"

unset CCL_ZE_IPC_EXCHANGE
unset CCL_WORKER_COUNT
unset VLLM_XPU_GDN_SKIP_DECODE_CONV_TMP
unset VLLM_XPU_DEDUP_INT8_QUANT

if [[ "${VLLM_XPU_DECODE_TIMING_ALLOW:-0}" != "1" ]]; then
  unset VLLM_XPU_DECODE_TIMING
  unset VLLM_XPU_DECODE_TIMING_SYNC
  unset VLLM_XPU_DECODE_TIMING_RANK
  unset VLLM_XPU_DECODE_TIMING_SUMMARY
  unset VLLM_XPU_DECODE_TIMING_PRINT_EVERY
  unset VLLM_XPU_DECODE_TIMING_SKIP_FIRST
  unset VLLM_XPU_DECODE_TIMING_LABEL_REGEX
  unset VLLM_XPU_DECODE_TIMING_EXCLUDE_LABEL_REGEX
  unset VLLM_XPU_DECODE_TIMING_SYNC_LABEL_REGEX
  unset VLLM_XPU_DECODE_TIMING_SYNC_EXCLUDE_LABEL_REGEX
  unset VLLM_XPU_DECODE_TIMING_STEP_SUMMARY
  unset VLLM_XPU_DECODE_TIMING_STEP_EVERY
  unset VLLM_XPU_DECODE_TIMING_STEP_SKIP_FIRST
fi
if [[ "${VLLM_XPU_METADATA_COPY_ALLOW:-0}" != "1" ]]; then
  unset VLLM_XPU_BLOCK_TABLE_DIRTY_COMMIT
  unset VLLM_XPU_BLOCK_TABLE_DIRTY_COMMIT_LOG_EVERY
fi

source /home/steve/.venvs/vllm-xpu/bin/activate

EXTRA_ARGS=()
if [[ -n "${VLLM_EXTRA_ARGS:-}" ]]; then
  # shellcheck disable=SC2206
  EXTRA_ARGS=(${VLLM_EXTRA_ARGS})
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
  --max-model-len "$MAX_MODEL_LEN" \
  --max-num-batched-tokens "$MAX_NUM_BATCHED_TOKENS" \
  --max-num-seqs "$MAX_NUM_SEQS" \
  --gpu-memory-utilization "$GPU_MEMORY_UTILIZATION" \
  --kv-cache-dtype auto \
  --no-enable-prefix-caching \
  --language-model-only \
  --compilation-config "$COMPILATION_CONFIG" \
  --generation-config vllm \
  "${EXTRA_ARGS[@]}" \
  >"$LOG_PATH" 2>&1
