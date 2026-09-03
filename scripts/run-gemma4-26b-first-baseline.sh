#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GPU_INDEX="${GPU_INDEX:-0}"
PORT="${PORT:-18260}"
BASE_URL="${BASE_URL:-http://127.0.0.1:${PORT}}"
MODEL_ALIAS="${MODEL_ALIAS:-gemma4-26b-a4b-q8}"
MODEL="${MODEL:-/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf}"
EXPECTED_LLAMA_SERVER_DEFAULT="/home/steve/src/llama.cpp-gemma-record-repro-c926/build-sycl-b70-aot-bmg-g31-q8reorder-vdr2/bin/llama-server"
LLAMA_SERVER="${LLAMA_SERVER:-$EXPECTED_LLAMA_SERVER_DEFAULT}"
[[ -x "$LLAMA_SERVER" ]] || { echo "set LLAMA_SERVER=/path/to/build/bin/llama-server (not executable: $LLAMA_SERVER)" >&2; exit 2; }
CTX_SIZE="${CTX_SIZE:-8192}"
BATCH_SIZE="${BATCH_SIZE:-512}"
UBATCH_SIZE="${UBATCH_SIZE:-64}"
THREADS="${THREADS:-8}"
CPU_AFFINITY="${CPU_AFFINITY:-}"
CACHE_TYPE_K="${CACHE_TYPE_K:-f16}"
CACHE_TYPE_V="${CACHE_TYPE_V:-f16}"
POLL="${POLL:-50}"
FLASH_ATTN="${FLASH_ATTN:-on}"
REASONING="${REASONING:-off}"
EXTRA_LLAMA_ARGS="${EXTRA_LLAMA_ARGS:-}"
CANARY_REPEATS="${CANARY_REPEATS:-32}"
BENCH_REPEATS="${BENCH_REPEATS:-8}"
PROMPT_TOKENS="${PROMPT_TOKENS:-512}"
BENCH_PROMPT_MODE="${BENCH_PROMPT_MODE:-default}"
MAX_TOKENS="${MAX_TOKENS:-512}"
REALISTIC_GATE="${REALISTIC_GATE:-0}"
REALISTIC_SUITE="${REALISTIC_SUITE:-$ROOT/repro/gemma4-26b-a4b-q8-b70/realistic-suite-v1.json}"
REALISTIC_METRIC_TOKENS="${REALISTIC_METRIC_TOKENS:-100}"
LONG_CONTEXT_GATE="${LONG_CONTEXT_GATE:-0}"
LONG_CONTEXT_SUITE="${LONG_CONTEXT_SUITE:-$ROOT/repro/gemma4-26b-a4b-q8-b70/long-context-suite-v1.json}"
LONG_CONTEXT_CASE_IDS="${LONG_CONTEXT_CASE_IDS:-}"
LONG_CONTEXT_MAX_TARGET_PROMPT_TOKENS="${LONG_CONTEXT_MAX_TARGET_PROMPT_TOKENS:-}"
READINESS_TIMEOUT_S="${READINESS_TIMEOUT_S:-900}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
LABEL="${LABEL:-gemma4-26b-q8-llamacpp-gpu${GPU_INDEX}-ctx${CTX_SIZE}-${STAMP}}"
RUN_DIR="${RUN_DIR:-$ROOT/data/$LABEL}"
SERVER_OUT_DIR="${SERVER_OUT_DIR:-/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers}"
SERVER_LOG="$SERVER_OUT_DIR/${LABEL}.server.log"
SUMMARY_OUT="$RUN_DIR/summary.json"

mkdir -p "$RUN_DIR" "$SERVER_OUT_DIR"

server_pid=""
cleanup() {
  if [[ -n "$server_pid" ]]; then
    kill "$server_pid" 2>/dev/null || true
    wait "$server_pid" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

cd "$ROOT"

echo "[gemma4-baseline] label=$LABEL"
echo "[gemma4-baseline] base_url=$BASE_URL"
echo "[gemma4-baseline] model=$MODEL"
echo "[gemma4-baseline] llama_server=$LLAMA_SERVER"
echo "[gemma4-baseline] server_log=$SERVER_LOG"

GPU_INDEX="$GPU_INDEX" \
PORT="$PORT" \
MODEL_ALIAS="$MODEL_ALIAS" \
MODEL="$MODEL" \
LLAMA_SERVER="$LLAMA_SERVER" \
CTX_SIZE="$CTX_SIZE" \
BATCH_SIZE="$BATCH_SIZE" \
UBATCH_SIZE="$UBATCH_SIZE" \
THREADS="$THREADS" \
CPU_AFFINITY="$CPU_AFFINITY" \
CACHE_TYPE_K="$CACHE_TYPE_K" \
CACHE_TYPE_V="$CACHE_TYPE_V" \
POLL="$POLL" \
FLASH_ATTN="$FLASH_ATTN" \
REASONING="$REASONING" \
EXTRA_LLAMA_ARGS="$EXTRA_LLAMA_ARGS" \
LLAMA_MTP_DRAFT_TOP_K="${LLAMA_MTP_DRAFT_TOP_K:-}" \
LLAMA_MTP_DRAFT_LOGIT_GAP_MIN="${LLAMA_MTP_DRAFT_LOGIT_GAP_MIN:-}" \
LLAMA_MTP_DRAFT_LOGIT_GAP_MIN_START_POS="${LLAMA_MTP_DRAFT_LOGIT_GAP_MIN_START_POS:-}" \
LLAMA_MTP_DRAFT_FAST_TOPK="${LLAMA_MTP_DRAFT_FAST_TOPK:-}" \
LLAMA_MTP_DRAFT_FAST_ARGMAX="${LLAMA_MTP_DRAFT_FAST_ARGMAX:-}" \
LLAMA_MTP_DRAFT_DIRECT_ARGMAX_IDS="${LLAMA_MTP_DRAFT_DIRECT_ARGMAX_IDS:-}" \
LLAMA_MTP_DRAFT_DIRECT_ARGMAX_SCORES="${LLAMA_MTP_DRAFT_DIRECT_ARGMAX_SCORES:-}" \
LLAMA_MTP_DRAFT_DIRECT_ARGMAX_UNROLL="${LLAMA_MTP_DRAFT_DIRECT_ARGMAX_UNROLL:-}" \
LLAMA_MTP_DRAFT_DEVICE_H_HANDOFF="${LLAMA_MTP_DRAFT_DEVICE_H_HANDOFF:-}" \
LLAMA_MTP_DRAFT_BACKEND_ARGMAX="${LLAMA_MTP_DRAFT_BACKEND_ARGMAX:-}" \
LLAMA_MTP_DRAFT_BACKEND_TOPK="${LLAMA_MTP_DRAFT_BACKEND_TOPK:-}" \
LLAMA_MTP_DRAFT_PROFILE="${LLAMA_MTP_DRAFT_PROFILE:-}" \
LLAMA_SERVER_SPEC_PROFILE="${LLAMA_SERVER_SPEC_PROFILE:-}" \
LLAMA_SPEC_VERIFY_SYNC_PROFILE="${LLAMA_SPEC_VERIFY_SYNC_PROFILE:-}" \
GGML_SYCL_NODE_PROFILE="${GGML_SYCL_NODE_PROFILE:-}" \
GGML_SYCL_NODE_PROFILE_EVERY="${GGML_SYCL_NODE_PROFILE_EVERY:-}" \
GGML_SYCL_NODE_PROFILE_DETAIL="${GGML_SYCL_NODE_PROFILE_DETAIL:-}" \
LLAMA_MTP_DRAFT_TERMINAL_LOGITS_ONLY="${LLAMA_MTP_DRAFT_TERMINAL_LOGITS_ONLY:-}" \
LLAMA_MTP_DEFER_TARGET_H_NEXTN="${LLAMA_MTP_DEFER_TARGET_H_NEXTN:-}" \
LLAMA_MTP_DEFER_VERIFIER_PENDING_H_COPY="${LLAMA_MTP_DEFER_VERIFIER_PENDING_H_COPY:-}" \
LLAMA_MTP_DEFER_TARGET_H_ACCEPT_ONLY="${LLAMA_MTP_DEFER_TARGET_H_ACCEPT_ONLY:-}" \
LLAMA_GEMMA4_MTP_FUSED_OUTPUT_ARGMAX="${LLAMA_GEMMA4_MTP_FUSED_OUTPUT_ARGMAX:-}" \
LLAMA_GEMMA4_MTP_QONLY_ATTN_INPUTS="${LLAMA_GEMMA4_MTP_QONLY_ATTN_INPUTS:-}" \
LLAMA_GEMMA4_SKIP_IDENTITY_OUT_IDS="${LLAMA_GEMMA4_SKIP_IDENTITY_OUT_IDS:-}" \
LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX="${LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX:-}" \
LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX_FUSED="${LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX_FUSED:-}" \
LLAMA_GEMMA4_MOE_REUSE_ATTN_RMS="${LLAMA_GEMMA4_MOE_REUSE_ATTN_RMS:-}" \
LLAMA_GEMMA4_FUSED_FINAL_POST_NORM_RESIDUAL="${LLAMA_GEMMA4_FUSED_FINAL_POST_NORM_RESIDUAL:-}" \
LLAMA_GEMMA4_FUSED_ATTN_POST_NORM_RESIDUAL="${LLAMA_GEMMA4_FUSED_ATTN_POST_NORM_RESIDUAL:-}" \
LLAMA_GEMMA4_FUSED_PER_LAYER_POST_NORM_RESIDUAL="${LLAMA_GEMMA4_FUSED_PER_LAYER_POST_NORM_RESIDUAL:-}" \
LLAMA_GEMMA4_MOE_FUSED_BRANCH_POST_NORM_ADD="${LLAMA_GEMMA4_MOE_FUSED_BRANCH_POST_NORM_ADD:-}" \
LLAMA_GEMMA4_MOE_ROUTER_POST_SCALE="${LLAMA_GEMMA4_MOE_ROUTER_POST_SCALE:-}" \
LLAMA_GEMMA4_MOE_TOP_K="${LLAMA_GEMMA4_MOE_TOP_K:-}" \
LLAMA_GEMMA4_MOE_SORTED_TOP_K="${LLAMA_GEMMA4_MOE_SORTED_TOP_K:-}" \
LLAMA_GEMMA4_MOE_WEIGHTED_SUM="${LLAMA_GEMMA4_MOE_WEIGHTED_SUM:-}" \
LLAMA_GEMMA4_MOE_FUSED_ROUTER_SELECTED_WEIGHTS="${LLAMA_GEMMA4_MOE_FUSED_ROUTER_SELECTED_WEIGHTS:-}" \
LLAMA_GEMMA4_MOE_WEIGHTED_SUM_2D="${LLAMA_GEMMA4_MOE_WEIGHTED_SUM_2D:-}" \
LLAMA_GEMMA4_MOE_WEIGHTED_SUM_SELECTED_SOFTMAX="${LLAMA_GEMMA4_MOE_WEIGHTED_SUM_SELECTED_SOFTMAX:-}" \
LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX_WEIGHTED_SUM="${LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX_WEIGHTED_SUM:-}" \
LLAMA_GEMMA4_MOE_SKIP_EARLY_WEIGHTS_EXPAND="${LLAMA_GEMMA4_MOE_SKIP_EARLY_WEIGHTS_EXPAND:-}" \
LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM="${LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM:-}" \
LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM_REORDER_VDR2="${LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM_REORDER_VDR2:-}" \
LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM_REORDER_VDR2_ROWPACK="${LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM_REORDER_VDR2_ROWPACK:-}" \
LLAMA_GEMMA4_MOE_FUSED_DOWN_SELECTED_SOFTMAX="${LLAMA_GEMMA4_MOE_FUSED_DOWN_SELECTED_SOFTMAX:-}" \
LLAMA_GEMMA4_MOE_FUSED_DOWN_SELECTED_SOFTMAX_PRECOMPUTE="${LLAMA_GEMMA4_MOE_FUSED_DOWN_SELECTED_SOFTMAX_PRECOMPUTE:-}" \
LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM_PARALLEL_SLOTS="${LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM_PARALLEL_SLOTS:-}" \
LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM_DIRECT_F32_PARALLEL_SLOTS="${LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM_DIRECT_F32_PARALLEL_SLOTS:-}" \
LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM_MATMUL_EPILOGUE="${LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM_MATMUL_EPILOGUE:-}" \
LLAMA_GEMMA4_MOE_FUSED_GEGLU_DOWN_WEIGHTED_SUM="${LLAMA_GEMMA4_MOE_FUSED_GEGLU_DOWN_WEIGHTED_SUM:-}" \
LLAMA_GEMMA4_MOE_GEGLU_DOWN_MATMUL_EPILOGUE="${LLAMA_GEMMA4_MOE_GEGLU_DOWN_MATMUL_EPILOGUE:-}" \
LLAMA_GEMMA4_MOE_GATEUP_GEGLU="${LLAMA_GEMMA4_MOE_GATEUP_GEGLU:-}" \
LLAMA_GEMMA4_MOE_GATEUP_GEGLU_BF16="${LLAMA_GEMMA4_MOE_GATEUP_GEGLU_BF16:-}" \
LLAMA_GEMMA4_MOE_GATEUP_GEGLU_EPILOGUE="${LLAMA_GEMMA4_MOE_GATEUP_GEGLU_EPILOGUE:-}" \
LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM_DEBUG="${LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM_DEBUG:-}" \
LLAMA_SYCL_MUL_MAT_ID_MULTI_TOKEN_NAME_SUBSTR="${LLAMA_SYCL_MUL_MAT_ID_MULTI_TOKEN_NAME_SUBSTR:-}" \
LLAMA_SYCL_MUL_MAT_ID_MULTI_TOKEN_BF16_DIRECT="${LLAMA_SYCL_MUL_MAT_ID_MULTI_TOKEN_BF16_DIRECT:-}" \
LLAMA_SYCL_MUL_MAT_ID_MULTI_TOKEN_GROUPED_Q8_0_REORDER="${LLAMA_SYCL_MUL_MAT_ID_MULTI_TOKEN_GROUPED_Q8_0_REORDER:-}" \
LLAMA_SYCL_MUL_MAT_ID_GATE_UP_FAST_SEED_ROUTE_CACHE="${LLAMA_SYCL_MUL_MAT_ID_GATE_UP_FAST_SEED_ROUTE_CACHE:-}" \
LLAMA_SYCL_MUL_MAT_ID_GATE_UP_Q8_SINGLETON_DIRECT="${LLAMA_SYCL_MUL_MAT_ID_GATE_UP_Q8_SINGLETON_DIRECT:-}" \
LLAMA_SYCL_MUL_MAT_ID_ROUTE_CACHE="${LLAMA_SYCL_MUL_MAT_ID_ROUTE_CACHE:-}" \
LLAMA_SYCL_MUL_MAT_ID_ROUTE_CACHE_INPLACE="${LLAMA_SYCL_MUL_MAT_ID_ROUTE_CACHE_INPLACE:-}" \
LLAMA_SYCL_MUL_MAT_ID_ROUTE_CACHE_DEVICE_MAP="${LLAMA_SYCL_MUL_MAT_ID_ROUTE_CACHE_DEVICE_MAP:-}" \
LLAMA_SYCL_MUL_MAT_ID_ROUTE_TIMING="${LLAMA_SYCL_MUL_MAT_ID_ROUTE_TIMING:-}" \
LLAMA_SYCL_MUL_MAT_ID_ROUTE_TIMING_EVERY="${LLAMA_SYCL_MUL_MAT_ID_ROUTE_TIMING_EVERY:-}" \
LLAMA_SYCL_MUL_MAT_ID_Q8_0_REORDER="${LLAMA_SYCL_MUL_MAT_ID_Q8_0_REORDER:-}" \
LLAMA_SYCL_MUL_MAT_ID_Q8_0_REORDER_PAIR_SLOTS="${LLAMA_SYCL_MUL_MAT_ID_Q8_0_REORDER_PAIR_SLOTS:-}" \
LLAMA_SYCL_MUL_MAT_ID_Q8_0_REORDER_TOP8_SLOTS="${LLAMA_SYCL_MUL_MAT_ID_Q8_0_REORDER_TOP8_SLOTS:-}" \
LLAMA_SYCL_MUL_MAT_ID_Q8_0_REORDER_DIRECT_VDR2="${LLAMA_SYCL_MUL_MAT_ID_Q8_0_REORDER_DIRECT_VDR2:-}" \
LLAMA_SYCL_MUL_MAT_ID_Q8_0_REORDER_ROWPACK="${LLAMA_SYCL_MUL_MAT_ID_Q8_0_REORDER_ROWPACK:-}" \
LLAMA_SYCL_F16_P021_SMALL_NCOLS="${LLAMA_SYCL_F16_P021_SMALL_NCOLS:-}" \
GGML_SYCL_FATTN_DV512_GQA_NCOLS2="${GGML_SYCL_FATTN_DV512_GQA_NCOLS2:-}" \
GGML_SYCL_FATTN_DV512_GQA8_KQ_REG_BCAST="${GGML_SYCL_FATTN_DV512_GQA8_KQ_REG_BCAST:-}" \
LLAMA_SYCL_Q8_MMVQ_SMALL_NCOLS="${LLAMA_SYCL_Q8_MMVQ_SMALL_NCOLS:-}" \
LLAMA_SYCL_Q8_0_LM_HEAD_1COL_DMMV="${LLAMA_SYCL_Q8_0_LM_HEAD_1COL_DMMV:-}" \
LLAMA_SYCL_Q8_0_LM_HEAD_1COL_NO_REORDER="${LLAMA_SYCL_Q8_0_LM_HEAD_1COL_NO_REORDER:-}" \
LLAMA_SYCL_Q8_0_LM_HEAD_1COL_SUBGROUPS="${LLAMA_SYCL_Q8_0_LM_HEAD_1COL_SUBGROUPS:-}" \
LLAMA_SPEC_VERIFY_GREEDY_ARGMAX="${LLAMA_SPEC_VERIFY_GREEDY_ARGMAX:-}" \
LLAMA_SPEC_VERIFY_BACKEND_ARGMAX_IDS="${LLAMA_SPEC_VERIFY_BACKEND_ARGMAX_IDS:-}" \
LLAMA_SPEC_VERIFY_BULK_SAMPLED_IDS="${LLAMA_SPEC_VERIFY_BULK_SAMPLED_IDS:-}" \
LLAMA_SPEC_VERIFY_DIRECT_SAMPLED_EGRESS="${LLAMA_SPEC_VERIFY_DIRECT_SAMPLED_EGRESS:-}" \
LLAMA_SPEC_VERIFY_DIRECT_SAMPLED_EGRESS_PARITY="${LLAMA_SPEC_VERIFY_DIRECT_SAMPLED_EGRESS_PARITY:-}" \
LLAMA_SPEC_VERIFY_DIRECT_SAMPLED_EGRESS_SKIP_COPY="${LLAMA_SPEC_VERIFY_DIRECT_SAMPLED_EGRESS_SKIP_COPY:-}" \
LLAMA_SPEC_VERIFY_ACCEPT_PREFIX_PARITY="${LLAMA_SPEC_VERIFY_ACCEPT_PREFIX_PARITY:-}" \
LLAMA_SPEC_VERIFY_ACCEPT_PREFIX_ARGMAX="${LLAMA_SPEC_VERIFY_ACCEPT_PREFIX_ARGMAX:-}" \
LLAMA_SPEC_VERIFY_SKIP_STATELESS_ACCEPT="${LLAMA_SPEC_VERIFY_SKIP_STATELESS_ACCEPT:-}" \
LLAMA_SPEC_VERIFY_NO_BONUS_ROW="${LLAMA_SPEC_VERIFY_NO_BONUS_ROW:-}" \
LLAMA_SPEC_VERIFY_STAGE_MTP3="${LLAMA_SPEC_VERIFY_STAGE_MTP3:-}" \
LLAMA_SPEC_VERIFY_STAGE_MTP3_SPLIT_BONUS="${LLAMA_SPEC_VERIFY_STAGE_MTP3_SPLIT_BONUS:-}" \
LLAMA_SPEC_VERIFY_LATE_HEAD_BONUS="${LLAMA_SPEC_VERIFY_LATE_HEAD_BONUS:-}" \
LLAMA_SPEC_VERIFY_PREFIX2_TAIL_HEAD="${LLAMA_SPEC_VERIFY_PREFIX2_TAIL_HEAD:-}" \
LLAMA_SPEC_VERIFY_CLIP_DRAFT_AT_EOG="${LLAMA_SPEC_VERIFY_CLIP_DRAFT_AT_EOG:-}" \
LLAMA_SPEC_VERIFY_ADAPTIVE_BONUS_ROW="${LLAMA_SPEC_VERIFY_ADAPTIVE_BONUS_ROW:-}" \
LLAMA_SPEC_VERIFY_ADAPTIVE_BONUS_WARMUP="${LLAMA_SPEC_VERIFY_ADAPTIVE_BONUS_WARMUP:-}" \
LLAMA_SPEC_VERIFY_ADAPTIVE_BONUS_MIN_FULL_ACCEPT="${LLAMA_SPEC_VERIFY_ADAPTIVE_BONUS_MIN_FULL_ACCEPT:-}" \
LLAMA_SPEC_VERIFY_FUSED_OUTPUT_ARGMAX="${LLAMA_SPEC_VERIFY_FUSED_OUTPUT_ARGMAX:-}" \
LLAMA_SPEC_HEAD_FUSED_OUTPUT_ARGMAX="${LLAMA_SPEC_HEAD_FUSED_OUTPUT_ARGMAX:-}" \
LLAMA_SPEC_VERIFY_SOFTCAP_ARGMAX="${LLAMA_SPEC_VERIFY_SOFTCAP_ARGMAX:-}" \
LLAMA_SPEC_VERIFY_RAW_ARGMAX="${LLAMA_SPEC_VERIFY_RAW_ARGMAX:-}" \
LLAMA_SPEC_VERIFY_REGULAR_MMVQ_TOP1_EPILOGUE="${LLAMA_SPEC_VERIFY_REGULAR_MMVQ_TOP1_EPILOGUE:-}" \
LLAMA_SYCL_MUL_MAT_TOP1_EPILOGUE="${LLAMA_SYCL_MUL_MAT_TOP1_EPILOGUE:-}" \
LLAMA_SYCL_ACCEPT_PREFIX_TOP1_EPILOGUE="${LLAMA_SYCL_ACCEPT_PREFIX_TOP1_EPILOGUE:-}" \
LLAMA_SYCL_MUL_MAT_TOP1_EPILOGUE_PARTIAL="${LLAMA_SYCL_MUL_MAT_TOP1_EPILOGUE_PARTIAL:-}" \
LLAMA_SYCL_MUL_MAT_ARGMAX_TILE_SUBGROUPS="${LLAMA_SYCL_MUL_MAT_ARGMAX_TILE_SUBGROUPS:-}" \
LLAMA_SYCL_MUL_MAT_ARGMAX_MULTI_REUSE="${LLAMA_SYCL_MUL_MAT_ARGMAX_MULTI_REUSE:-}" \
LLAMA_SYCL_MUL_MAT_ARGMAX_REORDER_NCOLS="${LLAMA_SYCL_MUL_MAT_ARGMAX_REORDER_NCOLS:-}" \
LLAMA_SYCL_MUL_MAT_ARGMAX_PROFILE="${LLAMA_SYCL_MUL_MAT_ARGMAX_PROFILE:-}" \
LLAMA_SYCL_MUL_MAT_ARGMAX_PROFILE_EVERY="${LLAMA_SYCL_MUL_MAT_ARGMAX_PROFILE_EVERY:-}" \
LLAMA_SPEC_ADAPTIVE_MTP="${LLAMA_SPEC_ADAPTIVE_MTP:-}" \
LLAMA_SPEC_ADAPTIVE_MTP_WARMUP="${LLAMA_SPEC_ADAPTIVE_MTP_WARMUP:-}" \
LLAMA_SPEC_ADAPTIVE_MTP_LOW_N_MAX="${LLAMA_SPEC_ADAPTIVE_MTP_LOW_N_MAX:-}" \
LLAMA_SPEC_ADAPTIVE_MTP_LOW="${LLAMA_SPEC_ADAPTIVE_MTP_LOW:-}" \
LLAMA_SPEC_ADAPTIVE_MTP_HIGH="${LLAMA_SPEC_ADAPTIVE_MTP_HIGH:-}" \
LLAMA_SPEC_ADAPTIVE_MTP_ALPHA="${LLAMA_SPEC_ADAPTIVE_MTP_ALPHA:-}" \
LLAMA_EXPERIMENTAL_SWA_FATTN_LEFT_BOUND="${LLAMA_EXPERIMENTAL_SWA_FATTN_LEFT_BOUND:-}" \
LLAMA_EXPERIMENTAL_SWA_FATTN_LEFT_BOUND_MIN_Q="${LLAMA_EXPERIMENTAL_SWA_FATTN_LEFT_BOUND_MIN_Q:-}" \
LLAMA_EXPERIMENTAL_SWA_FATTN_LEFT_BOUND_FAST="${LLAMA_EXPERIMENTAL_SWA_FATTN_LEFT_BOUND_FAST:-}" \
LLAMA_EXPERIMENTAL_GLOBAL_FATTN_RIGHT_BOUND="${LLAMA_EXPERIMENTAL_GLOBAL_FATTN_RIGHT_BOUND:-}" \
LLAMA_EXPERIMENTAL_GLOBAL_FATTN_RIGHT_BOUND_MIN_Q="${LLAMA_EXPERIMENTAL_GLOBAL_FATTN_RIGHT_BOUND_MIN_Q:-}" \
LLAMA_EXPERIMENTAL_GLOBAL_FATTN_CAUSAL_FAST_MASK="${LLAMA_EXPERIMENTAL_GLOBAL_FATTN_CAUSAL_FAST_MASK:-}" \
LLAMA_EXPERIMENTAL_GLOBAL_FATTN_CAUSAL_FAST_MASK_MIN_Q="${LLAMA_EXPERIMENTAL_GLOBAL_FATTN_CAUSAL_FAST_MASK_MIN_Q:-}" \
LOG="$SERVER_LOG" \
scripts/run-gemma4-26b-llamacpp-replica.sh > "$RUN_DIR/server.stdout.log" 2>&1 &
server_pid="$!"

deadline=$((SECONDS + READINESS_TIMEOUT_S))
until curl -fsS "$BASE_URL/v1/models" > "$RUN_DIR/models.json" 2> /dev/null; do
  if (( SECONDS >= deadline )); then
    echo "[gemma4-baseline] server did not become ready after ${READINESS_TIMEOUT_S}s" >&2
    tail -80 "$SERVER_LOG" >&2 || true
    exit 1
  fi
  if ! kill -0 "$server_pid" 2>/dev/null; then
    echo "[gemma4-baseline] server exited before readiness" >&2
    tail -80 "$SERVER_LOG" >&2 || true
    exit 1
  fi
  sleep 5
done

echo "[gemma4-baseline] server ready"

python3 scripts/gemma4-text-canary.py \
  --base-url "$BASE_URL" \
  --model "$MODEL_ALIAS" \
  --api-mode chat \
  --repeats "$CANARY_REPEATS" \
  --out "$RUN_DIR/chat-canary.json"

bench_rc=0
if [[ "$LONG_CONTEXT_GATE" == "1" || "$LONG_CONTEXT_GATE" == "true" ]]; then
  long_context_args=()
  if [[ -n "$LONG_CONTEXT_MAX_TARGET_PROMPT_TOKENS" ]]; then
    long_context_args+=(--max-target-prompt-tokens "$LONG_CONTEXT_MAX_TARGET_PROMPT_TOKENS")
  fi
  for case_id in $LONG_CONTEXT_CASE_IDS; do
    long_context_args+=(--case-id "$case_id")
  done
  set +e
  python3 scripts/bench-openai-long-context-suite.py \
    --base-url "$BASE_URL" \
    --model "$MODEL_ALIAS" \
    --suite "$LONG_CONTEXT_SUITE" \
    --max-tokens "$MAX_TOKENS" \
    --out "$RUN_DIR/long-context-suite.json" \
    "${long_context_args[@]}"
  bench_rc=$?
  set -e
elif [[ "$REALISTIC_GATE" == "1" || "$REALISTIC_GATE" == "true" ]]; then
  set +e
  python3 scripts/bench-openai-realistic-suite.py \
    --base-url "$BASE_URL" \
    --model "$MODEL_ALIAS" \
    --api-mode chat \
    --suite "$REALISTIC_SUITE" \
    --max-tokens "$MAX_TOKENS" \
    --metric-tokens "$REALISTIC_METRIC_TOKENS" \
    --out "$RUN_DIR/realistic-suite.json"
  bench_rc=$?
  set -e
else
  set +e
  python3 scripts/bench-openai-single-decode.py \
    --base-url "$BASE_URL" \
    --model "$MODEL_ALIAS" \
    --api-mode chat \
    --prompt-tokens "$PROMPT_TOKENS" \
    --prompt-mode "$BENCH_PROMPT_MODE" \
    --max-tokens "$MAX_TOKENS" \
    --repeats "$BENCH_REPEATS" \
    --out "$RUN_DIR/p${PROMPT_TOKENS}o${MAX_TOKENS}.json"
  bench_rc=$?
  set -e
fi

BENCH_RC="$bench_rc" python3 - "$RUN_DIR" "$LABEL" "$SERVER_LOG" "$SUMMARY_OUT" "$MODEL" <<'PY'
import json
import os
import sys
from pathlib import Path

run_dir = Path(sys.argv[1])
label = sys.argv[2]
server_log = sys.argv[3]
summary_out = Path(sys.argv[4])
model = Path(sys.argv[5])
canary = json.loads((run_dir / "chat-canary.json").read_text())
realistic_path = run_dir / "realistic-suite.json"
long_context_path = run_dir / "long-context-suite.json"
if long_context_path.exists():
    bench_path = long_context_path
    bench = json.loads(long_context_path.read_text())
    bench_kind = "long_context_gate"
elif realistic_path.exists():
    bench_path = realistic_path
    bench = json.loads(realistic_path.read_text())
    bench_kind = "realistic_final_gate"
else:
    bench_path = next(run_dir.glob("p*o*.json"))
    bench = json.loads(bench_path.read_text())
    bench_kind = "synthetic_diagnostic"

server_env = {}
try:
    for line in Path(server_log).read_text(errors="replace").splitlines():
        if line == "--- server ---":
            break
        if "=" in line:
            key, value = line.split("=", 1)
            server_env[key] = value
except OSError:
    pass

def env_or_log(env_key, log_key=None):
    value = os.environ.get(env_key)
    if value:
        return value
    return server_env.get(log_key or env_key)

model_path_lower = str(model).lower()
if "ud-q8_k_xl" in model_path_lower:
    quality_lane = "q8_target"
    headline_eligible_for_gemma_q8 = True
elif "q8_0.gguf" in model_path_lower:
    quality_lane = "alternate_q8_0_control"
    headline_eligible_for_gemma_q8 = False
elif "q4" in model_path_lower or "qat" in model_path_lower:
    quality_lane = "lower_precision_side_lane"
    headline_eligible_for_gemma_q8 = False
else:
    quality_lane = "unknown"
    headline_eligible_for_gemma_q8 = False

out = {
    "label": label,
    "server_log": server_log,
    "run_dir": str(run_dir),
    "model_path": str(model),
    "model_file_bytes": model.stat().st_size if model.exists() else None,
    "quality_lane": quality_lane,
    "headline_eligible_for_gemma_q8": headline_eligible_for_gemma_q8,
    "launcher_identity": {
        "gpu_index": os.environ.get("GPU_INDEX"),
        "port": os.environ.get("PORT"),
        "ctx_size": os.environ.get("CTX_SIZE"),
        "batch_size": os.environ.get("BATCH_SIZE"),
        "ubatch_size": os.environ.get("UBATCH_SIZE"),
        "prefill_ubatch_size": env_or_log("LLAMA_PREFILL_UBATCH_SIZE", "prefill_ubatch_size"),
        "threads": os.environ.get("THREADS"),
        "cpu_affinity": os.environ.get("CPU_AFFINITY"),
        "cache_type_k": os.environ.get("CACHE_TYPE_K"),
        "cache_type_v": os.environ.get("CACHE_TYPE_V"),
        "poll": os.environ.get("POLL"),
        "flash_attn": os.environ.get("FLASH_ATTN"),
        "reasoning": os.environ.get("REASONING"),
        "llama_devices": env_or_log("LLAMA_DEVICES", "llama_devices"),
        "llama_split_mode": env_or_log("LLAMA_SPLIT_MODE", "llama_split_mode"),
        "llama_tensor_split": env_or_log("LLAMA_TENSOR_SPLIT", "llama_tensor_split"),
        "llama_main_gpu": env_or_log("LLAMA_MAIN_GPU", "llama_main_gpu"),
        "extra_llama_args": os.environ.get("EXTRA_LLAMA_ARGS"),
        "realistic_gate": os.environ.get("REALISTIC_GATE"),
        "realistic_suite": os.environ.get("REALISTIC_SUITE"),
        "realistic_metric_tokens": os.environ.get("REALISTIC_METRIC_TOKENS"),
        "long_context_gate": os.environ.get("LONG_CONTEXT_GATE"),
        "long_context_suite": os.environ.get("LONG_CONTEXT_SUITE"),
        "long_context_case_ids": os.environ.get("LONG_CONTEXT_CASE_IDS"),
        "long_context_max_target_prompt_tokens": os.environ.get("LONG_CONTEXT_MAX_TARGET_PROMPT_TOKENS"),
        "llama_mtp_draft_top_k": env_or_log("LLAMA_MTP_DRAFT_TOP_K"),
        "llama_mtp_draft_logit_gap_min": env_or_log("LLAMA_MTP_DRAFT_LOGIT_GAP_MIN"),
        "llama_mtp_draft_logit_gap_min_start_pos": env_or_log("LLAMA_MTP_DRAFT_LOGIT_GAP_MIN_START_POS"),
        "llama_mtp_draft_fast_topk": env_or_log("LLAMA_MTP_DRAFT_FAST_TOPK"),
        "llama_mtp_draft_fast_argmax": env_or_log("LLAMA_MTP_DRAFT_FAST_ARGMAX"),
        "llama_mtp_draft_direct_argmax_ids": env_or_log("LLAMA_MTP_DRAFT_DIRECT_ARGMAX_IDS"),
        "llama_mtp_draft_direct_argmax_scores": env_or_log("LLAMA_MTP_DRAFT_DIRECT_ARGMAX_SCORES"),
        "llama_mtp_draft_direct_argmax_unroll": env_or_log("LLAMA_MTP_DRAFT_DIRECT_ARGMAX_UNROLL"),
        "llama_mtp_draft_device_h_handoff": env_or_log("LLAMA_MTP_DRAFT_DEVICE_H_HANDOFF"),
        "llama_mtp_draft_backend_argmax": env_or_log("LLAMA_MTP_DRAFT_BACKEND_ARGMAX"),
        "llama_mtp_draft_backend_topk": env_or_log("LLAMA_MTP_DRAFT_BACKEND_TOPK"),
        "llama_mtp_draft_profile": env_or_log("LLAMA_MTP_DRAFT_PROFILE"),
        "llama_server_spec_profile": env_or_log("LLAMA_SERVER_SPEC_PROFILE"),
        "llama_spec_verify_sync_profile": env_or_log("LLAMA_SPEC_VERIFY_SYNC_PROFILE"),
        "ggml_sycl_node_profile": env_or_log("GGML_SYCL_NODE_PROFILE"),
        "ggml_sycl_node_profile_every": env_or_log("GGML_SYCL_NODE_PROFILE_EVERY"),
        "ggml_sycl_node_profile_detail": env_or_log("GGML_SYCL_NODE_PROFILE_DETAIL"),
        "llama_mtp_draft_terminal_logits_only": env_or_log("LLAMA_MTP_DRAFT_TERMINAL_LOGITS_ONLY"),
        "llama_mtp_defer_target_h_nextn": env_or_log("LLAMA_MTP_DEFER_TARGET_H_NEXTN"),
        "llama_mtp_defer_verifier_pending_h_copy": env_or_log("LLAMA_MTP_DEFER_VERIFIER_PENDING_H_COPY"),
        "llama_mtp_defer_target_h_accept_only": env_or_log("LLAMA_MTP_DEFER_TARGET_H_ACCEPT_ONLY"),
        "llama_gemma4_mtp_fused_output_argmax": env_or_log("LLAMA_GEMMA4_MTP_FUSED_OUTPUT_ARGMAX"),
        "llama_gemma4_mtp_qonly_attn_inputs": env_or_log("LLAMA_GEMMA4_MTP_QONLY_ATTN_INPUTS"),
        "llama_gemma4_skip_identity_out_ids": env_or_log("LLAMA_GEMMA4_SKIP_IDENTITY_OUT_IDS"),
        "llama_gemma4_moe_selected_softmax": env_or_log("LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX"),
        "llama_gemma4_moe_selected_softmax_fused": env_or_log("LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX_FUSED"),
        "llama_gemma4_moe_reuse_attn_rms": env_or_log("LLAMA_GEMMA4_MOE_REUSE_ATTN_RMS"),
        "llama_gemma4_fused_final_post_norm_residual": env_or_log("LLAMA_GEMMA4_FUSED_FINAL_POST_NORM_RESIDUAL"),
        "llama_gemma4_fused_attn_post_norm_residual": env_or_log("LLAMA_GEMMA4_FUSED_ATTN_POST_NORM_RESIDUAL"),
        "llama_gemma4_fused_per_layer_post_norm_residual": env_or_log("LLAMA_GEMMA4_FUSED_PER_LAYER_POST_NORM_RESIDUAL"),
        "llama_gemma4_moe_fused_branch_post_norm_add": env_or_log("LLAMA_GEMMA4_MOE_FUSED_BRANCH_POST_NORM_ADD"),
        "llama_gemma4_moe_router_post_scale": env_or_log("LLAMA_GEMMA4_MOE_ROUTER_POST_SCALE"),
        "llama_gemma4_moe_top_k": env_or_log("LLAMA_GEMMA4_MOE_TOP_K"),
        "llama_gemma4_moe_sorted_top_k": env_or_log("LLAMA_GEMMA4_MOE_SORTED_TOP_K"),
        "llama_gemma4_moe_weighted_sum": env_or_log("LLAMA_GEMMA4_MOE_WEIGHTED_SUM"),
        "llama_gemma4_moe_fused_router_selected_weights": env_or_log("LLAMA_GEMMA4_MOE_FUSED_ROUTER_SELECTED_WEIGHTS"),
        "llama_gemma4_moe_weighted_sum_2d": env_or_log("LLAMA_GEMMA4_MOE_WEIGHTED_SUM_2D"),
        "llama_gemma4_moe_weighted_sum_selected_softmax": env_or_log("LLAMA_GEMMA4_MOE_WEIGHTED_SUM_SELECTED_SOFTMAX"),
        "llama_gemma4_moe_selected_softmax_weighted_sum": env_or_log("LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX_WEIGHTED_SUM"),
        "llama_gemma4_moe_skip_early_weights_expand": env_or_log("LLAMA_GEMMA4_MOE_SKIP_EARLY_WEIGHTS_EXPAND"),
        "llama_gemma4_moe_fused_down_weighted_sum": env_or_log("LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM"),
        "llama_gemma4_moe_fused_down_weighted_sum_reorder_vdr2": env_or_log("LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM_REORDER_VDR2"),
        "llama_gemma4_moe_fused_down_weighted_sum_reorder_vdr2_rowpack": env_or_log("LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM_REORDER_VDR2_ROWPACK"),
        "llama_gemma4_moe_fused_down_selected_softmax": env_or_log("LLAMA_GEMMA4_MOE_FUSED_DOWN_SELECTED_SOFTMAX"),
        "llama_gemma4_moe_fused_down_selected_softmax_precompute": env_or_log("LLAMA_GEMMA4_MOE_FUSED_DOWN_SELECTED_SOFTMAX_PRECOMPUTE"),
        "llama_gemma4_moe_fused_down_weighted_sum_parallel_slots": env_or_log("LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM_PARALLEL_SLOTS"),
        "llama_gemma4_moe_fused_down_weighted_sum_direct_f32_parallel_slots": env_or_log("LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM_DIRECT_F32_PARALLEL_SLOTS"),
        "llama_gemma4_moe_fused_down_weighted_sum_matmul_epilogue": env_or_log("LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM_MATMUL_EPILOGUE"),
        "llama_gemma4_moe_fused_geglu_down_weighted_sum": env_or_log("LLAMA_GEMMA4_MOE_FUSED_GEGLU_DOWN_WEIGHTED_SUM"),
        "llama_gemma4_moe_geglu_down_matmul_epilogue": env_or_log("LLAMA_GEMMA4_MOE_GEGLU_DOWN_MATMUL_EPILOGUE"),
        "llama_gemma4_moe_gateup_geglu": env_or_log("LLAMA_GEMMA4_MOE_GATEUP_GEGLU"),
        "llama_gemma4_moe_gateup_geglu_bf16": env_or_log("LLAMA_GEMMA4_MOE_GATEUP_GEGLU_BF16"),
        "llama_gemma4_moe_gateup_geglu_epilogue": env_or_log("LLAMA_GEMMA4_MOE_GATEUP_GEGLU_EPILOGUE"),
        "llama_gemma4_moe_fused_down_weighted_sum_debug": env_or_log("LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM_DEBUG"),
        "llama_sycl_mul_mat_id_multi_token_fast": env_or_log("LLAMA_SYCL_MUL_MAT_ID_MULTI_TOKEN_FAST"),
        "llama_sycl_mul_mat_id_multi_token_no_reorder": env_or_log("LLAMA_SYCL_MUL_MAT_ID_MULTI_TOKEN_NO_REORDER"),
        "llama_sycl_mul_mat_id_multi_token_grouped_q8_0": env_or_log("LLAMA_SYCL_MUL_MAT_ID_MULTI_TOKEN_GROUPED_Q8_0"),
        "llama_sycl_mul_mat_id_multi_token_grouped_q8_0_reorder": env_or_log("LLAMA_SYCL_MUL_MAT_ID_MULTI_TOKEN_GROUPED_Q8_0_REORDER"),
        "llama_sycl_mul_mat_id_multi_token_per_slot_q8_0": env_or_log("LLAMA_SYCL_MUL_MAT_ID_MULTI_TOKEN_PER_SLOT_Q8_0"),
        "llama_sycl_mul_mat_id_multi_token_filter": env_or_log("LLAMA_SYCL_MUL_MAT_ID_MULTI_TOKEN_FILTER"),
        "llama_sycl_mul_mat_id_multi_token_name_substr": env_or_log("LLAMA_SYCL_MUL_MAT_ID_MULTI_TOKEN_NAME_SUBSTR"),
        "llama_sycl_mul_mat_id_multi_token_bf16_direct": env_or_log("LLAMA_SYCL_MUL_MAT_ID_MULTI_TOKEN_BF16_DIRECT"),
        "llama_sycl_mul_mat_id_gate_up_fast_seed_route_cache": env_or_log("LLAMA_SYCL_MUL_MAT_ID_GATE_UP_FAST_SEED_ROUTE_CACHE"),
        "llama_sycl_mul_mat_id_gate_up_q8_singleton_direct": env_or_log("LLAMA_SYCL_MUL_MAT_ID_GATE_UP_Q8_SINGLETON_DIRECT"),
        "llama_sycl_mul_mat_id_route_cache": env_or_log("LLAMA_SYCL_MUL_MAT_ID_ROUTE_CACHE"),
        "llama_sycl_mul_mat_id_route_cache_inplace": env_or_log("LLAMA_SYCL_MUL_MAT_ID_ROUTE_CACHE_INPLACE"),
        "llama_sycl_mul_mat_id_route_cache_device_map": env_or_log("LLAMA_SYCL_MUL_MAT_ID_ROUTE_CACHE_DEVICE_MAP"),
        "llama_sycl_mul_mat_id_route_timing": env_or_log("LLAMA_SYCL_MUL_MAT_ID_ROUTE_TIMING"),
        "llama_sycl_mul_mat_id_route_timing_every": env_or_log("LLAMA_SYCL_MUL_MAT_ID_ROUTE_TIMING_EVERY"),
        "llama_sycl_mul_mat_id_q8_0_reorder": env_or_log("LLAMA_SYCL_MUL_MAT_ID_Q8_0_REORDER"),
        "llama_sycl_mul_mat_id_q8_0_reorder_pair_slots": env_or_log("LLAMA_SYCL_MUL_MAT_ID_Q8_0_REORDER_PAIR_SLOTS"),
        "llama_sycl_mul_mat_id_q8_0_reorder_top8_slots": env_or_log("LLAMA_SYCL_MUL_MAT_ID_Q8_0_REORDER_TOP8_SLOTS"),
        "llama_sycl_mul_mat_id_q8_0_reorder_direct_vdr2": env_or_log("LLAMA_SYCL_MUL_MAT_ID_Q8_0_REORDER_DIRECT_VDR2"),
        "llama_sycl_mul_mat_id_q8_0_reorder_rowpack": env_or_log("LLAMA_SYCL_MUL_MAT_ID_Q8_0_REORDER_ROWPACK"),
        "llama_sycl_f16_p021_small_ncols": env_or_log("LLAMA_SYCL_F16_P021_SMALL_NCOLS"),
        "llama_sycl_q8_mmvq_small_ncols": env_or_log("LLAMA_SYCL_Q8_MMVQ_SMALL_NCOLS"),
        "llama_sycl_q8_0_lm_head_1col_dmmv": env_or_log("LLAMA_SYCL_Q8_0_LM_HEAD_1COL_DMMV"),
        "llama_sycl_q8_0_lm_head_1col_no_reorder": env_or_log("LLAMA_SYCL_Q8_0_LM_HEAD_1COL_NO_REORDER"),
        "llama_sycl_q8_0_lm_head_1col_subgroups": env_or_log("LLAMA_SYCL_Q8_0_LM_HEAD_1COL_SUBGROUPS"),
        "llama_spec_verify_greedy_argmax": env_or_log("LLAMA_SPEC_VERIFY_GREEDY_ARGMAX"),
        "llama_spec_verify_backend_argmax_ids": env_or_log("LLAMA_SPEC_VERIFY_BACKEND_ARGMAX_IDS"),
        "llama_spec_verify_backend_argmax_scores": env_or_log("LLAMA_SPEC_VERIFY_BACKEND_ARGMAX_SCORES"),
        "llama_spec_verify_bulk_sampled_ids": env_or_log("LLAMA_SPEC_VERIFY_BULK_SAMPLED_IDS"),
        "llama_spec_verify_direct_sampled_egress": env_or_log("LLAMA_SPEC_VERIFY_DIRECT_SAMPLED_EGRESS"),
        "llama_spec_verify_direct_sampled_egress_parity": env_or_log("LLAMA_SPEC_VERIFY_DIRECT_SAMPLED_EGRESS_PARITY"),
        "llama_spec_verify_direct_sampled_egress_skip_copy": env_or_log("LLAMA_SPEC_VERIFY_DIRECT_SAMPLED_EGRESS_SKIP_COPY"),
        "llama_spec_verify_top2_profile": env_or_log("LLAMA_SPEC_VERIFY_TOP2_PROFILE"),
        "llama_spec_verify_accept_prefix_parity": env_or_log("LLAMA_SPEC_VERIFY_ACCEPT_PREFIX_PARITY"),
        "llama_spec_verify_accept_prefix_argmax": env_or_log("LLAMA_SPEC_VERIFY_ACCEPT_PREFIX_ARGMAX"),
        "llama_spec_verify_skip_stateless_accept": env_or_log("LLAMA_SPEC_VERIFY_SKIP_STATELESS_ACCEPT"),
        "llama_spec_verify_no_bonus_row": env_or_log("LLAMA_SPEC_VERIFY_NO_BONUS_ROW"),
        "llama_spec_verify_stage_mtp3": env_or_log("LLAMA_SPEC_VERIFY_STAGE_MTP3"),
        "llama_spec_verify_stage_mtp3_split_bonus": env_or_log("LLAMA_SPEC_VERIFY_STAGE_MTP3_SPLIT_BONUS"),
        "llama_spec_verify_late_head_bonus": env_or_log("LLAMA_SPEC_VERIFY_LATE_HEAD_BONUS"),
        "llama_spec_verify_prefix2_tail_head": env_or_log("LLAMA_SPEC_VERIFY_PREFIX2_TAIL_HEAD"),
        "llama_spec_verify_clip_draft_at_eog": env_or_log("LLAMA_SPEC_VERIFY_CLIP_DRAFT_AT_EOG"),
        "llama_spec_verify_adaptive_bonus_row": env_or_log("LLAMA_SPEC_VERIFY_ADAPTIVE_BONUS_ROW"),
        "llama_spec_verify_adaptive_bonus_warmup": env_or_log("LLAMA_SPEC_VERIFY_ADAPTIVE_BONUS_WARMUP"),
        "llama_spec_verify_adaptive_bonus_min_full_accept": env_or_log("LLAMA_SPEC_VERIFY_ADAPTIVE_BONUS_MIN_FULL_ACCEPT"),
        "llama_spec_verify_fused_output_argmax": env_or_log("LLAMA_SPEC_VERIFY_FUSED_OUTPUT_ARGMAX"),
        "llama_spec_head_fused_output_argmax": env_or_log("LLAMA_SPEC_HEAD_FUSED_OUTPUT_ARGMAX"),
        "llama_spec_verify_softcap_argmax": env_or_log("LLAMA_SPEC_VERIFY_SOFTCAP_ARGMAX"),
        "llama_spec_verify_raw_argmax": env_or_log("LLAMA_SPEC_VERIFY_RAW_ARGMAX"),
        "llama_spec_verify_regular_mmvq_top1_epilogue": env_or_log("LLAMA_SPEC_VERIFY_REGULAR_MMVQ_TOP1_EPILOGUE"),
        "llama_sycl_mul_mat_top1_epilogue": env_or_log("LLAMA_SYCL_MUL_MAT_TOP1_EPILOGUE"),
        "llama_sycl_accept_prefix_top1_epilogue": env_or_log("LLAMA_SYCL_ACCEPT_PREFIX_TOP1_EPILOGUE"),
        "llama_sycl_mul_mat_top1_epilogue_partial": env_or_log("LLAMA_SYCL_MUL_MAT_TOP1_EPILOGUE_PARTIAL"),
        "llama_sycl_mul_mat_argmax_tile_subgroups": env_or_log("LLAMA_SYCL_MUL_MAT_ARGMAX_TILE_SUBGROUPS"),
        "llama_sycl_mul_mat_argmax_multi_reuse": env_or_log("LLAMA_SYCL_MUL_MAT_ARGMAX_MULTI_REUSE"),
        "llama_sycl_mul_mat_argmax_reorder_ncols": env_or_log("LLAMA_SYCL_MUL_MAT_ARGMAX_REORDER_NCOLS"),
        "llama_sycl_mul_mat_argmax_profile": env_or_log("LLAMA_SYCL_MUL_MAT_ARGMAX_PROFILE"),
        "llama_sycl_mul_mat_argmax_profile_every": env_or_log("LLAMA_SYCL_MUL_MAT_ARGMAX_PROFILE_EVERY"),
        "llama_spec_adaptive_mtp": env_or_log("LLAMA_SPEC_ADAPTIVE_MTP"),
        "llama_spec_adaptive_mtp_warmup": env_or_log("LLAMA_SPEC_ADAPTIVE_MTP_WARMUP"),
        "llama_spec_adaptive_mtp_low_n_max": env_or_log("LLAMA_SPEC_ADAPTIVE_MTP_LOW_N_MAX"),
        "llama_spec_adaptive_mtp_low": env_or_log("LLAMA_SPEC_ADAPTIVE_MTP_LOW"),
        "llama_spec_adaptive_mtp_high": env_or_log("LLAMA_SPEC_ADAPTIVE_MTP_HIGH"),
        "llama_spec_adaptive_mtp_alpha": env_or_log("LLAMA_SPEC_ADAPTIVE_MTP_ALPHA"),
        "llama_experimental_swa_fattn_left_bound": env_or_log("LLAMA_EXPERIMENTAL_SWA_FATTN_LEFT_BOUND"),
        "llama_experimental_swa_fattn_left_bound_min_q": env_or_log("LLAMA_EXPERIMENTAL_SWA_FATTN_LEFT_BOUND_MIN_Q"),
        "llama_experimental_swa_fattn_left_bound_fast": env_or_log("LLAMA_EXPERIMENTAL_SWA_FATTN_LEFT_BOUND_FAST"),
        "llama_experimental_global_fattn_right_bound": env_or_log("LLAMA_EXPERIMENTAL_GLOBAL_FATTN_RIGHT_BOUND"),
        "llama_experimental_global_fattn_right_bound_min_q": env_or_log("LLAMA_EXPERIMENTAL_GLOBAL_FATTN_RIGHT_BOUND_MIN_Q"),
        "llama_experimental_global_fattn_causal_fast_mask": env_or_log("LLAMA_EXPERIMENTAL_GLOBAL_FATTN_CAUSAL_FAST_MASK"),
        "llama_experimental_global_fattn_causal_fast_mask_min_q": env_or_log("LLAMA_EXPERIMENTAL_GLOBAL_FATTN_CAUSAL_FAST_MASK_MIN_Q"),
        "oneapi_device_selector": env_or_log("ONEAPI_DEVICE_SELECTOR"),
        "ur_l0_use_immediate_commandlists": env_or_log("UR_L0_USE_IMMEDIATE_COMMANDLISTS"),
        "ur_l0_enable_relaxed_allocation_limits": env_or_log("UR_L0_ENABLE_RELAXED_ALLOCATION_LIMITS"),
        "ur_l0_use_copy_engine": env_or_log("UR_L0_USE_COPY_ENGINE"),
        "sycl_pi_level_zero_use_copy_engine": env_or_log("SYCL_PI_LEVEL_ZERO_USE_COPY_ENGINE"),
        "ggml_sycl_disable_opt": env_or_log("GGML_SYCL_DISABLE_OPT"),
        "ggml_sycl_enable_vmm": env_or_log("GGML_SYCL_ENABLE_VMM"),
        "ggml_sycl_disable_graph": env_or_log("GGML_SYCL_DISABLE_GRAPH"),
        "ggml_sycl_disable_dnn": env_or_log("GGML_SYCL_DISABLE_DNN"),
        "ggml_sycl_fattn_dv512_gqa_ncols2": env_or_log("GGML_SYCL_FATTN_DV512_GQA_NCOLS2"),
        "ggml_sycl_fattn_dv512_gqa8_kq_reg_bcast": env_or_log("GGML_SYCL_FATTN_DV512_GQA8_KQ_REG_BCAST"),
        "llama_cpp_commit": server_env.get("llama_cpp_commit"),
        "llama_server": server_env.get("llama_server"),
    },
    "canary_pass_all": canary["summary"]["pass_all"],
    "canary_rows_completed": canary["summary"]["rows_completed"],
    "bench_rc": int(os.environ.get("BENCH_RC", "0")),
    "bench_kind": bench_kind,
    "bench_path": str(bench_path),
    "bench_summary": bench["summary"],
    "fresh_response_validity": bench.get("fresh_response_validity"),
    "realistic_final_gate": bench.get("realistic_final_gate"),
    "long_context_gate": (bench.get("summary") or {}).get("long_context_gate"),
    "bench_run_identity": bench["run_identity"],
}
summary_out.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
print(json.dumps(out, indent=2, sort_keys=True))
PY

echo "[gemma4-baseline] summary=$SUMMARY_OUT"
exit "$bench_rc"
