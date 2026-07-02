#!/usr/bin/env bash
set -euo pipefail

# Full-output short-decode A/B for the draft-side MUL_MAT_ARGMAX tile subgroup
# knob on the current Gemma 4 26B Q8 record stack.
#
# Isolated variable:
#   control:   LLAMA_SYCL_MUL_MAT_ARGMAX_TILE_SUBGROUPS unset (default 32)
#   candidate: LLAMA_SYCL_MUL_MAT_ARGMAX_TILE_SUBGROUPS=${ARGMAX_TILE_SUBGROUPS}
#
# This is a diagnostic/optimization screen only. Submit/promote only if the
# fixed cold-suite gate passes, cached_tokens=0 for every prompt, and the paired
# analysis beats the current valid record after independent confirmation.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

STAMP="${STAMP:-$(date -u +%Y%m%dT%H%M%SZ)-argmaxtile-short-full512-ab}"
BASE_PORT="${BASE_PORT:-19120}"
MAX_TOKENS="${MAX_TOKENS:-512}"
CANARY_REPEATS="${CANARY_REPEATS:-32}"
REALISTIC_METRIC_TOKENS="${REALISTIC_METRIC_TOKENS:-100}"
READINESS_TIMEOUT_S="${READINESS_TIMEOUT_S:-900}"
ARGMAX_TILE_SUBGROUPS="${ARGMAX_TILE_SUBGROUPS:-16}"

case "$ARGMAX_TILE_SUBGROUPS" in
  1|2|4|8|16|32) ;;
  *)
    echo "[gemma4-argmaxtile-short-ab] invalid ARGMAX_TILE_SUBGROUPS=$ARGMAX_TILE_SUBGROUPS" >&2
    exit 2
    ;;
esac

run_guard() {
  local variant="$1"
  local wave="$2"
  local base_port="$3"
  local lane_specs="$4"
  local enable_candidate="$5"
  local run_stamp="${STAMP}-${wave}-${variant}"

  echo "[gemma4-argmaxtile-short-ab] variant=$variant wave=$wave lanes=$lane_specs"
  (
    if [[ "$enable_candidate" == "1" ]]; then
      export LLAMA_SYCL_MUL_MAT_ARGMAX_TILE_SUBGROUPS="$ARGMAX_TILE_SUBGROUPS"
    else
      unset LLAMA_SYCL_MUL_MAT_ARGMAX_TILE_SUBGROUPS
    fi

    STAMP="$run_stamp" \
    MAX_TOKENS="$MAX_TOKENS" \
    CANARY_REPEATS="$CANARY_REPEATS" \
    REALISTIC_METRIC_TOKENS="$REALISTIC_METRIC_TOKENS" \
    READINESS_TIMEOUT_S="$READINESS_TIMEOUT_S" \
    BASE_PORT="$base_port" \
    LANE_SPECS="$lane_specs" \
    "$ROOT/repro/gemma4-26b-a4b-q8-b70/run-vdr2-short-decode-guard.sh"
  )
}

run_pair() {
  local wave="$1"
  local control_base_port="$2"
  local candidate_base_port="$3"
  local control_specs="$4"
  local candidate_specs="$5"

  run_guard control "$wave" "$control_base_port" "$control_specs" 0 &
  local control_pid=$!
  run_guard candidate "$wave" "$candidate_base_port" "$candidate_specs" 1 &
  local candidate_pid=$!

  local rc=0
  wait "$control_pid" || rc=1
  wait "$candidate_pid" || rc=1
  return "$rc"
}

summary_for() {
  local gpu="$1"
  local tag="$2"
  local run_stamp="$3"
  printf '%s/data/gemma4-q8-gpu%s-shortguard-%s-ctx32768-o%s-%s/summary.json' \
    "$ROOT" "$gpu" "$tag" "$MAX_TOKENS" "$run_stamp"
}

wave_a="waveA"
wave_b="waveB"
candidate_tag="argmaxtile${ARGMAX_TILE_SUBGROUPS}"

run_pair "$wave_a" "$BASE_PORT" "$((BASE_PORT + 20))" \
  '0:1024:1024:control-gpu0 2:1024:1024:control-gpu2' \
  "1:1024:1024:${candidate_tag}-gpu1 3:1024:1024:${candidate_tag}-gpu3"

run_pair "$wave_b" "$((BASE_PORT + 40))" "$((BASE_PORT + 60))" \
  '1:1024:1024:control-gpu1 3:1024:1024:control-gpu3' \
  "0:1024:1024:${candidate_tag}-gpu0 2:1024:1024:${candidate_tag}-gpu2"

analysis_json="$ROOT/data/gemma4-argmaxtile${ARGMAX_TILE_SUBGROUPS}-short-full512-ab-${STAMP}.json"
analysis_md="$ROOT/data/gemma4-argmaxtile${ARGMAX_TILE_SUBGROUPS}-short-full512-ab-${STAMP}.md"

"$ROOT/scripts/analyze-gemma-realistic-ab.py" \
  --control "$(summary_for 0 control-gpu0 "${STAMP}-${wave_a}-control")" \
  --control "$(summary_for 2 control-gpu2 "${STAMP}-${wave_a}-control")" \
  --control "$(summary_for 1 control-gpu1 "${STAMP}-${wave_b}-control")" \
  --control "$(summary_for 3 control-gpu3 "${STAMP}-${wave_b}-control")" \
  --candidate "$(summary_for 1 "${candidate_tag}-gpu1" "${STAMP}-${wave_a}-candidate")" \
  --candidate "$(summary_for 3 "${candidate_tag}-gpu3" "${STAMP}-${wave_a}-candidate")" \
  --candidate "$(summary_for 0 "${candidate_tag}-gpu0" "${STAMP}-${wave_b}-candidate")" \
  --candidate "$(summary_for 2 "${candidate_tag}-gpu2" "${STAMP}-${wave_b}-candidate")" \
  --out "$analysis_json" \
  --markdown-out "$analysis_md"

echo "[gemma4-argmaxtile-short-ab] analysis_json=$analysis_json"
echo "[gemma4-argmaxtile-short-ab] analysis_md=$analysis_md"
