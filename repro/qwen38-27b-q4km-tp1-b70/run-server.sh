#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
model_dir="${MODEL_DIR:-}"
build_dir="${BUILD_DIR:-}"
host="${HOST_ADDR:-127.0.0.1}"
port="${PORT:-18088}"
gpu="${GPU_INDEX:-0}"

[[ -n "${model_dir}" && -n "${build_dir}" ]] || {
    printf 'Set MODEL_DIR and BUILD_DIR. Run preflight.sh first.\n' >&2; exit 2;
}
server="${build_dir}/bin/llama-server"
model="${model_dir}/Qwen3.8-27B-Q4_K_M.gguf"
[[ -x "${server}" ]] || { printf 'Missing executable: %s\n' "${server}" >&2; exit 1; }
[[ "${gpu}" =~ ^[0-9]+$ ]] || { printf 'GPU_INDEX must be numeric.\n' >&2; exit 2; }
pgrep -x llama-server >/dev/null && {
    printf 'Refusing to start while another llama-server is running.\n' >&2; exit 1;
}
"${script_dir}/verify-model-direct.sh" "${model_dir}"

set +u
# shellcheck disable=SC1091
source /opt/intel/oneapi/setvars.sh --force >/dev/null 2>&1
set -u
export ONEAPI_DEVICE_SELECTOR="level_zero:${gpu}"
export UR_L0_USE_IMMEDIATE_COMMANDLISTS=1
export UR_L0_V2_FORCE_DISABLE_COPY_OFFLOAD=1
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
unset GGML_SYCL_FUSED_MMVQ_SWIGLU_Q4K_POISON GGML_SYCL_FUSED_GDN_STATE_IO_POISON
unset GGML_SYCL_FUSED_CONV_STATE_IO_POISON GGML_SYCL_GDN_RMS_TAIL_POISON
unset GGML_SYCL_FUSED_QK_NORM_ROPE_POISON GGML_SYCL_FUSED_CONV_SILU_OUTPUT
unset GGML_SYCL_MMVQ_SG32_OUTPUT_HEAD

exec systemd-run --user --scope --quiet \
  --property=MemoryHigh=48G --property=MemoryMax=64G --property=MemorySwapMax=0 \
  "${server}" --model "${model}" --device SYCL0 --gpu-layers 99 \
  --flash-attn on --batch-size 1024 --ubatch-size 256 \
  --cache-type-k f16 --cache-type-v f16 --cache-ram 0 --ctx-checkpoints 0 \
  --fit off --reasoning off --threads 8 --poll 50 --ctx-size 8192 \
  --parallel 1 --metrics --host "${host}" --port "${port}"
