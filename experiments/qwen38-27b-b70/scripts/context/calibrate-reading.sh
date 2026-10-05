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
  | tee "$O/calibration.log"
python3 - "$O/calibration.log" <<'PY'
import re, sys
rows = []
for ln in open(sys.argv[1]):
    m = re.search(r"/d([\d.]+)-(\w+)/\S+\tsetting=\S+\tdensity=\S+\tthinking=\w+\tvariant=(\w+)\tchanged_right=\d+/\d+ \(([\d.]+)%\)\tfull_table=([\d.]+)%", ln)
    if m and not ln.startswith("#"):
        rows.append((float(m.group(1)), m.group(2), m.group(3), float(m.group(4)), float(m.group(5))))
rows = sorted(set(rows))
order = {"plain": 0, "words": 1, "pronouns": 2, "corrections": 3, "plans": 4, "all": 5}
print("\n# calibration table (thinking off)")
print("density\tsetting\tvariant\tchanged_right%\tfull_table%\tpass(>=98 and >=99.5)")
for r in sorted(rows, key=lambda r: (r[0], order.get(r[1], 9), r[2])):
    print(f"{r[0]:g}\t{r[1]}\t{r[2]}\t{r[3]:.1f}\t{r[4]:.2f}\t{'PASS' if r[3] >= 98 and r[4] >= 99.5 else '-'}")
ok = [r for r in rows if r[3] >= 98 and r[4] >= 99.5]
if ok:
    best = max(ok, key=lambda r: (order.get(r[1], 0), r[0], r[2] == "plain"))
    flag = "" if best[1] == "plain" else f" --{best[1]}"
    print(f"\n# hardest passing setting: density {best[0]:g}, {best[1]}, variant {best[2]}")
    print(f'SPARSE_ARGS="--density {best[0]:g}{flag}" READ_REASONS={1 if best[2] == "reason" else 0}')
else:
    print("\n# no setting passed: do not start the long run; make the steps easier (lower density, plain)")
PY
