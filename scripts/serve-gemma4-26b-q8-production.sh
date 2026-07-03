#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_dir"

profile="${GEMMA4_26B_PROFILE:-record}"
batch_size_was_set="${BATCH_SIZE+x}"
ubatch_size_was_set="${UBATCH_SIZE+x}"
case "$profile" in
  record|service)
    ;;
  *)
    echo "Invalid GEMMA4_26B_PROFILE=$profile; expected record or service" >&2
    exit 2
    ;;
esac

export GPU_INDEX="${GPU_INDEX:-0}"
export PORT="${PORT:-19350}"
export HOST="${HOST:-127.0.0.1}"
export MODEL_ALIAS="${MODEL_ALIAS:-gemma4-26b-a4b-q8}"
export MODEL="${MODEL:-/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf}"
export LLAMA_SERVER="${LLAMA_SERVER:-/home/steve/src/llama.cpp-gemma-record-repro-c926/build-sycl-b70-aot-bmg-g31-q8reorder-vdr2/bin/llama-server}"
export OUT_DIR="${OUT_DIR:-/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers}"

# Shared production defaults. Keep target/verifier at UD-Q8_K_XL. The Q4_0 MTP
# draft proposes only; accepted tokens are verified by the Q8 target.
export CTX_SIZE="${CTX_SIZE:-32768}"
export BATCH_SIZE="${BATCH_SIZE:-1024}"
export UBATCH_SIZE="${UBATCH_SIZE:-1024}"
export THREADS="${THREADS:-8}"
export POLL="${POLL:-100}"
export FLASH_ATTN="${FLASH_ATTN:-on}"
export CACHE_TYPE_K="${CACHE_TYPE_K:-f16}"
export CACHE_TYPE_V="${CACHE_TYPE_V:-f16}"
export REASONING="${REASONING:-off}"
export GGML_SYCL_ENABLE_VMM="${GGML_SYCL_ENABLE_VMM:-1}"
export GGML_SYCL_DISABLE_OPT="${GGML_SYCL_DISABLE_OPT:-0}"
export GGML_SYCL_DISABLE_GRAPH="${GGML_SYCL_DISABLE_GRAPH:-0}"
export UR_L0_USE_IMMEDIATE_COMMANDLISTS="${UR_L0_USE_IMMEDIATE_COMMANDLISTS:-1}"
export UR_L0_ENABLE_RELAXED_ALLOCATION_LIMITS="${UR_L0_ENABLE_RELAXED_ALLOCATION_LIMITS:-1}"

export LLAMA_SYCL_MUL_MAT_ID_MULTI_TOKEN_FAST="${LLAMA_SYCL_MUL_MAT_ID_MULTI_TOKEN_FAST:-1}"
export LLAMA_SYCL_MUL_MAT_ID_Q8_0_REORDER="${LLAMA_SYCL_MUL_MAT_ID_Q8_0_REORDER:-1}"
export LLAMA_SYCL_MUL_MAT_ID_Q8_0_REORDER_DIRECT_VDR2="${LLAMA_SYCL_MUL_MAT_ID_Q8_0_REORDER_DIRECT_VDR2:-1}"
export LLAMA_SPEC_VERIFY_BACKEND_ARGMAX_IDS="${LLAMA_SPEC_VERIFY_BACKEND_ARGMAX_IDS:-1}"
export LLAMA_SPEC_VERIFY_BULK_SAMPLED_IDS="${LLAMA_SPEC_VERIFY_BULK_SAMPLED_IDS:-1}"
export LLAMA_MTP_DEFER_TARGET_H_NEXTN="${LLAMA_MTP_DEFER_TARGET_H_NEXTN:-1}"
export LLAMA_MTP_DRAFT_FAST_ARGMAX="${LLAMA_MTP_DRAFT_FAST_ARGMAX:-1}"
export LLAMA_MTP_DRAFT_DIRECT_ARGMAX_IDS="${LLAMA_MTP_DRAFT_DIRECT_ARGMAX_IDS:-1}"
export LLAMA_MTP_DRAFT_DIRECT_ARGMAX_UNROLL="${LLAMA_MTP_DRAFT_DIRECT_ARGMAX_UNROLL:-7}"
export LLAMA_GEMMA4_MTP_QONLY_ATTN_INPUTS="${LLAMA_GEMMA4_MTP_QONLY_ATTN_INPUTS:-1}"
export LLAMA_GEMMA4_MTP_FUSED_OUTPUT_ARGMAX="${LLAMA_GEMMA4_MTP_FUSED_OUTPUT_ARGMAX:-1}"
export LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX="${LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX:-1}"
export LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX_FUSED="${LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX_FUSED:-1}"
export LLAMA_GEMMA4_MOE_WEIGHTED_SUM="${LLAMA_GEMMA4_MOE_WEIGHTED_SUM:-1}"
export LLAMA_GEMMA4_MOE_REUSE_ATTN_RMS="${LLAMA_GEMMA4_MOE_REUSE_ATTN_RMS:-1}"
export LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM_REORDER_VDR2="${LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM_REORDER_VDR2:-1}"
export LLAMA_GEMMA4_FUSED_FINAL_POST_NORM_RESIDUAL="${LLAMA_GEMMA4_FUSED_FINAL_POST_NORM_RESIDUAL:-1}"
export LLAMA_SYCL_MUL_MAT_ID_ROUTE_CACHE="${LLAMA_SYCL_MUL_MAT_ID_ROUTE_CACHE:-1}"
export LLAMA_SYCL_F16_P021_SMALL_NCOLS="${LLAMA_SYCL_F16_P021_SMALL_NCOLS:-1}"

if [[ "$profile" == "service" ]]; then
  # Service/prefill profile: validated on the long-context ladder. This keeps
  # the same Q8 target and MTP verifier rules, but favors prompt throughput.
  if [[ -z "$batch_size_was_set" ]]; then
    export BATCH_SIZE=2048
  fi
  if [[ -z "$ubatch_size_was_set" ]]; then
    export UBATCH_SIZE=1024
  fi
  export LLAMA_PREFILL_UBATCH_SIZE="${LLAMA_PREFILL_UBATCH_SIZE:-2048}"
  export GGML_SYCL_FATTN_DV512_GQA_NCOLS2="${GGML_SYCL_FATTN_DV512_GQA_NCOLS2:-8}"
  export LLAMA_EXPERIMENTAL_SWA_FATTN_LEFT_BOUND="${LLAMA_EXPERIMENTAL_SWA_FATTN_LEFT_BOUND:-1}"
  export LLAMA_EXPERIMENTAL_SWA_FATTN_LEFT_BOUND_MIN_Q="${LLAMA_EXPERIMENTAL_SWA_FATTN_LEFT_BOUND_MIN_Q:-2048}"
  export GGML_SYCL_FATTN_DV512_GQA8_KQ_REG_BCAST="${GGML_SYCL_FATTN_DV512_GQA8_KQ_REG_BCAST:-1}"
fi

export EXTRA_LLAMA_ARGS="${EXTRA_LLAMA_ARGS:---parallel 1 --cache-ram 0 --spec-type draft-mtp --spec-draft-model /mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/MTP/gemma-4-26B-A4B-it-Q4_0-MTP.gguf --spec-draft-n-max 3 --spec-draft-device SYCL0 --spec-draft-ngl all --spec-draft-type-k f16 --spec-draft-type-v f16 --spec-draft-n-min 2 --spec-draft-p-min 0.0475 --no-spec-draft-backend-sampling --spec-draft-threads 32 --spec-draft-threads-batch 32 --ctx-checkpoints 0}"

echo "[gemma4-prod] profile=$profile gpu=$GPU_INDEX endpoint=http://$HOST:$PORT/v1"
echo "[gemma4-prod] model=$MODEL"
echo "[gemma4-prod] llama_server=$LLAMA_SERVER"
exec "$repo_dir/scripts/run-gemma4-26b-llamacpp-replica.sh"
