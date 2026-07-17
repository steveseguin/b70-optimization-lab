#!/usr/bin/env bash
set -euo pipefail

root="/home/steve/llm-optimizations"
serve="${root}/experiments/deepseek-v4-flash-reap-xpu-b70/scripts/serve-k160-tp4-smoke.sh"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
run_dir="${RUN_DIR:-/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/mtp1-postportfolio-eager-profile-${stamp}}"
trace_dir="${run_dir}/trace"

test ! -e "${run_dir}"

export RUN_DIR="${run_dir}"
export VLLM_TREE=/home/steve/src/deepseek-v4-vllm-qnorm-routeportfolio
export VLLM_COMMIT=4a6fd874725312c53883b1d53970af1d0eccfc3f
export KERNEL_TREE=/home/steve/src/deepseek-v4-xpu-kernels-qnorm-routeportfolio
export KERNEL_COMMIT=18a44f440ca3ac2006d5ba19cd12ccca0a0c9982

export ONECCL_INSTALL_DIR=/home/steve/.venvs/deepseek-v4-xpu
export ONECCL_LIB_DIR=/mnt/fast-ai/runtime/oneccl-2021.17.2-b70-wideepoch-48fda4f/lib
export ONECCL_SOURCE_TREE=/home/steve/src/oneccl-2021.17.2-b70-sizegate
export ONECCL_FORCE_PRELOAD=1
export B70_ONECCL_SYCL_ALLREDUCE_MAX_BYTES=131072

export XPU_GRAPH=0
export VLLM_XPU_ENABLE_XPU_GRAPH=0
export COMPILATION_CONFIG='{"cudagraph_mode":"NONE"}'
export ENFORCE_EAGER=1

export VLLM_XPU_V4_SPLIT_FP8_ATTN=1
export VLLM_XPU_V4_INPLACE_ALLREDUCE=1
export VLLM_XPU_V4_MHC_POST_PRE_M1_SINGLE_KERNEL=1
export VLLM_XPU_V4_MHC_POST_PRE_M2_SINGLE_KERNEL=1
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
export VLLM_XPU_V4_BLOCK_FP8_W8A16=1
export VLLM_XPU_V4_BLOCK_FP8_W8A16_MAX_M=2
export VLLM_XPU_V4_BLOCK_FP8_W8A16_SHAPES=1536x4096,8192x1024,4096x2048,1024x4096
export VLLM_XPU_MXFP4_SMALL_M_N=64
export VLLM_XPU_V4_SPLIT_FP8_BLOCK_H=4
export VLLM_XPU_V4_SPLIT_FP8_QK_NUM_WARPS=16
export VLLM_XPU_V4_SPLIT_FP8_PV_NUM_WARPS=4
export VLLM_XPU_NATIVE_MHC=1

export MAX_MODEL_LEN=1024
export MAX_NUM_BATCHED_TOKENS=1024
export GPU_MEMORY_UTILIZATION=0.94
export VLLM_CACHE_ROOT=/mnt/fast-ai/vllm-cache-exp/deepseek-v4-k160-mtp1-direct-wideepoch-20260715/vllm
export TORCHINDUCTOR_CACHE_DIR=/mnt/fast-ai/vllm-cache-exp/deepseek-v4-k160-mtp1-direct-wideepoch-20260715/torchinductor
export VLLM_EXTRA_ARGS="--enable-prompt-tokens-details --spec-method mtp --spec-tokens 1 --profiler-config.profiler=torch --profiler-config.torch_profiler_dir=${trace_dir} --profiler-config.torch_profiler_with_stack=false --profiler-config.torch_profiler_record_shapes=true --profiler-config.torch_profiler_use_gzip=false"

printf 'run_dir=%s\n' "${run_dir}"
exec "${serve}"
