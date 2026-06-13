#!/usr/bin/env bash
set -euo pipefail

# Diagnostic launcher for the graph-replay MoE digest probe. The overlay keeps
# package import side effects light: __init__.py only extends the package path,
# while the digest _xpu_C extension is exposed as a normal module file and is
# loaded only if vLLM imports the XPU fused-MoE path.

MODEL_PATH="${MODEL_PATH:-/mnt/fast-ai/llm-cache/hf/models--nameistoken--Qwen3.6-35B-A3B-Quark-W8A8-INT8/snapshots/cced56592e8c8935f8220836b4baa04dfd389118}"
SERVED_MODEL_NAME="${SERVED_MODEL_NAME:-qwen36-35b-a3b-fp8}"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-18082}"
TAG="${TAG:-replay-digest-20260612di}"
LOG_PATH="${LOG_PATH:-/tmp/qwen36-quark-int8-tp4-${TAG}.log}"

VLLM_SRC="${VLLM_SRC:-/home/steve/src/vllm}"
KERNELS_SRC="${KERNELS_SRC:-/home/steve/src/vllm-xpu-kernels}"
DIGEST_SRC="${DIGEST_SRC:-/home/steve/src/vllm-xpu-kernels-digest-20260612dh}"
DIGEST_BUILD_DIR="${DIGEST_BUILD_DIR:-$DIGEST_SRC/build/qwen36-replay-digest-20260612dh}"
OVERLAY_DIR="${OVERLAY_DIR:-/tmp/qwen36-vllm-xpu-replay-digest-overlay-${TAG}}"
ONEAPI_COMPILER_VARS="${ONEAPI_COMPILER_VARS:-/opt/intel/oneapi/compiler/2026.0/env/vars.sh}"

if [[ ! -f "$DIGEST_BUILD_DIR/_xpu_C.abi3.so" ]]; then
  echo "Missing replay-digest module: $DIGEST_BUILD_DIR/_xpu_C.abi3.so" >&2
  exit 1
fi

if [[ -f "$ONEAPI_COMPILER_VARS" ]]; then
  # shellcheck disable=SC1090
  set +u
  source "$ONEAPI_COMPILER_VARS" >/tmp/oneapi-vars-qwen36-replay-digest.log 2>&1
  set -u
fi

ONEAPI_COMPILER_ROOT="$(cd "$(dirname "$ONEAPI_COMPILER_VARS")/.." 2>/dev/null && pwd || true)"
ONEAPI_COMPILER_LIB=""
if [[ -n "$ONEAPI_COMPILER_ROOT" && -d "$ONEAPI_COMPILER_ROOT/lib" ]]; then
  ONEAPI_COMPILER_LIB="$ONEAPI_COMPILER_ROOT/lib"
fi

rm -rf "$OVERLAY_DIR"
mkdir -p "$OVERLAY_DIR/vllm_xpu_kernels"
ln -sf "$DIGEST_SRC/vllm_xpu_kernels/fused_moe_interface.py" \
  "$OVERLAY_DIR/vllm_xpu_kernels/fused_moe_interface.py"
ln -sf "$DIGEST_BUILD_DIR/_xpu_C.abi3.so" \
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
export LD_LIBRARY_PATH="$DIGEST_BUILD_DIR:$KERNELS_SRC/vllm_xpu_kernels${ONEAPI_COMPILER_LIB:+:$ONEAPI_COMPILER_LIB}:/home/steve/.venvs/vllm-xpu/lib:/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"

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

export VLLM_XPU_MOE_REPLAY_DIGEST="${VLLM_XPU_MOE_REPLAY_DIGEST:-1}"
export VLLM_XPU_MOE_REPLAY_DIGEST_LAYER_REGEX="${VLLM_XPU_MOE_REPLAY_DIGEST_LAYER_REGEX:-}"
export VLLM_XPU_MOE_REPLAY_DIGEST_RANK="${VLLM_XPU_MOE_REPLAY_DIGEST_RANK:-0}"
export VLLM_XPU_MOE_REPLAY_DIGEST_MAX_RECORDS="${VLLM_XPU_MOE_REPLAY_DIGEST_MAX_RECORDS:-4096}"
export VLLM_XPU_MOE_REPLAY_DIGEST_MAX_TOPK="${VLLM_XPU_MOE_REPLAY_DIGEST_MAX_TOPK:-64}"
export VLLM_XPU_MOE_REPLAY_DIGEST_MAX_OUTPUT_BYTES="${VLLM_XPU_MOE_REPLAY_DIGEST_MAX_OUTPUT_BYTES:-512}"
DEFAULT_REPLAY_DIGEST_LOG="/tmp/qwen36-replay-digest-${TAG}-{rank}-{pid}.jsonl"
export VLLM_XPU_MOE_REPLAY_DIGEST_LOG="${VLLM_XPU_MOE_REPLAY_DIGEST_LOG:-$DEFAULT_REPLAY_DIGEST_LOG}"
export VLLM_XPU_MOE_REPLAY_DIGEST_LOG_INTERVAL_MS="${VLLM_XPU_MOE_REPLAY_DIGEST_LOG_INTERVAL_MS:-1000}"
export VLLM_XPU_MOE_REPLAY_DIGEST_LOG_MAX_ROWS="${VLLM_XPU_MOE_REPLAY_DIGEST_LOG_MAX_ROWS:-256}"

export ONEAPI_DEVICE_SELECTOR="${ONEAPI_DEVICE_SELECTOR:-level_zero:0,1,2,3}"
export ZE_AFFINITY_MASK="${ZE_AFFINITY_MASK:-0,1,2,3}"
export CCL_ATL_TRANSPORT=ofi
export CCL_TOPO_P2P_ACCESS=1
export FI_TCP_IFACE="${FI_TCP_IFACE:-eth1}"
export CCL_KVS_IFACE="${CCL_KVS_IFACE:-eth1}"

unset CCL_ZE_IPC_EXCHANGE
unset CCL_WORKER_COUNT
unset VLLM_XPU_W8A8_USE_OFFSETS
unset VLLM_XPU_MOE_ONEDNN_SIDECAR_PROBE
unset VLLM_XPU_MOE_ONEDNN_SIDECAR_OFFSETS
unset VLLM_XPU_MOE_ONEDNN_SIDECAR_DRY_DESCRIPTORS
unset VLLM_XPU_FUSED_MOE_FUSE_SILU_QUANT
unset VLLM_XPU_MOE_LIVE_ABI_FILE
unset VLLM_XPU_GDN_SKIP_DECODE_CONV_TMP
unset VLLM_XPU_DEDUP_INT8_QUANT

source /home/steve/.venvs/vllm-xpu/bin/activate

python3 - <<'PY'
import torch
import vllm_xpu_kernels.fused_moe_interface as fused_moe_interface
import vllm_xpu_kernels._xpu_C  # noqa: F401

if not hasattr(torch.ops._xpu_C, "qwen36_moe_replay_digest_probe"):
    raise SystemExit("replay digest op did not register")
print("replay_digest_import_ok", fused_moe_interface.__file__)
PY

if [[ "${DRY_RUN_IMPORT:-0}" == "1" ]]; then
  exit 0
fi

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
  --max-model-len 32768 \
  --max-num-batched-tokens 8192 \
  --max-num-seqs 48 \
  --gpu-memory-utilization 0.95 \
  --kv-cache-dtype auto \
  --no-enable-prefix-caching \
  --language-model-only \
  --compilation-config '{"cudagraph_mode":"PIECEWISE"}' \
  --generation-config vllm \
  "${EXTRA_ARGS[@]}" \
  >"$LOG_PATH" 2>&1
