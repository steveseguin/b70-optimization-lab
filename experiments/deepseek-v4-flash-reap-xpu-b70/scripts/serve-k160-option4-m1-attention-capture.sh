#!/usr/bin/env bash
set -euo pipefail

# Bounded eager TP4 oracle capture. Every new selector is default-off and this
# wrapper fails closed unless a fresh append-only capture directory is supplied.
root=/home/steve/llm-optimizations
vllm_tree=/home/steve/src/deepseek-v4-vllm-xpu-dspark
kernel_tree=/home/steve/src/deepseek-v4-xpu-kernels-mwidth-mhc

export RUN_DIR="${RUN_DIR:?set RUN_DIR to a fresh artifact directory}"
export CAPTURE_DIR="${CAPTURE_DIR:?set CAPTURE_DIR to a fresh corpus directory}"
if [[ -e "${CAPTURE_DIR}" ]]; then
  printf 'refusing to overwrite capture directory: %s\n' "${CAPTURE_DIR}" >&2
  exit 2
fi
mkdir -p "${RUN_DIR}" "${CAPTURE_DIR}"

export PYTHONPATH="${vllm_tree}:${kernel_tree}${PYTHONPATH:+:${PYTHONPATH}}"
export VLLM_TREE="${vllm_tree}"
export VLLM_COMMIT="${VLLM_COMMIT:-$(git -C "${vllm_tree}" rev-parse HEAD)}"
export KERNEL_TREE="${kernel_tree}"
export KERNEL_COMMIT=5a1e9fa4602f69302dc50ecf85b06b6f86762117
export PORT="${PORT:-18080}"
export RUN_PREFLIGHT=1 VERIFY_MANIFEST=0 ENFORCE_EAGER=1
export XPU_GRAPH=0 VLLM_XPU_ENABLE_XPU_GRAPH=0
export MAX_MODEL_LEN=2048 MAX_NUM_BATCHED_TOKENS=2048
export GPU_MEMORY_UTILIZATION=0.94

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

# Explicitly keep later/rejected paths out of the oracle identity.
export VLLM_XPU_PERSISTENT_KSTEP_DECODE=0
export VLLM_XPU_NATIVE_K2_SINGLE_SUBMISSION=0
export DSPARK_SPEC_TOKENS=0 VLLM_XPU_DSPARK_SPEC_TOKENS=0
export VLLM_XPU_DSPARK_DISABLE_DRAFT_GRAPH=0
export VLLM_XPU_DSPARK_PIECEWISE_DRAFT_GRAPH=0
export VLLM_XPU_GREEDY_SHARDED_TARGET_ARGMAX=0

export VLLM_XPU_V4_DIVERGENCE_CAPTURE_DIR="${CAPTURE_DIR}/raw"
export VLLM_XPU_V4_DIVERGENCE_ARM_FILE="${CAPTURE_DIR}/capture.arm"
export VLLM_XPU_V4_DIVERGENCE_WARMUP_FILE="${CAPTURE_DIR}/warmup.arm"
export VLLM_XPU_V4_DIVERGENCE_POSITIONS=64,512
export VLLM_XPU_V4_DIVERGENCE_MODE=full
export VLLM_XPU_V4_DIVERGENCE_LAYERS=all
export VLLM_XPU_V4_DIVERGENCE_MAX_RECORDS=16384
export VLLM_XPU_V4_DIVERGENCE_STAGES='m1_boundary_ingress,mhc_attn_out,attn_static_binding,kv_storage_binding,compressor_state_before,compressor_state_after,compressed_kv_before,compressed_kv_after,swa_kv_before,swa_kv_after,attn_in,attn_input_gemm,attn_qkv_norm,attn_mqa_inputs,attn_sparse_bindings,compressed_kv_selected,swa_kv_selected,attn_qk_lse_pv,attn_mqa_out,attn_wo_a,attn_wo_b_local,attn_wo_b_reduced,attn_o_proj_out,attn_out'
export VLLM_EXTRA_ARGS='--enable-prompt-tokens-details'

exec "${root}/experiments/deepseek-v4-flash-reap-xpu-b70/scripts/serve-k160-tp4-smoke.sh"
