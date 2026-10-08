#!/usr/bin/env bash
# LongMemEval retention study driver (notes/2026-10-07-longmemeval-retention-prereg.md).
# One arm per call; one Harbor job per built task ("<arm>__<task>"), via run-context-job.sh (agent arms) or
# longmemeval_direct.py (arm F). Same conventions as second-comparison.sh: finished jobs are skipped, a STOP
# file in OUT_DIR stops before the next trial, summarize_results.py --check flags cap/timeout/void trials.
#
#   longmemeval-run.sh ARM        ARM = B32ira-free | C32 | Ar | E32r | F
#
# Arms (tasks from make_longmemeval_tasks.py; memory tasks except E32r):
#   B32ira-free  improved agent, read mode + archive/recall, FREE-TEXT notes (clm_freenotes.ClmFreeNotesAgent,
#                STATE.txt capped at STATE_MAX_TOKENS [6144], `ctxfold --drop` forced), budget 32,768,
#                THINKING_POLICY=judgement, THINK_CAP 4096 (THINK_CAP_R) as B32ira
#   C32          summary agent at 75 % of a 32,768 budget
#   Ar           plain agent, keep everything, SHOW_WINDOW=1 (262,144 window; checked against /v1/models)
#   E32r         plain agent, files allowed (notes tasks), budget 32,768
#   F            one call with the whole history + question (official reader prompt); needs prompt
#                (~103-112K tokens) + MAX_TOKENS within the server window, else written as skipped:window
#
# Environment:
#   API_BASE MODEL_NAME OUT_DIR (required)   TASKS_ROOT [/mnt/fast-ai/datasets/longmemeval/tasks-s8-seed0]
#   QIDS="id id ..."  only these question ids;  PILOT=1  first id of each stratum in selection.json (7 tasks)
#   MAX_TOKENS [16384] TEMPERATURE [0] ENABLE_THINKING [true] TASK_TEMPLATE [open_problems]
#   STATE_MAX_TOKENS [6144]  THINK_CAP_R [4096]  DRY_RUN=1 prints the plan only
# Output: $OUT_DIR/runs/jobs/<arm>__<task>/..., $OUT_DIR/runs/<job>.{out,check,arm.txt,wall}
#         $OUT_DIR/summary-<arm>.txt (longmemeval_summary.py over all jobs in OUT_DIR)
# Judging afterwards (owner's choice of judge): longmemeval_judge.py $OUT_DIR/runs/jobs --out verdicts.jsonl
set -uo pipefail
D=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PY=${VENV:-/mnt/fast-ai/venvs/clm}/bin/python
ARM=${1:?usage: longmemeval-run.sh B32ira-free|C32|Ar|E32r|F}
O=${OUT_DIR:?set OUT_DIR}
mkdir -p "$O"; O=$(cd "$O" && pwd)
ROOT=${TASKS_ROOT:-/mnt/fast-ai/datasets/longmemeval/tasks-s8-seed0}
export MAX_TOKENS=${MAX_TOKENS:-16384} TEMPERATURE=${TEMPERATURE:-0} ENABLE_THINKING=${ENABLE_THINKING:-true}
export TASK_TEMPLATE=${TASK_TEMPLATE:-open_problems}
[[ "${DRY_RUN:-0}" == 1 ]] || : "${API_BASE:?set API_BASE}" "${MODEL_NAME:?set MODEL_NAME}"

mode=memory; [[ "$ARM" == E32r ]] && mode=notes
case "$ARM" in
  B32ira-free) agent=improved; budget=32768 ;;
  C32)         agent=summary;  budget=32768 ;;
  Ar)          agent=plain;    budget=0 ;;
  E32r)        agent=plain;    budget=32768 ;;
  F)           agent=direct;   budget=0 ;;
  *) echo "unknown arm $ARM (B32ira-free|C32|Ar|E32r|F)"; exit 2 ;;
esac
TD="$ROOT/lme-$mode"
[[ -d "$TD" ]] || { echo "no tasks at $TD (make_longmemeval_tasks.py build $TD --subset 8 --seed 0 --mode $mode --exact-tokens)"; exit 2; }

# task list: all, QIDS, or PILOT (first id per stratum in selection.json order)
mapfile -t TASKS < <("$PY" - "$TD" "${QIDS:-}" "${PILOT:-0}" <<'PY'
import json, sys, pathlib
td, qids, pilot = pathlib.Path(sys.argv[1]), sys.argv[2].split(), sys.argv[3] == "1"
sel = json.loads((td / "selection.json").read_text())
rows = sel["tasks"]
if qids:
    rows = [r for r in rows if r["question_id"] in set(qids)]
elif pilot:
    seen, keep = set(), []
    for r in rows:
        s = "abstention" if r["abstention"] else r["type"]
        if s not in seen:
            seen.add(s); keep.append(r)
    rows = keep
for r in rows:
    print(td / r["name"])
PY
)
echo "== arm $ARM ($agent, budget $budget, $mode tasks): ${#TASKS[@]} task(s) under $TD"
[[ "${DRY_RUN:-0}" == 1 ]] && { printf '  %s\n' "${TASKS[@]##*/}"; exit 0; }

RUNS="$O/runs"; mkdir -p "$RUNS/jobs"
FAILED=0
for td in "${TASKS[@]}"; do
  [[ -e "$O/STOP" ]] && { echo "stopped by STOP file"; break; }
  job="${ARM}__$(basename "$td")"
  if compgen -G "$RUNS/jobs/$job/*/verifier/reward.txt" >/dev/null; then
    echo "== $job: done earlier, skipped"; continue
  fi
  rm -rf "${RUNS:?}/jobs/$job"
  echo "== $(date +%H:%M:%S) $job"
  t0=$(date +%s)
  if [[ "$ARM" == F ]]; then
    "$PY" "$D/longmemeval_direct.py" --task "$td" --job-dir "$RUNS/jobs/$job" > "$RUNS/$job.out" 2>&1
    echo "   rc=$? $(tail -1 "$RUNS/$job.out")"
    grep -q '"status": "ok"' "$RUNS/$job.out" || { echo "!!! $job: not a valid trial (see $RUNS/$job.out)"; FAILED=1; }
  else
    xa=(); extra=""
    tp=${THINKING_POLICY:-}; tc=${THINK_CAP:-}; fm=${FOLD_MODE:-}; ar=0; sw=0
    if [[ "$ARM" == B32ira-free ]]; then
      fm=read; ar=1; tp=judgement; tc=${THINK_CAP_R:-4096}
      extra="state_max_tokens=${STATE_MAX_TOKENS:-6144}"
      xa=(-a clm_freenotes:ClmFreeNotesAgent)    # harbor: the last --agent wins; run-context-job.sh passes "$@" last
    fi
    [[ "$ARM" == Ar ]] && sw=1
    echo "arm=$ARM agent_class=${xa[1]:-run-context-job.sh default for $agent} extra_kwargs=$extra" > "$RUNS/$job.arm.txt"
    TASKS="$td" JOB_NAME="$job" CONTEXT_BUDGET="$budget" THINK_CAP="$tc" THINKING_POLICY="$tp" \
      FOLD_MODE="$fm" ARCHIVE="$ar" SHOW_WINDOW="$sw" EXTRA_KWARGS="${EXTRA_KWARGS:-} $extra" \
      "$D/run-context-job.sh" "$agent" "$RUNS" "${xa[@]}" > "$RUNS/$job.out" 2>&1
    echo "   rc=$? $(grep -h -o 'longmemeval score [0-9.]* raw [0-9.]*.*void=[A-Za-z]*' "$RUNS/jobs/$job"/*/verifier/test-stdout.txt 2>/dev/null | head -1)"
    if ! "$PY" "$D/summarize_results.py" --brief --check "$RUNS/jobs/$job" > "$RUNS/$job.check" 2>&1; then
      echo "!!! $job: a cap, timeout, server refusal or the storage rule ended this run; it does not count:"
      grep '^!!!' "$RUNS/$job.check" | sed 's/^/    /'
      FAILED=1
    fi
  fi
  echo $(( $(date +%s) - t0 )) > "$RUNS/$job.wall"
  compgen -G "$RUNS/jobs/$job/*/verifier/judge_pair.json" >/dev/null || { echo "!!! $job: no judge_pair.json"; FAILED=1; }
done

echo; echo "== LongMemEval table (all arms in $O; deterministic until judged)"
"$PY" "$D/longmemeval_summary.py" "$RUNS/jobs" --json "$O/summary-$ARM.json" | tee "$O/summary-$ARM.txt"
[[ $FAILED == 0 ]] || { echo "!!! at least one trial did not count; see above"; exit 1; }
