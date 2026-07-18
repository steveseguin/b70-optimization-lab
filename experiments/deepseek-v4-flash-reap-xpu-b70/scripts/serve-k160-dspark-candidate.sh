#!/usr/bin/env bash
set -euo pipefail

root="/home/steve/llm-optimizations"
serve="${root}/experiments/deepseek-v4-flash-reap-xpu-b70/scripts/serve-k160-tp4-smoke.sh"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
run_dir="${RUN_DIR:-/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/dspark7-xpu-candidate-${stamp}}"
draft_pack="${DSPARK_DRAFT_PACK:-/mnt/fast-ai/llm-models/deepseek-v4-flash-xpu/dspark-draft-pack-aa22cb0}"
graph_mode="${DSPARK_GRAPH_MODE:-eager}"
draft_graph_mode="${DSPARK_DRAFT_GRAPH_MODE:-eager}"

test ! -e "${run_dir}"
test -f "${draft_pack}/draft-pack-manifest.json"
case "${graph_mode}" in
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
  *) printf 'DSPARK_GRAPH_MODE must be eager or piecewise\n' >&2; exit 2 ;;
esac

export RUN_DIR="${run_dir}"
export VLLM_TREE="${VLLM_TREE:-/home/steve/src/deepseek-v4-vllm-xpu-dspark}"
export VLLM_COMMIT="${VLLM_COMMIT:-1f6d6be49c57a2d5b71c6ea4926d4b01ca612254}"
export KERNEL_TREE="${KERNEL_TREE:-/home/steve/src/deepseek-v4-xpu-kernels-mwidth-mhc}"
export KERNEL_COMMIT="${KERNEL_COMMIT:-0b99fc5360141d4dd6174fb15f30ec80c74c4d47}"
export PYTHONPATH="${VLLM_TREE}:${KERNEL_TREE}:${PYTHONPATH:-}"

export ONECCL_INSTALL_DIR=/home/steve/.venvs/deepseek-v4-xpu
export ONECCL_LIB_DIR=/mnt/fast-ai/runtime/oneccl-2021.17.2-b70-wideepoch-48fda4f/lib
export ONECCL_SOURCE_TREE=/home/steve/src/oneccl-2021.17.2-b70-sizegate
export ONECCL_FORCE_PRELOAD=1
export B70_ONECCL_SYCL_ALLREDUCE_MAX_BYTES=131072

export VLLM_XPU_V4_SPLIT_FP8_ATTN=1
export VLLM_XPU_V4_INPLACE_ALLREDUCE=1
export VLLM_XPU_V4_INPLACE_ALLREDUCE_M2=1
export VLLM_XPU_V4_SEGMENTED_ALLREDUCE_MAX_M=8
export VLLM_XPU_V4_MHC_POST_PRE_M1_SINGLE_KERNEL=1
export VLLM_XPU_V4_MHC_POST_PRE_M2_SINGLE_KERNEL=1
export VLLM_XPU_V4_MHC_POST_PRE_FIXED_WIDTH_MAX_M=8
export VLLM_XPU_V4_SHARED_EXPERT_FUSED_ACT_QUANT=1
export VLLM_XPU_V4_SHARED_EXPERT_FUSED_ACT_QUANT_MAX_M=2
export VLLM_XPU_V4_M2_ROUTED_CLAMP_SILU=1
export VLLM_XPU_MOE_OUTPUT_ALIAS=0
export VLLM_XPU_V4_M1_BIASED_TOPK=1
export VLLM_XPU_V4_M1_ROUTER_NORM=1
export VLLM_XPU_V4_M2_ROUTER_NORM=1
export VLLM_XPU_V4_M1_DIRECT_ROUTED_MOE=1
export VLLM_XPU_V4_M2_ROUTE_DIRECT_COMPACT=1
export VLLM_XPU_V4_DIRECT_ROUTED_MOE_ALLOW_256_EXPERT_FALLBACK=1
export VLLM_XPU_V4_FUSED_QNORM_ROPE_KV_INSERT=1
export VLLM_XPU_V4_FUSED_QNORM_ROPE_KV_INSERT_MAX_M=2
export VLLM_XPU_V4_COMPRESSOR_M2_ROW_EXACT=1
export VLLM_XPU_V4_COMPRESSOR_M2_BATCHED_EXACT=1
export VLLM_XPU_V4_COMPRESSOR_ROW_EXACT_MAX_M=8
export VLLM_XPU_V4_COMPRESSOR_BATCHED_EXACT_MAX_M="${VLLM_XPU_V4_COMPRESSOR_BATCHED_EXACT_MAX_M:-2}"
export VLLM_XPU_V4_BLOCK_FP8_W8A16=1
export VLLM_XPU_V4_BLOCK_FP8_W8A16_MAX_M="${VLLM_XPU_V4_BLOCK_FP8_W8A16_MAX_M:-2}"
export VLLM_XPU_V4_BLOCK_FP8_W8A16_SHAPES=1536x4096,8192x1024,4096x2048,1024x4096
export VLLM_XPU_MXFP4_SMALL_M_N="${VLLM_XPU_MXFP4_SMALL_M_N:-64}"
export VLLM_XPU_V4_SPLIT_FP8_BLOCK_H=4
export VLLM_XPU_V4_SPLIT_FP8_QK_NUM_WARPS=16
export VLLM_XPU_V4_SPLIT_FP8_PV_NUM_WARPS=4
export VLLM_XPU_NATIVE_MHC=1
export VLLM_XPU_DSPARK_EXACT_QUERY_CAPTURE="${VLLM_XPU_DSPARK_EXACT_QUERY_CAPTURE:-0}"
export VLLM_XPU_DSPARK_PIECEWISE_SAMPLE_GRAPH="${VLLM_XPU_DSPARK_PIECEWISE_SAMPLE_GRAPH:-0}"
export VLLM_XPU_DSPARK_FUSED_CONTEXT_WKV="${VLLM_XPU_DSPARK_FUSED_CONTEXT_WKV:-0}"
export VLLM_XPU_DSPARK_REPLICATED_MARKOV="${VLLM_XPU_DSPARK_REPLICATED_MARKOV:-0}"
export VLLM_XPU_GREEDY_FUSED_REJECTION="${VLLM_XPU_GREEDY_FUSED_REJECTION:-0}"
export VLLM_XPU_DSPARK_FIXED_M7_TARGET_INPUTS="${VLLM_XPU_DSPARK_FIXED_M7_TARGET_INPUTS:-0}"
export VLLM_XPU_DSPARK_PERSISTENT_MARKOV="${VLLM_XPU_DSPARK_PERSISTENT_MARKOV:-0}"
export VLLM_XPU_DSPARK_REPLICATED_MARKOV_W1="${VLLM_XPU_DSPARK_REPLICATED_MARKOV_W1:-0}"
export VLLM_XPU_DSPARK_DIRECT_DRAFT_OUTPUT="${VLLM_XPU_DSPARK_DIRECT_DRAFT_OUTPUT:-0}"
export VLLM_XPU_DSPARK_GREEDY_COPY_ELISION="${VLLM_XPU_DSPARK_GREEDY_COPY_ELISION:-0}"
case "${draft_graph_mode}" in
  eager)
    export VLLM_XPU_DSPARK_DISABLE_DRAFT_GRAPH=1
    export VLLM_XPU_DSPARK_PIECEWISE_DRAFT_GRAPH=0
    ;;
  piecewise)
    export VLLM_XPU_DSPARK_DISABLE_DRAFT_GRAPH=0
    export VLLM_XPU_DSPARK_PIECEWISE_DRAFT_GRAPH=1
    ;;
  full)
    export VLLM_XPU_DSPARK_DISABLE_DRAFT_GRAPH=0
    export VLLM_XPU_DSPARK_PIECEWISE_DRAFT_GRAPH=0
    ;;
  *) printf 'DSPARK_DRAFT_GRAPH_MODE must be eager, piecewise, or full\n' >&2; exit 2 ;;
esac

export MAX_MODEL_LEN="${MAX_MODEL_LEN:-256}"
export MAX_NUM_BATCHED_TOKENS="${MAX_NUM_BATCHED_TOKENS:-256}"
export GPU_MEMORY_UTILIZATION="${GPU_MEMORY_UTILIZATION:-0.958}"
export DSPARK_KV_CACHE_MEMORY_BYTES="${DSPARK_KV_CACHE_MEMORY_BYTES:-125829120}"
export DSPARK_SPEC_TOKENS="${DSPARK_SPEC_TOKENS:-7}"
export VLLM_CACHE_ROOT=/mnt/fast-ai/vllm-cache-exp/deepseek-v4-k160-dspark/vllm
export TORCHINDUCTOR_CACHE_DIR=/mnt/fast-ai/vllm-cache-exp/deepseek-v4-k160-dspark/torchinductor
if [[ "${DSPARK_DISABLE_SPECULATION:-0}" == "1" ]]; then
  export VLLM_EXTRA_ARGS="--enable-prompt-tokens-details --kv-cache-memory ${DSPARK_KV_CACHE_MEMORY_BYTES}"
else
  export VLLM_EXTRA_ARGS="--enable-prompt-tokens-details --kv-cache-memory ${DSPARK_KV_CACHE_MEMORY_BYTES} --spec-method dspark --spec-model ${draft_pack} --spec-tokens ${DSPARK_SPEC_TOKENS}"
fi
export VLLM_EXTRA_ARGS="${VLLM_EXTRA_ARGS} ${DSPARK_ADDITIONAL_VLLM_ARGS:-}"

printf 'run_dir=%s\n' "${run_dir}"
printf 'draft_pack=%s\n' "${draft_pack}"
printf 'graph_mode=%s\n' "${graph_mode}"
printf 'draft_graph_mode=%s\n' "${draft_graph_mode}"
printf 'promotion_requires_frozen_heldout_gate=true\n'
exec "${serve}"
