#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

# Validated service/prefill optimization for Gemma 4 26B A4B Q8 on B70:
# force the DV512/GQA FlashAttention tile shape to ncols2=8. This is a
# long-context service gate, not a LocalMaxxing short-decode headline recipe.
export GGML_SYCL_FATTN_DV512_GQA_NCOLS2="${GGML_SYCL_FATTN_DV512_GQA_NCOLS2:-8}"

STAMP="${STAMP:-$(date -u +%Y%m%dT%H%M%SZ)}"
LONG_CONTEXT_CASE_IDS="${LONG_CONTEXT_CASE_IDS:-lc-12288-early lc-16384-late lc-22000-middle}"
LONG_CONTEXT_MAX_TARGET_PROMPT_TOKENS="${LONG_CONTEXT_MAX_TARGET_PROMPT_TOKENS:-24000}"
CANARY_REPEATS="${CANARY_REPEATS:-2}"
MAX_TOKENS="${MAX_TOKENS:-96}"
BASE_PORT="${BASE_PORT:-18520}"

# Broad default:
# - UB1024 keeps the best decode balance;
# - UB2048 is the general service default candidate;
# - UB2304/UB2560 probe pure long-prefill throughput.
LANE_SPECS="${LANE_SPECS:-0:1024:1024:ub1024-gqa8 1:2048:2048:ub2048-gqa8 2:2304:2304:ub2304-gqa8 3:2560:2560:ub2560-gqa8}"

echo "[gemma4-gqa8-long-prefill] stamp=$STAMP"
echo "[gemma4-gqa8-long-prefill] GGML_SYCL_FATTN_DV512_GQA_NCOLS2=$GGML_SYCL_FATTN_DV512_GQA_NCOLS2"
echo "[gemma4-gqa8-long-prefill] lanes=$LANE_SPECS"

STAMP="$STAMP" \
LONG_CONTEXT_CASE_IDS="$LONG_CONTEXT_CASE_IDS" \
LONG_CONTEXT_MAX_TARGET_PROMPT_TOKENS="$LONG_CONTEXT_MAX_TARGET_PROMPT_TOKENS" \
CANARY_REPEATS="$CANARY_REPEATS" \
MAX_TOKENS="$MAX_TOKENS" \
BASE_PORT="$BASE_PORT" \
LANE_SPECS="$LANE_SPECS" \
"$ROOT/repro/gemma4-26b-a4b-q8-b70/run-vdr2-long-context-service-gate.sh"
