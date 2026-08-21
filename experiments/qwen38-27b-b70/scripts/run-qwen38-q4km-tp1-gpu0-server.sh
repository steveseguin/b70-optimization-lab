#!/usr/bin/env bash
set -euo pipefail

# Qwen3.8 27B Q4_K_M target-only TP1 lane server, four-B70 measuring host.
# One physical B70, no MTP/DFlash/draft/speculation, one slot, cache RAM zero.
# Identity differences from the promoted TP2 repro are deliberate and recorded
# in notes/2026-08-21-qwen38-q4km-tp1-lane-open.md: single device, this host,
# oneAPI 2026.0.0 build, and a 48/64 GiB host-memory scope.

QWEN38_SOURCE_DIR="${QWEN38_SOURCE_DIR:-/home/steve/src/llama.cpp-q38-tp1-lane}"
QWEN38_BUILD_DIR="${QWEN38_BUILD_DIR:-${QWEN38_SOURCE_DIR}/build-sycl-aot-bmg-g31}"
QWEN38_MODEL="${QWEN38_MODEL:-/mnt/usb-models/models/qwen3.8-27b-gguf/Qwen3.8-27B-Q4_K_M.gguf}"
QWEN38_HOST="${QWEN38_HOST:-127.0.0.1}"
QWEN38_PORT="${QWEN38_PORT:-18088}"
QWEN38_BATCH="${QWEN38_BATCH:-1024}"
QWEN38_UBATCH="${QWEN38_UBATCH:-256}"
QWEN38_GPU="${QWEN38_GPU:-0}"
QWEN38_CTX="${QWEN38_CTX:-8192}"

server="${QWEN38_BUILD_DIR}/bin/llama-server"
[[ -x "${server}" ]] || { printf 'Missing executable: %s\n' "${server}" >&2; exit 1; }
[[ -f "${QWEN38_MODEL}" ]] || { printf 'Missing model: %s\n' "${QWEN38_MODEL}" >&2; exit 1; }

expected_model_sha=31629f53165ab6a7dad8c9847dcfd1fdf55829dac1e6e748f4a68581b0033d34
actual_model_sha=$(sha256sum "${QWEN38_MODEL}" | awk '{print $1}')
[[ "${actual_model_sha}" == "${expected_model_sha}" ]] || {
    printf 'Model SHA-256 mismatch: expected %s, got %s\n' "${expected_model_sha}" "${actual_model_sha}" >&2
    exit 1
}

if pgrep -x llama-server >/dev/null; then
    printf 'Refusing to start: another llama-server is running.\n' >&2
    exit 1
fi

set +u
source /opt/intel/oneapi/setvars.sh --force >/dev/null 2>&1 || true
set -u

# Restrict enumeration to the one selected physical B70.
export ONEAPI_DEVICE_SELECTOR="level_zero:${QWEN38_GPU}"
export UR_L0_USE_IMMEDIATE_COMMANDLISTS=1
export UR_L0_V2_FORCE_DISABLE_COPY_OFFLOAD=1

# Accepted-lane runtime doors. TP2 communication doors are shape-gated and
# inert with a single device; the per-device fusion doors are live.
export GGML_SYCL_COMM_SINGLE_KERNEL=1
export GGML_META_FUSE_ALLREDUCE_ADD=1
export GGML_META_FUSE_ALLREDUCE_ADD_RMS_MUL=1
export GGML_SYCL_COMM_FUSED_Q8=1
export GGML_SYCL_FUSED_SWIGLU_Q8=1
export GGML_SYCL_FUSED_ATTN_Q8=1
export GGML_SYCL_FUSED_GDN_Q8=1
export GGML_SYCL_FUSED_MMVQ_PAIR=1
export GGML_SYCL_FUSED_MMVQ_SWIGLU_Q4K=1
export GGML_SYCL_FUSED_MMVQ_PAIR_GDN=1
export GGML_SYCL_FUSED_MMVQ_TRIPLE_ATTN=1
export GGML_SYCL_FUSED_MMVQ_TRIPLE_GDN=1
export GGML_SYCL_FUSED_MMVQ_QUAD_GDN=1
export GGML_SYCL_FUSED_GDN_BETA_SIGMOID=1
export GGML_SYCL_FUSED_CONCAT_STATE=1
export GGML_SYCL_FUSED_GDN_STATE_IO=1
export GGML_SYCL_FUSED_CONV_STATE_IO=1
export GGML_SYCL_COMM_DIRECT_Q8=2
export GGML_SYCL_FUSED_ROPE_SET_ROWS=1
export GGML_SYCL_COMM_REDUCE_VEC4=1
export GGML_SYCL_FUSED_QK_NORM_ROPE=1
export GGML_SYCL_FUSED_CONV_SILU_L2=1
export GGML_SYCL_FUSE_EXT=31
export GGML_SYCL_QDEDUP_STATS=1
export GGML_SYCL_MMQ_Q4K_REORDER=1
unset GGML_SYCL_FUSED_MMVQ_SWIGLU_Q4K_POISON
unset GGML_SYCL_FUSED_GDN_STATE_IO_POISON
unset GGML_SYCL_FUSED_CONV_STATE_IO_POISON
unset GGML_SYCL_GDN_RMS_TAIL_POISON
unset GGML_SYCL_FUSED_QK_NORM_ROPE_POISON
unset GGML_SYCL_FUSED_CONV_SILU_OUTPUT
unset GGML_SYCL_MMVQ_SG32_OUTPUT_HEAD

env | grep -E '^(GGML_|UR_L0_|ONEAPI_DEVICE_SELECTOR)' | LC_ALL=C sort > \
    "${QWEN38_SERVICE_ENV_OUT:-/tmp/qwen38-tp1-service-environment.txt}"

exec systemd-run --user --scope --quiet \
    --property=MemoryHigh=48G \
    --property=MemoryMax=64G \
    --property=MemorySwapMax=0 \
    "${server}" \
    --model "${QWEN38_MODEL}" \
    --device SYCL0 \
    --gpu-layers 99 \
    --flash-attn on \
    --batch-size "${QWEN38_BATCH}" \
    --ubatch-size "${QWEN38_UBATCH}" \
    --cache-type-k f16 \
    --cache-type-v f16 \
    --cache-ram 0 \
    --ctx-checkpoints 0 \
    --fit off \
    --reasoning off \
    --threads 8 \
    --poll 50 \
    --ctx-size "${QWEN38_CTX}" \
    --parallel 1 \
    --metrics \
    --host "${QWEN38_HOST}" \
    --port "${QWEN38_PORT}"
