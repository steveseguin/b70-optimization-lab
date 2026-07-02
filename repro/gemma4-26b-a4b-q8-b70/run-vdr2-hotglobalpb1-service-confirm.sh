#!/usr/bin/env bash
set -euo pipefail

# Reproduce the Gemma 4 26B Q8 long-context service A/B for a narrow scheduler
# experiment on the hot global GQA8 FlashAttention tile:
#
#   control:   current service stack + KQ register/broadcast service flag
#   candidate: control + GGML_SYCL_FATTN_DV512_GQA8_GLOBAL_PB1=1
#
# This is a service/prefill validation wrapper, not a short-decode
# LocalMaxxing record command. The default REPLICATES=2 runs four paired waves,
# so every GPU sees both control and candidate twice.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

STAMP="${STAMP:-$(date -u +%Y%m%dT%H%M%SZ)-hotglobalpb1-service-confirm}"
BASE_PORT="${BASE_PORT:-19040}"
REPLICATES="${REPLICATES:-2}"
LONG_CONTEXT_CASE_IDS="${LONG_CONTEXT_CASE_IDS:-lc-12288-early lc-16384-late lc-22000-middle}"
LONG_CONTEXT_MAX_TARGET_PROMPT_TOKENS="${LONG_CONTEXT_MAX_TARGET_PROMPT_TOKENS:-24000}"
CANARY_REPEATS_LONG="${CANARY_REPEATS_LONG:-2}"
MAX_TOKENS_LONG="${MAX_TOKENS_LONG:-96}"
READINESS_TIMEOUT_S="${READINESS_TIMEOUT_S:-900}"
RUN_SHORT_GUARD="${RUN_SHORT_GUARD:-0}"
CANARY_REPEATS_SHORT="${CANARY_REPEATS_SHORT:-8}"
MAX_TOKENS_SHORT="${MAX_TOKENS_SHORT:-256}"

run_gate() {
  local variant="$1"
  local wave="$2"
  local base_port="$3"
  local lane_specs="$4"
  local enable_candidate="$5"

  local run_stamp="${STAMP}-${wave}-${variant}"
  echo "[gemma4-hotglobalpb1-confirm] variant=$variant wave=$wave lanes=$lane_specs"
  (
    export GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8
    export GGML_SYCL_FATTN_DV512_GQA8_KQ_REG_BCAST=1
    export LLAMA_EXPERIMENTAL_SWA_FATTN_LEFT_BOUND=1
    export LLAMA_EXPERIMENTAL_SWA_FATTN_LEFT_BOUND_MIN_Q=2048
    if [[ "$enable_candidate" == "1" ]]; then
      export GGML_SYCL_FATTN_DV512_GQA8_GLOBAL_PB1=1
    else
      unset GGML_SYCL_FATTN_DV512_GQA8_GLOBAL_PB1
    fi

    STAMP="$run_stamp" \
    LONG_CONTEXT_CASE_IDS="$LONG_CONTEXT_CASE_IDS" \
    LONG_CONTEXT_MAX_TARGET_PROMPT_TOKENS="$LONG_CONTEXT_MAX_TARGET_PROMPT_TOKENS" \
    CANARY_REPEATS="$CANARY_REPEATS_LONG" \
    MAX_TOKENS="$MAX_TOKENS_LONG" \
    READINESS_TIMEOUT_S="$READINESS_TIMEOUT_S" \
    BASE_PORT="$base_port" \
    LANE_SPECS="$lane_specs" \
    "$ROOT/repro/gemma4-26b-a4b-q8-b70/run-vdr2-long-context-service-gate.sh"
  )
}

run_pair() {
  local wave="$1"
  local control_base_port="$2"
  local candidate_base_port="$3"
  local control_specs="$4"
  local candidate_specs="$5"

  run_gate control "$wave" "$control_base_port" "$control_specs" 0 &
  local control_pid=$!
  run_gate candidate "$wave" "$candidate_base_port" "$candidate_specs" 1 &
  local candidate_pid=$!

  local rc=0
  wait "$control_pid" || rc=1
  wait "$candidate_pid" || rc=1
  return "$rc"
}

letters=(A B C D E F G H)
for ((rep = 0; rep < REPLICATES; rep++)); do
  wave_ab="wave${letters[$((rep * 2))]}"
  wave_ba="wave${letters[$((rep * 2 + 1))]}"
  port_base=$((BASE_PORT + rep * 80))

  run_pair "$wave_ab" "$port_base" "$((port_base + 20))" \
    '0:2048:1024:control-gpu0:2048 2:2048:1024:control-gpu2:2048' \
    '1:2048:1024:candidate-gpu1:2048 3:2048:1024:candidate-gpu3:2048'

  run_pair "$wave_ba" "$((port_base + 40))" "$((port_base + 60))" \
    '1:2048:1024:control-gpu1:2048 3:2048:1024:control-gpu3:2048' \
    '0:2048:1024:candidate-gpu0:2048 2:2048:1024:candidate-gpu2:2048'
done

compare_args=(
  --kind gemma4_global_fattn_gqa8_hot_global_pb1_ab_comparison
  --decision needs-review
  --candidate-env GGML_SYCL_FATTN_DV512_GQA8_GLOBAL_PB1=1
  --candidate-env GGML_SYCL_FATTN_DV512_GQA8_KQ_REG_BCAST=1
  --candidate-env GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8
  --notes "Default-off hot-shape-only parallel_blocks=1 gate for the profiled global GQA8 FlashAttention service shape; service/prefill diagnostic, not LocalMaxxing headline."
)

for ((rep = 0; rep < REPLICATES; rep++)); do
  wave_ab="wave${letters[$((rep * 2))]}"
  wave_ba="wave${letters[$((rep * 2 + 1))]}"
  compare_args+=(
    --control "$wave_ab=data/gemma4-long-context-service-gate-${STAMP}-${wave_ab}-control.json"
    --candidate "$wave_ab=data/gemma4-long-context-service-gate-${STAMP}-${wave_ab}-candidate.json"
    --control "$wave_ba=data/gemma4-long-context-service-gate-${STAMP}-${wave_ba}-control.json"
    --candidate "$wave_ba=data/gemma4-long-context-service-gate-${STAMP}-${wave_ba}-candidate.json"
  )
done

comparison="$ROOT/data/gemma4-global-fattn-hotglobalpb1-comparison-${STAMP}.json"
"$ROOT/scripts/compare-gemma-long-context-service-ab.py" \
  "${compare_args[@]}" \
  --output "$comparison"
echo "[gemma4-hotglobalpb1-confirm] comparison=$comparison"

if [[ "$RUN_SHORT_GUARD" == "1" || "$RUN_SHORT_GUARD" == "true" ]]; then
  GGML_SYCL_FATTN_DV512_GQA8_GLOBAL_PB1=1 \
  GGML_SYCL_FATTN_DV512_GQA8_KQ_REG_BCAST=1 \
  GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8 \
  LLAMA_EXPERIMENTAL_SWA_FATTN_LEFT_BOUND=1 \
  LLAMA_EXPERIMENTAL_SWA_FATTN_LEFT_BOUND_MIN_Q=2048 \
  CANARY_REPEATS="$CANARY_REPEATS_SHORT" \
  MAX_TOKENS="$MAX_TOKENS_SHORT" \
  REALISTIC_METRIC_TOKENS=100 \
  READINESS_TIMEOUT_S="$READINESS_TIMEOUT_S" \
  BASE_PORT="$((BASE_PORT + REPLICATES * 80 + 20))" \
  LANE_SPECS='0:1024:1024:hotglobalpb1-ub1024-a 1:1024:1024:hotglobalpb1-ub1024-b 2:2048:2048:hotglobalpb1-ub2048-a 3:2048:2048:hotglobalpb1-ub2048-b' \
  "$ROOT/repro/gemma4-26b-a4b-q8-b70/run-vdr2-short-decode-guard.sh"
fi
