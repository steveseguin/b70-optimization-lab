#!/usr/bin/env bash
# Calibrate the sparse-prose reading task in single calls before any long agent run.
# Client for the serve_run wrapper: API_BASE (or BASE_URL), MODEL_NAME, OUT_DIR from the environment.
#
# Grid: density 3 / 6 / 12 real changes per 2K-token batch  x  plain | words | pronouns | corrections |
# plans | all (all = the four plus relative amounts), 12 batches each (make_sparse_prose_tasks.py),
# probed with thinking OFF in two output styles: values only (plain) and one short reason per changed
# counter (reason). Each call gets the TRUE previous state, so errors do not compound.
# Target for the long run: the hardest setting with changed-counter accuracy >= 98 % AND full-table
# accuracy >= 99.5 %. The last lines print that setting as SPARSE_ARGS for reading-run.sh.
#   DENSITIES ["3 6 12"]  SETTINGS ["plain words pronouns corrections plans all"]  BATCHES [12]
#   VARIANTS [both]  DRY_RUN=1 (estimate only)
set -uo pipefail
D=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
API_BASE=${API_BASE:-${BASE_URL:-}}
[[ -n "$API_BASE" && "$API_BASE" != */v1 ]] && API_BASE="${API_BASE%/}/v1"
export API_BASE MODEL_NAME=${MODEL_NAME:-qwen38-27b-fp8}
O=${OUT_DIR:?set OUT_DIR}; mkdir -p "$O"; O=$(cd "$O" && pwd)
DENS=${DENSITIES:-3 6 12}; SETS=${SETTINGS:-plain words pronouns corrections plans all}; NB=${BATCHES:-12}
TASKS=(); mkdir -p "$O/grid"
for d in $DENS; do
  for s in $SETS; do
    dir="$O/grid/d${d}-${s}"
    flag=; [[ $s != plain ]] && flag="--$s"
    [[ -d "$dir" ]] || python3 "$D/make_sparse_prose_tasks.py" "$dir" --n-batches "$NB" --density "$d" $flag \
        --seeds 0 --batch-tokens 2000 > "$dir.gen.json" || { echo "generation failed: $dir"; exit 1; }
    TASKS+=("$dir/sparse-memory-b${NB}-s0")
  done
done
python3 "$D/prose_fold_probe.py" "${TASKS[@]}" --thinking off --variant "${VARIANTS:-both}" --dry-run
[[ "${DRY_RUN:-0}" == 1 ]] && exit 0
: "${API_BASE:?set API_BASE}"
python3 "$D/prose_fold_probe.py" "${TASKS[@]}" --thinking off --variant "${VARIANTS:-both}" --sweep \
  --save "$O/replies" | tee "$O/calibration.log"
python3 "$D/calib_table.py" "$O/calibration.log" | tee "$O/calibration-table.txt"
