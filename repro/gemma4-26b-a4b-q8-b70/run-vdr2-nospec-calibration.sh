#!/usr/bin/env bash
set -euo pipefail

# Target-side calibration lane for Gemma 4 26B A4B Q8 on one B70.
#
# This intentionally disables MTP/speculative decoding and cache/history
# accelerators so small target-kernel/runtime changes can be compared with much
# lower variance than the MTP record lane. It is diagnostic only; it is not the
# headline MTP throughput recipe.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

GPU_INDEX="${GPU_INDEX:-0}"
PORT="${PORT:-18560}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
LABEL="${LABEL:-gemma4-q8-gpu${GPU_INDEX}-nospec-calib-realistic-full512-${STAMP}}"

# Make accidental inherited speculative knobs inert and keep the run identity
# clean. This wrapper is for target/no-spec calibration only.
while IFS= read -r name; do
  unset "$name"
done < <(compgen -e | grep -E '^LLAMA_(SPEC|MTP)_|^LLAMA_GEMMA4_MTP_' || true)

LLAMA_SERVER="${LLAMA_SERVER:-/home/steve/src/llama.cpp-gemma-record-repro-c926/build-sycl-b70-aot-bmg-g31-q8reorder-vdr2/bin/llama-server}" \
ONEAPI_DEVICE_SELECTOR="${ONEAPI_DEVICE_SELECTOR:-level_zero:${GPU_INDEX}}" \
UR_L0_USE_IMMEDIATE_COMMANDLISTS="${UR_L0_USE_IMMEDIATE_COMMANDLISTS:-1}" \
GGML_SYCL_DISABLE_OPT="${GGML_SYCL_DISABLE_OPT:-0}" \
GGML_SYCL_DISABLE_GRAPH="${GGML_SYCL_DISABLE_GRAPH:-0}" \
GGML_SYCL_ENABLE_VMM="${GGML_SYCL_ENABLE_VMM:-1}" \
LLAMA_SYCL_MUL_MAT_ID_MULTI_TOKEN_FAST="${LLAMA_SYCL_MUL_MAT_ID_MULTI_TOKEN_FAST:-1}" \
LLAMA_SYCL_MUL_MAT_ID_Q8_0_REORDER="${LLAMA_SYCL_MUL_MAT_ID_Q8_0_REORDER:-1}" \
LLAMA_SYCL_MUL_MAT_ID_Q8_0_REORDER_DIRECT_VDR2="${LLAMA_SYCL_MUL_MAT_ID_Q8_0_REORDER_DIRECT_VDR2:-1}" \
LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX="${LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX:-1}" \
LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX_FUSED="${LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX_FUSED:-1}" \
LLAMA_GEMMA4_MOE_WEIGHTED_SUM="${LLAMA_GEMMA4_MOE_WEIGHTED_SUM:-1}" \
LLAMA_GEMMA4_MOE_REUSE_ATTN_RMS="${LLAMA_GEMMA4_MOE_REUSE_ATTN_RMS:-1}" \
LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM_REORDER_VDR2="${LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM_REORDER_VDR2:-1}" \
LLAMA_GEMMA4_FUSED_FINAL_POST_NORM_RESIDUAL="${LLAMA_GEMMA4_FUSED_FINAL_POST_NORM_RESIDUAL:-1}" \
LLAMA_SYCL_MUL_MAT_ID_ROUTE_CACHE="${LLAMA_SYCL_MUL_MAT_ID_ROUTE_CACHE:-1}" \
LLAMA_SYCL_F16_P021_SMALL_NCOLS="${LLAMA_SYCL_F16_P021_SMALL_NCOLS:-1}" \
GPU_INDEX="$GPU_INDEX" PORT="$PORT" \
CTX_SIZE="${CTX_SIZE:-32768}" BATCH_SIZE="${BATCH_SIZE:-1024}" UBATCH_SIZE="${UBATCH_SIZE:-1024}" \
THREADS="${THREADS:-8}" POLL="${POLL:-100}" \
CACHE_TYPE_K="${CACHE_TYPE_K:-f16}" CACHE_TYPE_V="${CACHE_TYPE_V:-f16}" \
FLASH_ATTN="${FLASH_ATTN:-on}" REASONING="${REASONING:-off}" \
CANARY_REPEATS="${CANARY_REPEATS:-32}" MAX_TOKENS="${MAX_TOKENS:-512}" \
REALISTIC_GATE="${REALISTIC_GATE:-1}" REALISTIC_METRIC_TOKENS="${REALISTIC_METRIC_TOKENS:-100}" \
EXTRA_LLAMA_ARGS="${EXTRA_LLAMA_ARGS:---parallel 1 --cache-ram 0 --ctx-checkpoints 0}" \
LABEL="$LABEL" \
scripts/run-gemma4-26b-first-baseline.sh
