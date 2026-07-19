#!/usr/bin/env bash
set -euo pipefail

root=/home/steve/llm-optimizations
serve="${root}/experiments/deepseek-v4-flash-reap-xpu-b70/scripts/serve-k160-tp4-smoke.sh"
base_vllm_commit=264c7f2f7df21ddeeab32ecca0353133344f1ac9
capture_vllm_commit=157eb4bc58e385eaaf4000cd71ce2c363decabf6
kernel_commit=31315673737d95da0f79179c8f755260ef02c1d6
oneccl_commit=48fda4f0e074db005596d6899d5227d3f0316c12
stamp="$(date -u +%Y%m%dT%H%M%SZ)"

export RUN_DIR="${RUN_DIR:-/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/k160-eagle-capture-${stamp}}"
export VLLM_TREE="${VLLM_TREE:-/home/steve/src/deepseek-v4-vllm-record-264c7f2f7}"
export VLLM_COMMIT="${VLLM_COMMIT:-${capture_vllm_commit}}"
export KERNEL_TREE="${KERNEL_TREE:-/home/steve/src/deepseek-v4-xpu-kernels-record-313156737}"
export KERNEL_COMMIT="${KERNEL_COMMIT:-${kernel_commit}}"
export PYTHONPATH="${VLLM_TREE}:${KERNEL_TREE}:${PYTHONPATH:-}"

export ONECCL_INSTALL_DIR=/home/steve/.venvs/deepseek-v4-xpu
export ONECCL_LIB_DIR=/mnt/fast-ai/runtime/oneccl-2021.17.2-b70-wideepoch-48fda4f/lib
export ONECCL_SOURCE_TREE=/home/steve/src/oneccl-2021.17.2-b70-sizegate
export ONECCL_FORCE_PRELOAD=1
export B70_ONECCL_SYCL_ALLREDUCE_MAX_BYTES=131072

case "${CAPTURE_GRAPH_MODE:-piecewise}" in
  eager)
    export XPU_GRAPH=0
    export VLLM_XPU_ENABLE_XPU_GRAPH=0
    export COMPILATION_CONFIG='{"cudagraph_mode":"NONE"}'
    export ENFORCE_EAGER=1
    ;;
  piecewise)
    export XPU_GRAPH=1
    export VLLM_XPU_ENABLE_XPU_GRAPH=1
    export VLLM_XPU_FORCE_GRAPH_WITH_COMM=0
    export VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE=0
    export COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE"}'
    export ENFORCE_EAGER=0
    ;;
  *)
    printf 'CAPTURE_GRAPH_MODE must be eager or piecewise\n' >&2
    exit 2
    ;;
esac
export MAX_MODEL_LEN="${MAX_MODEL_LEN:-2048}"
export MAX_NUM_BATCHED_TOKENS="${MAX_NUM_BATCHED_TOKENS:-2048}"
export GPU_MEMORY_UTILIZATION="${GPU_MEMORY_UTILIZATION:-0.95}"

export VLLM_XPU_V4_SPLIT_FP8_ATTN=1
export VLLM_XPU_V4_INPLACE_ALLREDUCE=1
export VLLM_XPU_V4_INPLACE_ALLREDUCE_M2=1
export VLLM_XPU_V4_SEGMENTED_ALLREDUCE_MAX_M=8
export VLLM_XPU_V4_MHC_POST_PRE_M1_SINGLE_KERNEL=1
export VLLM_XPU_V4_MHC_POST_PRE_M2_SINGLE_KERNEL=1
export VLLM_XPU_V4_MHC_POST_PRE_FIXED_WIDTH_MAX_M=8
export VLLM_XPU_NATIVE_MHC=1
export VLLM_XPU_V4_SHARED_EXPERT_FUSED_ACT_QUANT=1
export VLLM_XPU_V4_SHARED_EXPERT_FUSED_ACT_QUANT_MAX_M=2
export VLLM_XPU_V4_M2_ROUTED_CLAMP_SILU=1
export VLLM_XPU_V4_M1_BIASED_TOPK=1
export VLLM_XPU_V4_M1_ROUTER_NORM=1
export VLLM_XPU_V4_M2_ROUTER_NORM=1
export VLLM_XPU_V4_ROUTER_NORM_MAX_M=8
export VLLM_XPU_V4_M1_DIRECT_ROUTED_MOE=1
export VLLM_XPU_V4_M2_ROUTE_DIRECT_COMPACT=1
export VLLM_XPU_V4_DIRECT_ROUTED_MOE_ALLOW_256_EXPERT_FALLBACK=1
export VLLM_XPU_V4_FUSED_QNORM_ROPE_KV_INSERT=1
export VLLM_XPU_V4_FUSED_QNORM_ROPE_KV_INSERT_MAX_M=2
export VLLM_XPU_V4_COMPRESSOR_M2_ROW_EXACT=1
export VLLM_XPU_V4_COMPRESSOR_M2_BATCHED_EXACT=1
export VLLM_XPU_V4_COMPRESSOR_ROW_EXACT_MAX_M=8
export VLLM_XPU_V4_COMPRESSOR_BATCHED_EXACT_MAX_M=8
export VLLM_XPU_V4_BLOCK_FP8_W8A16=1
export VLLM_XPU_V4_BLOCK_FP8_W8A16_MAX_M=8
export VLLM_XPU_V4_BLOCK_FP8_W8A16_SHAPES=1536x4096,8192x1024,4096x2048,1024x4096
export VLLM_XPU_MXFP4_SMALL_M_N=128

export VLLM_XPU_EAGLE_TRAINING_CAPTURE_SHARD_ROWS="${VLLM_XPU_EAGLE_TRAINING_CAPTURE_SHARD_ROWS:-4096}"
if [[ -n "${VLLM_XPU_EAGLE_TRAINING_CAPTURE_DIR:-}" ]]; then
  export VLLM_XPU_EAGLE_TRAINING_CAPTURE_NAMESPACE="${VLLM_XPU_EAGLE_TRAINING_CAPTURE_NAMESPACE:-eaglesmoke}"
  export VLLM_XPU_EAGLE_TRAINING_CAPTURE_ARM_FILE="${VLLM_XPU_EAGLE_TRAINING_CAPTURE_ARM_FILE:-${RUN_DIR}/capture.arm}"
fi
export VLLM_EXTRA_ARGS="--enable-prompt-tokens-details ${VLLM_ADDITIONAL_ARGS:-}"

mkdir -p "${RUN_DIR}"
{
  printf 'capture_base_vllm_commit=%s\n' "${base_vllm_commit}"
  printf 'capture_patch_vllm_commit=%s\n' "${capture_vllm_commit}"
  printf 'xpu_kernel_commit=%s\n' "${kernel_commit}"
  printf 'oneccl_commit=%s\n' "${oneccl_commit}"
  printf 'feature_boundaries=4,22,43\n'
  printf 'feature_reduction=post_mhc_mean_stream\n'
  printf 'capture_dir=%s\n' "${VLLM_XPU_EAGLE_TRAINING_CAPTURE_DIR:-disabled}"
  printf 'capture_namespace=%s\n' "${VLLM_XPU_EAGLE_TRAINING_CAPTURE_NAMESPACE:-disabled}"
  printf 'capture_arm_file=%s\n' "${VLLM_XPU_EAGLE_TRAINING_CAPTURE_ARM_FILE:-disabled}"
  printf 'capture_all_ranks=%s\n' "${VLLM_XPU_EAGLE_TRAINING_CAPTURE_ALL_RANKS:-0}"
  printf 'one_active_generation=true\n'
  printf 'speculation=false\n'
} >"${RUN_DIR}/eagle-capture-identity.txt"

exec "${serve}"
