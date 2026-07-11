#!/usr/bin/env bash
set -euo pipefail

# Experimental Qwen27 target-verified DDTree endpoint. This keeps the DFlash
# draft PIECEWISE while capturing the complete 16-row target decode verifier.
# It is a research launcher, not a promoted production or benchmark recipe.

export MODEL_DIR="${MODEL_DIR:-/mnt/fast-ai/llm-cache/hf/hub/models--webhie--Qwen3.6-27B-int4-AutoRound/snapshots/f5750c90b3776db658594df5fe8051098226dd8e}"
export GPU_INDEX="${GPU_INDEX:-3}"
export ZE_AFFINITY_MASK="${ZE_AFFINITY_MASK:-$GPU_INDEX}"
export ONEAPI_DEVICE_SELECTOR="${ONEAPI_DEVICE_SELECTOR:-level_zero:0}"
export PORT="${PORT:-19439}"
export HOST="${HOST:-127.0.0.1}"
export SERVED_MODEL_NAME="${SERVED_MODEL_NAME:-qwen36-27b-int4-autoround}"

export MAX_MODEL_LEN="${MAX_MODEL_LEN:-2048}"
export MAX_NUM_BATCHED_TOKENS="${MAX_NUM_BATCHED_TOKENS:-1024}"
export MAX_NUM_SEQS="${MAX_NUM_SEQS:-1}"
export GPU_MEMORY_UTILIZATION="${GPU_MEMORY_UTILIZATION:-0.95}"
export QWEN36_27B_ENABLE_MTP="${QWEN36_27B_ENABLE_MTP:-0}"
export QWEN36_27B_ENABLE_XPU_GRAPH="${QWEN36_27B_ENABLE_XPU_GRAPH:-1}"
if [[ -z "${COMPILATION_CONFIG:-}" ]]; then
  export COMPILATION_CONFIG='{"cudagraph_mode":"FULL_DECODE_ONLY","max_cudagraph_capture_size":16}'
fi
if [[ -z "${QWEN36_27B_SPECULATIVE_CONFIG:-}" ]]; then
  export QWEN36_27B_SPECULATIVE_CONFIG='{"method":"dflash","model":"/mnt/fast-ai/llm-cache/hf/manual/z-lab--Qwen3.6-27B-DFlash","num_speculative_tokens":15}'
fi
export QWEN36_27B_DEFAULT_ENABLE_THINKING=0
export QWEN36_27B_ENABLE_PROMPT_TOKEN_DETAILS=1
export VLLM_EXTRA_ARGS="${VLLM_EXTRA_ARGS:---no-async-scheduling --mamba-cache-mode align --attention-backend TREE_ATTN --generation-config vllm}"

export VLLM_XPU_LM_HEAD_INT8="${VLLM_XPU_LM_HEAD_INT8:-1}"
export VLLM_XPU_LM_HEAD_INT8_SCALE_DTYPE="${VLLM_XPU_LM_HEAD_INT8_SCALE_DTYPE:-bf16}"
export VLLM_XPU_GDN_NATIVE_SPEC_PREFIX_BASE_STATE="${VLLM_XPU_GDN_NATIVE_SPEC_PREFIX_BASE_STATE:-1}"
export VLLM_XPU_GDN_NONSPEC_POSTPROCESS_ACCEPTED_STATE="${VLLM_XPU_GDN_NONSPEC_POSTPROCESS_ACCEPTED_STATE:-1}"
export VLLM_XPU_GDN_PROMOTE_ACCEPTED_SPEC_STATE="${VLLM_XPU_GDN_PROMOTE_ACCEPTED_SPEC_STATE:-0}"
export VLLM_XPU_QWEN3_DFLASH_LAYER_TYPES="${VLLM_XPU_QWEN3_DFLASH_LAYER_TYPES:-mixed}"
export VLLM_XPU_DFLASH_DDTREE_BUDGET="${VLLM_XPU_DFLASH_DDTREE_BUDGET:-15}"
export VLLM_XPU_DDTREE_NATIVE_KV_COPY="${VLLM_XPU_DDTREE_NATIVE_KV_COPY:-1}"
export VLLM_XPU_DDTREE_NATIVE_TREE_ATTN="${VLLM_XPU_DDTREE_NATIVE_TREE_ATTN:-1}"
export VLLM_XPU_TREE_ATTN_BOOL_SDPA="${VLLM_XPU_TREE_ATTN_BOOL_SDPA:-1}"
export VLLM_XPU_DDTREE_CAPTURE_GDN_CORE="${VLLM_XPU_DDTREE_CAPTURE_GDN_CORE:-1}"
export VLLM_XPU_DDTREE_FULL_GRAPH="${VLLM_XPU_DDTREE_FULL_GRAPH:-1}"

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
exec "$repo_dir/experiments/qwen36-27b-autoround-int4-b70/scripts/serve-vllm.sh"
