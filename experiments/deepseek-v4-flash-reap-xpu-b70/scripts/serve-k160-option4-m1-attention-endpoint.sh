#!/usr/bin/env bash
set -euo pipefail

# Same-binary Option-4 endpoint A/B.  The new selector remains default-off.
root=/home/steve/llm-optimizations
vllm_tree=/home/steve/src/deepseek-v4-vllm-xpu-dspark
kernel_tree=/home/steve/src/deepseek-v4-xpu-kernels-mwidth-mhc

export RUN_DIR="${RUN_DIR:?set RUN_DIR to a unique artifact directory}"
mkdir -p "${RUN_DIR}"
export PYTHONPATH="${vllm_tree}:${kernel_tree}${PYTHONPATH:+:${PYTHONPATH}}"
export VLLM_TREE="${vllm_tree}"
export VLLM_COMMIT="${VLLM_COMMIT:-$(git -C "${vllm_tree}" rev-parse HEAD)}"
export KERNEL_TREE="${kernel_tree}"
export KERNEL_COMMIT=5a1e9fa4602f69302dc50ecf85b06b6f86762117
export PORT="${PORT:-18080}"
export RUN_PREFLIGHT="${RUN_PREFLIGHT:-0}" VERIFY_MANIFEST=0 ENFORCE_EAGER=0
export XPU_GRAPH=1 VLLM_XPU_ENABLE_XPU_GRAPH=1
export COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE"}'
export GPU_MEMORY_UTILIZATION=0.94 MAX_MODEL_LEN=2048 MAX_NUM_BATCHED_TOKENS=2048

export ONECCL_LIB_DIR=/mnt/fast-ai/runtime/oneccl-2021.17.2-b70-wideepoch-48fda4f/lib
export ONECCL_SOURCE_TREE=/home/steve/src/oneccl-2021.17.2-b70-sizegate
export ONECCL_FORCE_PRELOAD=1 B70_ONECCL_SYCL_ALLREDUCE_MAX_BYTES=131072

export VLLM_XPU_V4_SPLIT_FP8_ATTN=1
export VLLM_XPU_V4_SPLIT_FP8_BLOCK_H=4
export VLLM_XPU_V4_SPLIT_FP8_QK_NUM_WARPS=16
export VLLM_XPU_V4_SPLIT_FP8_PV_NUM_WARPS=4
export VLLM_XPU_V4_INPLACE_ALLREDUCE=1
export VLLM_XPU_V4_MHC_POST_PRE_M1_SINGLE_KERNEL=1
export VLLM_XPU_V4_SHARED_EXPERT_FUSED_ACT_QUANT=1
export VLLM_XPU_V4_SHARED_EXPERT_FUSED_ACT_QUANT_MAX_M=1
export VLLM_XPU_V4_M1_BIASED_TOPK=1
export VLLM_XPU_V4_M1_ROUTER_NORM=1
export VLLM_XPU_V4_M1_DIRECT_ROUTED_MOE=1
export VLLM_XPU_V4_FUSED_QNORM_ROPE_KV_INSERT=1
export VLLM_XPU_V4_FUSED_QNORM_ROPE_KV_INSERT_MAX_M=1
export VLLM_XPU_V4_BLOCK_FP8_W8A16=1
export VLLM_XPU_V4_BLOCK_FP8_W8A16_MAX_M=1
export VLLM_XPU_V4_BLOCK_FP8_W8A16_SHAPES=1536x4096,8192x1024,4096x2048,1024x4096
export VLLM_XPU_MXFP4_SMALL_M_N=64
export VLLM_XPU_NATIVE_MHC=1
export VLLM_XPU_V4_OPTION4_M1_ATTENTION_BOUNDARY="${VLLM_XPU_V4_OPTION4_M1_ATTENTION_BOUNDARY:-0}"

# Nonspeculative target; rejected/history lanes remain absent.
export VLLM_XPU_PERSISTENT_KSTEP_DECODE=0
export VLLM_XPU_NATIVE_K2_SINGLE_SUBMISSION=0
export DSPARK_SPEC_TOKENS=0 VLLM_XPU_DSPARK_SPEC_TOKENS=0
export VLLM_XPU_DSPARK_DISABLE_DRAFT_GRAPH=0
export VLLM_XPU_DSPARK_PIECEWISE_DRAFT_GRAPH=0
export VLLM_XPU_GREEDY_SHARDED_TARGET_ARGMAX=0
export VLLM_EXTRA_ARGS='--enable-prompt-tokens-details'

printf 'option4_m1_attention_boundary=%s\nvllm_commit=%s\n' \
  "${VLLM_XPU_V4_OPTION4_M1_ATTENTION_BOUNDARY}" "${VLLM_COMMIT}" \
  >"${RUN_DIR}/option4-endpoint-identity.txt"

exec "${root}/experiments/deepseek-v4-flash-reap-xpu-b70/scripts/serve-k160-tp4-smoke.sh"
