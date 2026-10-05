#!/usr/bin/env bash
# Second self-editing comparison (notes/2026-10-05-self-editing-first-comparison.md, "Second comparison").
# Run by the campaign's serve_run mode, which sets API_BASE, MODEL_NAME and OUT_DIR (like first-comparison.sh).
#
# Tasks (fixed absolute input sizes, served-model tokens; one `next` batch is ~6.4K tokens):
#   ledger  running ledger of ~160 counters (SET/ADD/DEL + a 16-word memo of noise per line);
#           the final item asks for 24 current values. Small state, constant surgical updates.
#   kv      key-value stream (100 SETs of 24-word values per batch); 24 GETs at the end.
#           Anything may be asked, so nothing can be dropped without risk.
# Storage modes: memory = stream data only in the model's context (enforced by `next`, audited by
#   the grader: a file holding stream data voids the run); notes = files allowed.
# Arms:
#   A     no management, no budget (whole task in the 262K window), memory-only  = lossless baseline
#   B32   self-editing (CLM agent), budget 32,768, memory-only
#   B131  self-editing, budget 131,072, memory-only    (only where the task is >= 0.8 x budget)
#   C32   summary at 75 %, budget 32,768, memory-only
#   C131  summary at 75 %, budget 131,072, memory-only (only where the task is >= 0.8 x budget)
#   D32   self-editing, budget 32,768, notes allowed
#   E32   no management, budget 32,768, notes allowed
# Every trial is its own Harbor job "<arm>__<task>" under $OUT_DIR/runs/jobs (finished jobs are
# skipped on a re-run). Caps are derived from the task (run-context-job.sh) and summarize_results.py
# --check marks any trial that a cap, a timeout or the storage rule ended; the script then exits 1.
#
# Environment:
#   API_BASE MODEL_NAME OUT_DIR (required unless STUB=1)
#   SUBSET    full [default] (~20 h) | core (~3 h) | quick (~1 h)   -- see the note for what each keeps
#   KINDS SIZES SEEDS ARMS   override the subset's lists (e.g. SIZES="120000" ARMS="A B32")
#   MAX_TOKENS [16384]  TEMPERATURE [0]  ENABLE_THINKING [true]  TASK_TEMPLATE [open_problems]
#   DRY_RUN=1  print the plan and the time estimate only
#   STUB=1     wiring test against fake_openai_server.py: tiny tasks (SIZES 4000 9000), all arms
#              forced, plus two rule probes (a storing agent must be VOID, an inline one must not)
set -uo pipefail
D=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PY=${VENV:-/mnt/fast-ai/venvs/clm}/bin/python
O=${OUT_DIR:?set OUT_DIR}
mkdir -p "$O"; O=$(cd "$O" && pwd)
export MAX_TOKENS=${MAX_TOKENS:-16384} TEMPERATURE=${TEMPERATURE:-0} ENABLE_THINKING=${ENABLE_THINKING:-true}
export TASK_TEMPLATE=${TASK_TEMPLATE:-open_problems}
SUBSET=${SUBSET:-full}
FORCE=0
STUB_PID=
cleanup() { [[ -n "$STUB_PID" ]] && kill "$STUB_PID" 2>/dev/null && echo "stub $STUB_PID stopped"; true; }
trap cleanup EXIT
if [[ "${STUB:-0}" == 1 ]]; then
  SIZES=${SIZES:-4000 9000}; SEEDS=${SEEDS:-0}; FORCE=1
  PORT=$("$PY" -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1])')
  "$PY" "$D/fake_openai_server.py" "$PORT" > "$O/stub.log" 2>&1 &
  STUB_PID=$!
  for _ in $(seq 50); do curl -sf "http://127.0.0.1:$PORT/v1/models" >/dev/null && break; sleep 0.1; done
  export API_BASE="http://127.0.0.1:$PORT/v1"
  echo "stub pid $STUB_PID at $API_BASE"
fi
: "${API_BASE:?set API_BASE}"
export API_BASE MODEL_NAME=${MODEL_NAME:-qwen38-27b-fp8}

case "$SUBSET" in
  full)  K=${KINDS:-ledger kv}; Z=${SIZES:-60000 120000 180000}; S=${SEEDS:-0 1}; A=${ARMS:-A B32 B131 C32 C131 D32 E32} ;;
  core)  K=${KINDS:-ledger kv}; Z=${SIZES:-120000};              S=${SEEDS:-0 1}; A=${ARMS:-A B32 C32 D32 E32} ;;
  quick) K=${KINDS:-ledger kv}; Z=${SIZES:-60000};               S=${SEEDS:-0};   A=${ARMS:-A B32 C32 D32 E32} ;;
  *) echo "SUBSET must be full|core|quick" >&2; exit 2 ;;
esac
# core runs seed 1 only for the ledger (the central question); kv gets seed 0.
CORE_KV_SEEDS=${CORE_KV_SEEDS:-0}

# ---- tasks (generated once; same task dirs for every arm)
T="$O/tasks"; mkdir -p "$T"
for kind in $K; do
  for mode in memory notes; do
    dir="$T/$kind-$mode"
    [[ -d "$dir" ]] && continue
    gen=$([[ $kind == kv ]] && echo make_kvstream_tasks.py || echo make_ledger_tasks.py)
    # shellcheck disable=SC2086
    "$PY" "$D/$gen" "$dir" --tokens $Z --seeds $S --mode "$mode" > "$dir.gen.json" || { echo "task generation failed"; exit 1; }
  done
done

# ---- plan + estimate
PLAN=$("$PY" - "$T" "$SUBSET" "$FORCE" "$CORE_KV_SEEDS" "$K" "$Z" "$S" "$A" <<'PY'
import sys, tomllib, pathlib
T, subset, force, core_kv_seeds = pathlib.Path(sys.argv[1]), sys.argv[2], sys.argv[3] == "1", sys.argv[4].split()
kinds, sizes, seeds, arms = (x.split() for x in sys.argv[5:9])
ARMS = {"A": ("plain", "memory", 0), "B32": ("clm", "memory", 32768), "B131": ("clm", "memory", 131072),
        "C32": ("summary", "memory", 32768), "C131": ("summary", "memory", 131072),
        "D32": ("clm", "notes", 32768), "E32": ("plain", "notes", 32768)}
R, W = 3000.0, 75.0          # prompt reading tok/s without prefix caching, writing tok/s
def est(arm, size, items):
    agent, mode, budget = ARMS[arm]
    over, out1 = 4000, 600
    if budget == 0:
        calls, p, ctx = items + 6, 0.0, over
        for _ in range(items):
            p += ctx; ctx += size / max(items - 1, 1) + out1
        return p + 6 * ctx, calls * out1 + 2500
    L = budget - 2048
    if mode == "notes":
        calls = items + 8
        return calls * 12000.0, calls * 350.0
    if agent == "clm":
        calls = 2 * items + 6
        return calls * min(0.65 * L, size / 2 + over), calls * out1 + items * 1500
    n_sum = max(0, int(size / (0.75 * L - over - 3000)))
    calls = items + 6 + n_sum
    return calls * min(0.5 * L + over, size / 2 + over) + n_sum * 0.8 * L, calls * out1 + n_sum * 6000
tot = 0.0
for seed in seeds:
    for size in sizes:
        for kind in kinds:
            if subset == "core" and kind == "kv" and seed not in core_kv_seeds:
                continue
            for arm in arms:
                agent, mode, budget = ARMS[arm]
                name = f"{kind}-{mode}-t{int(size)//1000}k-s{seed}"
                td = T / f"{kind}-{mode}" / name
                md = tomllib.loads((td / "task.toml").read_text())["metadata"]
                if budget and not force and md["stream_tokens"] < 0.8 * budget:
                    print(f"#skip\t{arm}\t{name}\tno pressure: {md['stream_tokens']} tokens < 0.8 x {budget}")
                    continue
                p, o = est(arm, md["stream_tokens"], md["n_items"])
                s = p / R + o / W
                tot += s
                print(f"{arm}\t{agent}\t{budget}\t{td}\t{name}\t{md['stream_tokens']}\t{md['n_items']}\t{p:.0f}\t{o:.0f}\t{s:.0f}")
print(f"#total\t{tot:.0f}")
PY
) || { echo "planning failed"; exit 1; }
echo "== plan (SUBSET=$SUBSET; estimate at 3,000 tok/s reading without prefix caching, 75 tok/s writing)"
echo "$PLAN" | awk -F'\t' '$1=="#skip"{print "  skip " $2 " " $3 " (" $4 ")"; next}
  $1=="#total"{printf "  estimated total: %.1f h (writing at 60-90 tok/s moves this by about -10/+15 %%; reading above ~150K\n  context is slower than 3,000 tok/s, so the 180K cells are optimistic)\n", $2/3600; next}
  {printf "  %-5s %-7s budget %-6s %-24s %7s tok %3s items  ~%4.1fM read ~%3.0fk written ~%3.0f min\n", $1,$2,$3,$5,$6,$7,$8/1e6,$9/1e3,$10/60}'
[[ "${DRY_RUN:-0}" == 1 ]] && exit 0

# ---- window check for the no-budget arm
"$PY" - "$API_BASE" "$MODEL_NAME" "$MAX_TOKENS" "$(echo "$PLAN" | awk -F'\t' '$1=="A"{print $6}' | sort -n | tail -1)" <<'PY' || exit 1
import json, sys, urllib.request
base, name, mx, big = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4] or 0)
d = json.load(urllib.request.urlopen(base.rstrip("/") + "/models", timeout=10))
win = {m.get("id"): m.get("max_model_len") for m in d.get("data", [])}.get(name)
need = big + 40000 + mx   # stream + prompts/thinking/answers headroom + one reply
print(f"window {win}; arm A needs about {need} at its largest task")
if big and win and need > int(win):
    sys.exit(f"server window {win} is too small for arm A at {big} tokens (needs ~{need}); "
             "raise --max-model-len or drop that size")
PY

RUNS="$O/runs"; mkdir -p "$RUNS"
FAILED=0
run_one() {  # arm agent budget task_dir job_name
  local arm=$1 agent=$2 budget=$3 td=$4 job=$5
  if compgen -G "$RUNS/jobs/$job/*/verifier/reward.txt" >/dev/null; then
    echo "== $job: done earlier, skipped"; return 0
  fi
  rm -rf "${RUNS:?}/jobs/$job"
  echo "== $(date +%H:%M:%S) $job (agent=$agent budget=$budget)"
  TASKS="$td" JOB_NAME="$job" CONTEXT_BUDGET="$budget" "$D/run-context-job.sh" "$agent" "$RUNS" > "$RUNS/$job.out" 2>&1
  echo "   rc=$? $(grep -h -o '[a-z]* score [0-9.]* raw [0-9.]*.*void=[A-Za-z]*' "$RUNS/jobs/$job"/*/verifier/test-stdout.txt 2>/dev/null | head -1)"
  if ! "$PY" "$D/summarize_results.py" --brief --check "$RUNS/jobs/$job" > "$RUNS/$job.check" 2>&1; then
    echo "!!! $job: a cap, timeout, server refusal or the storage rule ended this run; it does not count:"
    grep '^!!!' "$RUNS/$job.check" | sed 's/^/    /'
    FAILED=1
  fi
}
while IFS=$'\t' read -r arm agent budget td name _rest; do
  [[ -z "$arm" || "$arm" == \#* ]] && continue
  run_one "$arm" "$agent" "$budget" "$td" "${arm}__${name}"
done <<< "$PLAN"

if [[ "${STUB:-0}" == 1 ]]; then   # storage-rule probes (memory mode, no budget, plain agent)
  API_PORT=${API_BASE##*:}; API_PORT=${API_PORT%%/*}
  for kind in $K; do
    td=$(ls -d "$T/$kind-memory"/*-s0 | head -1)
    for plan in violate inline; do
      kill "$STUB_PID" 2>/dev/null; wait "$STUB_PID" 2>/dev/null
      FAKE_PLAN=$plan "$PY" "$D/fake_openai_server.py" "$API_PORT" > "$O/stub-$plan.log" 2>&1 &
      STUB_PID=$!
      for _ in $(seq 50); do curl -sf "$API_BASE/models" >/dev/null && break; sleep 0.1; done
      job="PROBE-${plan}__$(basename "$td")"
      rm -rf "${RUNS:?}/jobs/$job"
      TASKS="$td" JOB_NAME="$job" CONTEXT_BUDGET=0 "$D/run-context-job.sh" plain "$RUNS" > "$RUNS/$job.out" 2>&1
      v=$("$PY" -c "import json,glob; d=json.load(open(glob.glob('$RUNS/jobs/$job/*/verifier/details.json')[0])); print(d['void'], d['delivery']['refused'], d['violations'])" 2>&1)
      echo "== rule probe $plan on $(basename "$td"): void refused violations = $v"
      case "$plan" in
        violate) [[ "$v" == True\ [1-9]* ]] || { echo "!!! probe violate: expected VOID and a refused next"; FAILED=1; } ;;
        inline)  [[ "$v" == False\ 0* ]] || { echo "!!! probe inline: expected no violation"; FAILED=1; } ;;
      esac
    done
  done
fi

echo; echo "== table (all trials of this comparison)"
"$PY" "$D/summarize_results.py" --json "$O/summary.json" "$RUNS"/jobs/[A-E]* | tee "$O/summary.txt"
[[ $FAILED == 0 ]] || { echo "!!! at least one trial was ended by a cap/timeout/rule; see the lines above"; exit 1; }
