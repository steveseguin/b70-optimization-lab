#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

# Validated service profile for Gemma 4 26B A4B Q8 on B70:
# - prefill uses larger chunks via LLAMA_PREFILL_UBATCH_SIZE=2048;
# - decode stays at UBATCH_SIZE=1024, matching the short-record-friendly shape;
# - DV512/GQA8 FlashAttention selector is enabled for long-context prefill.
#
# This is a service/prefill recipe, not a LocalMaxxing short-decode headline.
# The source-side phase-ubatch support is preserved at:
#   patches/gemma4-26b-a4b-q8-b70/20260630-llama-phase-prefill-ubatch-memory-sized-experiment.patch

export GGML_SYCL_FATTN_DV512_GQA_NCOLS2="${GGML_SYCL_FATTN_DV512_GQA_NCOLS2:-8}"
export LLAMA_PREFILL_UBATCH_SIZE="${LLAMA_PREFILL_UBATCH_SIZE:-2048}"

STAMP="${STAMP:-$(date -u +%Y%m%dT%H%M%SZ)}"
LONG_CONTEXT_CASE_IDS="${LONG_CONTEXT_CASE_IDS:-lc-12288-early lc-16384-late lc-22000-middle}"
LONG_CONTEXT_MAX_TARGET_PROMPT_TOKENS="${LONG_CONTEXT_MAX_TARGET_PROMPT_TOKENS:-24000}"
CANARY_REPEATS="${CANARY_REPEATS:-2}"
MAX_TOKENS="${MAX_TOKENS:-96}"
BASE_PORT="${BASE_PORT:-18520}"

# One replica per B70. The middle fields are BATCH_SIZE:UBATCH_SIZE; prefill
# chunking is controlled globally by LLAMA_PREFILL_UBATCH_SIZE above.
LANE_SPECS="${LANE_SPECS:-0:2048:1024:phase2048-ub1024-a 1:2048:1024:phase2048-ub1024-b 2:2048:1024:phase2048-ub1024-c 3:2048:1024:phase2048-ub1024-d}"

echo "[gemma4-gqa8-phase-prefill] stamp=$STAMP"
echo "[gemma4-gqa8-phase-prefill] GGML_SYCL_FATTN_DV512_GQA_NCOLS2=$GGML_SYCL_FATTN_DV512_GQA_NCOLS2"
echo "[gemma4-gqa8-phase-prefill] LLAMA_PREFILL_UBATCH_SIZE=$LLAMA_PREFILL_UBATCH_SIZE"
echo "[gemma4-gqa8-phase-prefill] lanes=$LANE_SPECS"

STAMP="$STAMP" \
LONG_CONTEXT_CASE_IDS="$LONG_CONTEXT_CASE_IDS" \
LONG_CONTEXT_MAX_TARGET_PROMPT_TOKENS="$LONG_CONTEXT_MAX_TARGET_PROMPT_TOKENS" \
CANARY_REPEATS="$CANARY_REPEATS" \
MAX_TOKENS="$MAX_TOKENS" \
BASE_PORT="$BASE_PORT" \
LANE_SPECS="$LANE_SPECS" \
"$ROOT/repro/gemma4-26b-a4b-q8-b70/run-vdr2-long-context-service-gate.sh"
