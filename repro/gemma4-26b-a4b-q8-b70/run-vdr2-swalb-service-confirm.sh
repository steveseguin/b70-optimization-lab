#!/usr/bin/env bash
set -euo pipefail

# Reproduce the Gemma 4 26B Q8 long-context service confirmation for the
# host-derived SWA FlashAttention left-bound path. This is a service/prefill
# validation wrapper, not a short-decode LocalMaxxing record command.
#
# It runs a four-GPU long-context A/B plus GPU cross-over:
#   control: phase prefill 2048/1024 + GQA8 tile selector
#   candidate: control + LLAMA_EXPERIMENTAL_SWA_FATTN_LEFT_BOUND=1 MIN_Q=2048
#
# Set RUN_SHORT_GUARD=1 to also run the full512 short realistic-suite guard.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

STAMP="${STAMP:-$(date -u +%Y%m%dT%H%M%SZ)-swalb-service-confirm}"
BASE_PORT="${BASE_PORT:-18800}"
LONG_CONTEXT_CASE_IDS="${LONG_CONTEXT_CASE_IDS:-lc-12288-early lc-16384-late lc-22000-middle}"
LONG_CONTEXT_MAX_TARGET_PROMPT_TOKENS="${LONG_CONTEXT_MAX_TARGET_PROMPT_TOKENS:-24000}"
CANARY_REPEATS_LONG="${CANARY_REPEATS_LONG:-2}"
CANARY_REPEATS_SHORT="${CANARY_REPEATS_SHORT:-32}"
MAX_TOKENS_LONG="${MAX_TOKENS_LONG:-96}"
MAX_TOKENS_SHORT="${MAX_TOKENS_SHORT:-512}"
READINESS_TIMEOUT_S="${READINESS_TIMEOUT_S:-900}"
RUN_SHORT_GUARD="${RUN_SHORT_GUARD:-1}"

run_round() {
  local round="$1"
  local base_port="$2"
  local long_gate="$3"
  local max_tokens="$4"
  local canary_repeats="$5"
  shift 5
  local specs=("$@")
  local pids=()
  local labels=()
  local variants=()

  echo "[gemma4-swalb-confirm] round=$round long_gate=$long_gate max_tokens=$max_tokens specs=${specs[*]}"
  for spec in "${specs[@]}"; do
    IFS=: read -r gpu variant on <<<"$spec"
    if [[ -z "$gpu" || -z "$variant" || -z "$on" ]]; then
      echo "[gemma4-swalb-confirm] invalid spec: $spec" >&2
      exit 2
    fi
    local port=$((base_port + gpu))
    local mode="longctx"
    if [[ "$long_gate" != "1" ]]; then
      mode="shortguard"
    fi
    local label="gemma4-q8-gpu${gpu}-${mode}-${variant}-swalb2048-${STAMP}-${round}"
    labels+=("$label")
    variants+=("$variant")
    (
      export GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8
      export LLAMA_PREFILL_UBATCH_SIZE=2048
      if [[ "$on" == "1" ]]; then
        export LLAMA_EXPERIMENTAL_SWA_FATTN_LEFT_BOUND=1
        export LLAMA_EXPERIMENTAL_SWA_FATTN_LEFT_BOUND_MIN_Q=2048
      else
        unset LLAMA_EXPERIMENTAL_SWA_FATTN_LEFT_BOUND
        unset LLAMA_EXPERIMENTAL_SWA_FATTN_LEFT_BOUND_MIN_Q
      fi
      GPU_INDEX="$gpu" \
      PORT="$port" \
      LABEL="$label" \
      CTX_SIZE=32768 \
      FLASH_ATTN=on \
      GGML_SYCL_ENABLE_VMM=1 \
      BATCH_SIZE=2048 \
      UBATCH_SIZE=1024 \
      MAX_TOKENS="$max_tokens" \
      CANARY_REPEATS="$canary_repeats" \
      REALISTIC_GATE=$([[ "$long_gate" == "1" ]] && echo 0 || echo 1) \
      REALISTIC_METRIC_TOKENS=100 \
      LONG_CONTEXT_GATE="$long_gate" \
      LONG_CONTEXT_CASE_IDS="$LONG_CONTEXT_CASE_IDS" \
      LONG_CONTEXT_MAX_TARGET_PROMPT_TOKENS="$LONG_CONTEXT_MAX_TARGET_PROMPT_TOKENS" \
      READINESS_TIMEOUT_S="$READINESS_TIMEOUT_S" \
      "$ROOT/repro/gemma4-26b-a4b-q8-b70/run-vdr2-selecteddown-record.sh"
    ) >"$ROOT/data/${label}.driver.log" 2>&1 &
    pids+=("$!")
  done

  local rc=0
  for i in "${!pids[@]}"; do
    if wait "${pids[$i]}"; then
      echo "[gemma4-swalb-confirm] PASS ${variants[$i]} ${labels[$i]}"
    else
      local lane_rc=$?
      echo "[gemma4-swalb-confirm] FAIL rc=$lane_rc ${variants[$i]} ${labels[$i]}" >&2
      rc=1
    fi
  done

  local label_file="$ROOT/data/gemma4-swalb-confirm-labels-${STAMP}-${round}.txt"
  : > "$label_file"
  for i in "${!labels[@]}"; do
    printf '%s %s\n' "${variants[$i]}" "${labels[$i]}" >> "$label_file"
  done
  echo "[gemma4-swalb-confirm] labels=$label_file"
  return "$rc"
}

run_round long-ab "$BASE_PORT" 1 "$MAX_TOKENS_LONG" "$CANARY_REPEATS_LONG" \
  '0:control:0' '1:swalb:1' '2:control:0' '3:swalb:1'

run_round long-xover "$((BASE_PORT + 20))" 1 "$MAX_TOKENS_LONG" "$CANARY_REPEATS_LONG" \
  '0:swalb:1' '1:control:0' '2:swalb:1' '3:control:0'

if [[ "$RUN_SHORT_GUARD" == "1" || "$RUN_SHORT_GUARD" == "true" ]]; then
  run_round short-ab "$((BASE_PORT + 40))" 0 "$MAX_TOKENS_SHORT" "$CANARY_REPEATS_SHORT" \
    '0:control:0' '1:swalb:1' '2:control:0' '3:swalb:1'
  run_round short-xover "$((BASE_PORT + 60))" 0 "$MAX_TOKENS_SHORT" "$CANARY_REPEATS_SHORT" \
    '0:swalb:1' '1:control:0' '2:swalb:1' '3:control:0'
fi
