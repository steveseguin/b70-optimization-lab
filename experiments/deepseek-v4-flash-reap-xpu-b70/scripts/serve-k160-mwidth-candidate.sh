#!/usr/bin/env bash
set -euo pipefail

root="/home/steve/llm-optimizations"
serve="${root}/experiments/deepseek-v4-flash-reap-xpu-b70/scripts/serve-k160-tp4-smoke.sh"
width="${1:?usage: serve-k160-mwidth-candidate.sh 4|8}"
case "${width}" in
  4|8) ;;
  *) printf 'width must be 4 or 8\n' >&2; exit 2 ;;
esac
spec_tokens=$((width - 1))
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
run_dir="${RUN_DIR:-/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/m${width}-fixed-mhc-candidate-${stamp}}"

test ! -e "${run_dir}"

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

export XPU_GRAPH=1
export VLLM_XPU_ENABLE_XPU_GRAPH=1
export VLLM_XPU_FORCE_GRAPH_WITH_COMM=0
export VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE=0
export COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE"}'
export ENFORCE_EAGER=0

export VLLM_XPU_V4_SPLIT_FP8_ATTN=1
export VLLM_XPU_V4_INPLACE_ALLREDUCE=1
export VLLM_XPU_V4_INPLACE_ALLREDUCE_M2=1
export VLLM_XPU_V4_SEGMENTED_ALLREDUCE_MAX_M="${width}"
export VLLM_XPU_V4_MHC_POST_PRE_M1_SINGLE_KERNEL=1
export VLLM_XPU_V4_MHC_POST_PRE_M2_SINGLE_KERNEL=1
export VLLM_XPU_V4_MHC_POST_PRE_FIXED_WIDTH_MAX_M="${width}"
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
export VLLM_XPU_V4_COMPRESSOR_M2_BATCHED_EXACT=1
export VLLM_XPU_V4_COMPRESSOR_ROW_EXACT_MAX_M="${width}"
export VLLM_XPU_V4_BLOCK_FP8_W8A16=1
export VLLM_XPU_V4_BLOCK_FP8_W8A16_MAX_M=2
export VLLM_XPU_V4_BLOCK_FP8_W8A16_SHAPES=1536x4096,8192x1024,4096x2048,1024x4096
export VLLM_XPU_MXFP4_SMALL_M_N=64
export VLLM_XPU_V4_SPLIT_FP8_BLOCK_H=4
export VLLM_XPU_V4_SPLIT_FP8_QK_NUM_WARPS=16
export VLLM_XPU_V4_SPLIT_FP8_PV_NUM_WARPS=4
export VLLM_XPU_NATIVE_MHC=1

export MAX_MODEL_LEN="${MAX_MODEL_LEN:-1024}"
export MAX_NUM_BATCHED_TOKENS="${MAX_NUM_BATCHED_TOKENS:-1024}"
export GPU_MEMORY_UTILIZATION="${GPU_MEMORY_UTILIZATION:-0.94}"
export VLLM_CACHE_ROOT=/mnt/fast-ai/vllm-cache-exp/deepseek-v4-k160-mwidth/vllm
export TORCHINDUCTOR_CACHE_DIR=/mnt/fast-ai/vllm-cache-exp/deepseek-v4-k160-mwidth/torchinductor
export VLLM_EXTRA_ARGS="--enable-prompt-tokens-details --spec-method mtp --spec-tokens ${spec_tokens}"

printf 'run_dir=%s\n' "${run_dir}"
printf 'verifier_width=%s\n' "${width}"
printf 'proposal_source=attached_k160_mtp_repeated_geometry\n'
printf 'promotion_requires_heldout_acceptance_and_exact_endpoint_gate=true\n'
exec "${serve}"
