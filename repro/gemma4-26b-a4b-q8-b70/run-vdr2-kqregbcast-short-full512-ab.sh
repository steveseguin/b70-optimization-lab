#!/usr/bin/env bash
set -euo pipefail

# Full-output short-decode A/B for the default-off global FlashAttention KQ
# register/broadcast path. This is not a LocalMaxxing submission command by
# itself; it produces fixed-cold-suite control/candidate summaries plus a
# paired per-prompt analysis.
#
# Isolated variable:
#   control:   GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8
#   candidate: control + GGML_SYCL_FATTN_DV512_GQA8_KQ_REG_BCAST=1

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

STAMP="${STAMP:-$(date -u +%Y%m%dT%H%M%SZ)-kqregbcast-short-full512-ab}"
BASE_PORT="${BASE_PORT:-19020}"
MAX_TOKENS="${MAX_TOKENS:-512}"
CANARY_REPEATS="${CANARY_REPEATS:-32}"
REALISTIC_METRIC_TOKENS="${REALISTIC_METRIC_TOKENS:-100}"
READINESS_TIMEOUT_S="${READINESS_TIMEOUT_S:-900}"

run_guard() {
  local variant="$1"
  local wave="$2"
  local base_port="$3"
  local lane_specs="$4"
  local enable_candidate="$5"
  local run_stamp="${STAMP}-${wave}-${variant}"

  echo "[gemma4-kqregbcast-short-ab] variant=$variant wave=$wave lanes=$lane_specs"
  (
    export GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8
    if [[ "$enable_candidate" == "1" ]]; then
      export GGML_SYCL_FATTN_DV512_GQA8_KQ_REG_BCAST=1
    else
      unset GGML_SYCL_FATTN_DV512_GQA8_KQ_REG_BCAST
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

run_pair "$wave_a" "$BASE_PORT" "$((BASE_PORT + 20))" \
  '0:1024:1024:control-gpu0 2:1024:1024:control-gpu2' \
  '1:1024:1024:kqregbcast-gpu1 3:1024:1024:kqregbcast-gpu3'

run_pair "$wave_b" "$((BASE_PORT + 40))" "$((BASE_PORT + 60))" \
  '1:1024:1024:control-gpu1 3:1024:1024:control-gpu3' \
  '0:1024:1024:kqregbcast-gpu0 2:1024:1024:kqregbcast-gpu2'

analysis_json="$ROOT/data/gemma4-kqregbcast-short-full512-ab-${STAMP}.json"
analysis_md="$ROOT/data/gemma4-kqregbcast-short-full512-ab-${STAMP}.md"

"$ROOT/scripts/analyze-gemma-realistic-ab.py" \
  --control "$(summary_for 0 control-gpu0 "${STAMP}-${wave_a}-control")" \
  --control "$(summary_for 2 control-gpu2 "${STAMP}-${wave_a}-control")" \
  --control "$(summary_for 1 control-gpu1 "${STAMP}-${wave_b}-control")" \
  --control "$(summary_for 3 control-gpu3 "${STAMP}-${wave_b}-control")" \
  --candidate "$(summary_for 1 kqregbcast-gpu1 "${STAMP}-${wave_a}-candidate")" \
  --candidate "$(summary_for 3 kqregbcast-gpu3 "${STAMP}-${wave_a}-candidate")" \
  --candidate "$(summary_for 0 kqregbcast-gpu0 "${STAMP}-${wave_b}-candidate")" \
  --candidate "$(summary_for 2 kqregbcast-gpu2 "${STAMP}-${wave_b}-candidate")" \
  --out "$analysis_json" \
  --markdown-out "$analysis_md"

echo "[gemma4-kqregbcast-short-ab] analysis_json=$analysis_json"
echo "[gemma4-kqregbcast-short-ab] analysis_md=$analysis_md"
