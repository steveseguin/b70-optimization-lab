#!/usr/bin/env bash
set -euo pipefail

root="/home/steve/llm-optimizations"
serve="${root}/experiments/deepseek-v4-flash-reap-xpu-b70/scripts/serve-k160-tp4-smoke.sh"
width="${1:?usage: serve-k160-mwidth-cycle-capture.sh 4|8}"
case "${width}" in
  4|8) ;;
  *) printf 'width must be 4 or 8\n' >&2; exit 2 ;;
esac
spec_tokens=$((width - 1))
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
run_dir="${RUN_DIR:-/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/m${width}-sequential-cycle-capture-${stamp}}"
capture_dir="${CAPTURE_DIR:-/mnt/fast-ai/deepseek-v4-corpora/mtp-reuse-m${width}-sequential-${stamp}}"
arm_file="${CAPTURE_ARM_FILE:-/tmp/deepseek-v4-m${width}-sequential-${stamp}.arm}"

test ! -e "${run_dir}"
test ! -e "${capture_dir}"
test ! -e "${arm_file}"

export RUN_DIR="${run_dir}"
export VLLM_TREE=/home/steve/src/deepseek-v4-vllm-mwidth-integration
export VLLM_COMMIT=57cfb6771fef60253c98426a690948adfc049f8e
export KERNEL_TREE=/home/steve/src/deepseek-v4-xpu-kernels-mwidth-mhc
export KERNEL_COMMIT=50646a2bfd3e451d77e150a9f950cc097b40bce9
export PYTHONPATH="${VLLM_TREE}:${KERNEL_TREE}:${PYTHONPATH:-}"

export ONECCL_INSTALL_DIR=/home/steve/.venvs/deepseek-v4-xpu
export ONECCL_LIB_DIR=/mnt/fast-ai/runtime/oneccl-2021.17.2-b70-wideepoch-48fda4f/lib
export ONECCL_SOURCE_TREE=/home/steve/src/oneccl-2021.17.2-b70-sizegate
export ONECCL_FORCE_PRELOAD=1
export B70_ONECCL_SYCL_ALLREDUCE_MAX_BYTES=131072

# Capture the generic M-width target as the oracle. The candidate fixed MHC
# kernel is replayed against this corpus later and must not define its own
# reference outputs.
export XPU_GRAPH=0
export VLLM_XPU_ENABLE_XPU_GRAPH=0
export COMPILATION_CONFIG='{"cudagraph_mode":"NONE"}'
export ENFORCE_EAGER=1

export VLLM_XPU_V4_SPLIT_FP8_ATTN=1
export VLLM_XPU_V4_INPLACE_ALLREDUCE=1
export VLLM_XPU_V4_INPLACE_ALLREDUCE_M2=1
export VLLM_XPU_V4_SEGMENTED_ALLREDUCE_MAX_M="${width}"
export VLLM_XPU_V4_MHC_POST_PRE_M1_SINGLE_KERNEL=1
export VLLM_XPU_V4_MHC_POST_PRE_M2_SINGLE_KERNEL=1
export VLLM_XPU_V4_MHC_POST_PRE_FIXED_WIDTH_MAX_M=0
export VLLM_XPU_V4_SHARED_EXPERT_FUSED_ACT_QUANT=1
export VLLM_XPU_V4_SHARED_EXPERT_FUSED_ACT_QUANT_MAX_M=2
export VLLM_XPU_V4_M2_ROUTED_CLAMP_SILU=1
export VLLM_XPU_MOE_OUTPUT_ALIAS=0
export VLLM_XPU_V4_M1_BIASED_TOPK=1
export VLLM_XPU_V4_M1_ROUTER_NORM=1
export VLLM_XPU_V4_M2_ROUTER_NORM=1
export VLLM_XPU_V4_M1_DIRECT_ROUTED_MOE=1
export VLLM_XPU_V4_M2_ROUTE_DIRECT_COMPACT=1
export VLLM_XPU_V4_FUSED_QNORM_ROPE_KV_INSERT=1
export VLLM_XPU_V4_FUSED_QNORM_ROPE_KV_INSERT_MAX_M=2
export VLLM_XPU_V4_COMPRESSOR_M2_ROW_EXACT=1
export VLLM_XPU_V4_COMPRESSOR_M2_BATCHED_EXACT=0
export VLLM_XPU_V4_COMPRESSOR_ROW_EXACT_MAX_M="${width}"
export VLLM_XPU_V4_BLOCK_FP8_W8A16=1
export VLLM_XPU_V4_BLOCK_FP8_W8A16_MAX_M=2
export VLLM_XPU_V4_BLOCK_FP8_W8A16_SHAPES=1536x4096,8192x1024,4096x2048,1024x4096
export VLLM_XPU_MXFP4_SMALL_M_N=64
export VLLM_XPU_V4_SPLIT_FP8_BLOCK_H=4
export VLLM_XPU_V4_SPLIT_FP8_QK_NUM_WARPS=16
export VLLM_XPU_V4_SPLIT_FP8_PV_NUM_WARPS=4
export VLLM_XPU_NATIVE_MHC=1

export VLLM_XPU_V4_CAPTURE_CYCLE_DIR="${capture_dir}"
export VLLM_XPU_V4_CAPTURE_CYCLE_ARM_FILE="${arm_file}"
export VLLM_XPU_V4_CAPTURE_CYCLE_WIDTH="${width}"

export MAX_MODEL_LEN=1024
export MAX_NUM_BATCHED_TOKENS=1024
export GPU_MEMORY_UTILIZATION=0.94
export VLLM_CACHE_ROOT=/mnt/fast-ai/vllm-cache-exp/deepseek-v4-k160-mtp1-direct-wideepoch-20260715/vllm
export TORCHINDUCTOR_CACHE_DIR=/mnt/fast-ai/vllm-cache-exp/deepseek-v4-k160-mtp1-direct-wideepoch-20260715/torchinductor
export VLLM_EXTRA_ARGS="--enable-prompt-tokens-details --spec-method mtp --spec-tokens ${spec_tokens}"

mkdir -p "${capture_dir}"
{
  printf 'classification=deepseek_v4_sequential_mwidth_geometry_capture\n'
  printf 'width=%s\n' "${width}"
  printf 'spec_tokens=%s\n' "${spec_tokens}"
  printf 'proposal_source=attached_k160_mtp_repeated_geometry_only\n'
  printf 'predictor_acceptance_evaluated=false\n'
  printf 'decode_tps=null\n'
  printf 'localmax_eligible=false\n'
  printf 'capture_dir=%s\n' "${capture_dir}"
  printf 'capture_arm_file=%s\n' "${arm_file}"
  printf 'capture_vllm_commit=%s\n' "${VLLM_COMMIT}"
  printf 'kernel_commit=%s\n' "${KERNEL_COMMIT}"
} >"${capture_dir}/capture-identity.txt"

printf 'run_dir=%s\n' "${run_dir}"
printf 'capture_dir=%s\n' "${capture_dir}"
printf 'capture_arm_file=%s\n' "${arm_file}"
exec "${serve}"
