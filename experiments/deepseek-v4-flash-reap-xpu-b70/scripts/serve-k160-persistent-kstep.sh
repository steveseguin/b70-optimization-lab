#!/usr/bin/env bash
set -euo pipefail

root=/home/steve/llm-optimizations
kernel_tree=/home/steve/src/deepseek-v4-xpu-kernels-persistent-kstep
k="${PERSISTENT_KSTEP:?set PERSISTENT_KSTEP to 0,1,2,4,8,or 16}"
case "${k}" in
  0|1|2|4|8|16) ;;
  *) echo "invalid PERSISTENT_KSTEP=${k}" >&2; exit 2 ;;
esac
if [[ "${k}" == 0 ]]; then
  vllm_tree=/home/steve/src/deepseek-v4-vllm-nospec-oracle-20260719
else
  vllm_tree=/home/steve/src/deepseek-v4-vllm-persistent-kstep
fi

export PYTHONPATH="${vllm_tree}"
export VLLM_TREE="${vllm_tree}"
export VLLM_COMMIT="${VLLM_COMMIT:-$(git -C "${vllm_tree}" rev-parse HEAD)}"
export KERNEL_TREE="${kernel_tree}"
export KERNEL_COMMIT=6522849b02894273b1e779b3c115527b5cdf3756
export RUN_DIR="${RUN_DIR:?set RUN_DIR to a unique artifact directory}"
export PORT="${PORT:-18080}"
export RUN_PREFLIGHT=0 VERIFY_MANIFEST=0 ENFORCE_EAGER=0
export XPU_GRAPH=1 VLLM_XPU_ENABLE_XPU_GRAPH=1
export COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE"}'
export GPU_MEMORY_UTILIZATION=0.94 MAX_MODEL_LEN=1024
export MAX_NUM_BATCHED_TOKENS=1024

export ONECCL_LIB_DIR=/mnt/fast-ai/runtime/oneccl-2021.17.2-b70-wideepoch-48fda4f/lib
export ONECCL_SOURCE_TREE=/home/steve/src/oneccl-2021.17.2-b70-sizegate
export ONECCL_FORCE_PRELOAD=1 B70_ONECCL_SYCL_ALLREDUCE_MAX_BYTES=131072
unset CCL_ENABLE_SYCL_KERNELS

export VLLM_CACHE_ROOT=/mnt/fast-ai/vllm-cache-exp/deepseek-v4-k160-wideepoch-direct-20260715/vllm
export TORCHINDUCTOR_CACHE_DIR=/mnt/fast-ai/vllm-cache-exp/deepseek-v4-k160-direct-moe-router-norm-20260715/torchinductor

export VLLM_XPU_V4_SPLIT_FP8_ATTN=1
export VLLM_XPU_V4_SPLIT_FP8_BLOCK_H=4
export VLLM_XPU_V4_SPLIT_FP8_QK_NUM_WARPS=16
export VLLM_XPU_V4_SPLIT_FP8_PV_NUM_WARPS=4
export VLLM_XPU_V4_INPLACE_ALLREDUCE=1
export VLLM_XPU_V4_MHC_POST_PRE_M1_SINGLE_KERNEL=1
export VLLM_XPU_V4_SHARED_EXPERT_FUSED_ACT_QUANT=1
export VLLM_XPU_V4_M1_BIASED_TOPK=1
export VLLM_XPU_V4_M1_ROUTER_NORM=1
export VLLM_XPU_V4_M1_DIRECT_ROUTED_MOE=1
export VLLM_XPU_V4_FUSED_QNORM_ROPE_KV_INSERT=1
export VLLM_XPU_V4_BLOCK_FP8_W8A16=1
export VLLM_XPU_V4_BLOCK_FP8_W8A16_SHAPES=1536x4096,8192x1024,4096x2048,1024x4096
export VLLM_XPU_NATIVE_MHC=1
if [[ "${k}" == 0 ]]; then
  export VLLM_XPU_GREEDY_SHARDED_TARGET_ARGMAX=0
else
  export VLLM_XPU_GREEDY_SHARDED_TARGET_ARGMAX=1
fi
export VLLM_XPU_PERSISTENT_KSTEP_DECODE="${k}"

export VLLM_XPU_DSPARK_DISABLE_DRAFT_GRAPH=0
export VLLM_XPU_DSPARK_PIECEWISE_DRAFT_GRAPH=0
export VLLM_XPU_DSPARK_EXACT_QUERY_CAPTURE=0
export VLLM_XPU_DSPARK_PIECEWISE_SAMPLE_GRAPH=0
export VLLM_XPU_DSPARK_FUSED_CONTEXT_WKV=0
export VLLM_XPU_DSPARK_REPLICATED_MARKOV=0
export VLLM_XPU_GREEDY_FUSED_REJECTION=0
export VLLM_XPU_DSPARK_FIXED_M7_TARGET_INPUTS=0
export VLLM_XPU_DSPARK_FIXED_M8_TARGET_BUILDER=0
export VLLM_XPU_DSPARK_PERSISTENT_MARKOV=0
export VLLM_XPU_DSPARK_REPLICATED_MARKOV_W1=0
export VLLM_XPU_DSPARK_MARKOV_W2_DPAS=0
export VLLM_XPU_V4_MHC_POST_PRE_M8_DPAS=0
export VLLM_XPU_V4_MHC_POST_PRE_M8_PAIRTILE=0
export VLLM_XPU_DSPARK_SHARDED_MARKOV_ARGMAX=0
export VLLM_XPU_DSPARK_HOST_MARKOV_ARGMAX=0
export VLLM_XPU_DSPARK_IPC_EVENT_MARKOV_ARGMAX=0
export VLLM_XPU_DSPARK_IPC_EVENT_MARKOV7_BUNDLE=0
export VLLM_XPU_DSPARK_HOST_MARKOV_SHM=0
export VLLM_XPU_DSPARK_DIRECT_DRAFT_OUTPUT=0
export VLLM_XPU_DSPARK_GREEDY_COPY_ELISION=0
export DSPARK_SPEC_TOKENS=0
export VLLM_EXTRA_ARGS='--enable-prompt-tokens-details'

mkdir -p "${RUN_DIR}"
printf 'persistent_kstep=%s\nvllm_candidate_commit=%s\n' \
  "${k}" "${VLLM_COMMIT}" >"${RUN_DIR}/persistent-kstep.txt"
exec "${root}/experiments/deepseek-v4-flash-reap-xpu-b70/scripts/serve-k160-tp4-smoke.sh"
