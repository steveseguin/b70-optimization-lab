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
#   B32ik B131ik  the same with a per-turn thinking cap (THINK_CAP_K, default 8192 tokens)
#   B32in  improved agent, thinking OFF on routine fetch/fold calls, ON where judgement is needed
#          (clm_improved.ClmImprovedAgent._wants_thinking); B32io: thinking off on every call
#   E32o   no management, files allowed, thinking off on every call
#   B32ir  improved agent for prose: reads each report itself (FOLD_MODE=read, STATE.txt "name value" /
#          "name removed" lines, `ctxfold --drop` checks every mentioned name has a line), thinking off on
#          routine batches (judgement), cap THINK_CAP_R (4096) when on; READ_REASONS=1 adds reason lines
#   Ar     keep everything + SHOW_WINDOW (reading-task baseline);  E32r: files allowed, plain
#   KINDS=sparse  sparse prose (make_sparse_prose_tasks.py), options from SPARSE_ARGS (e.g. "--density 6 --words")
#   PROSE_BATCH_TOKENS  prose batch size at generation [6400] (use a new OUT_DIR when changing it)
#   Aw     A + SHOW_WINDOW: every tool result states the window used/left, and a fetch that cannot
#          fit (context + largest item so far + max_tokens > window) is refused with a request to
#          write down what is needed first (keep-everything seed 1 ran into the window at ~246K)
#   (all improved arms render earlier turns stably: preserve_thinking=true with thinking stripped,
#    mirror edits keep unchanged turns byte-identical, rollback notices appended at the end;
#    STABLE_RENDER=1 gives the plain drop-thinking arms the same preserve_thinking=true)
#   B32i B131i  the improved self-editing agent (clm_improved.py: delivered items never rolled back,
#         room check before `next`, harness-owned pinned STATE.txt, old thinking dropped), memory-only
#   At B32t C32t E32t   the same arms with earlier thinking dropped from every call (DROP_OLD_THINKING=1:
#         preserve_thinking=false + earlier reasoning stripped from the history; see clm_baselines.py)
# Every trial is its own Harbor job "<arm>__<task>" under $OUT_DIR/runs/jobs (finished jobs are
# skipped on a re-run). Caps are derived from the task (run-context-job.sh) and summarize_results.py
# --check marks any trial that a cap, a timeout or the storage rule ended; the script then exits 1.
#
# Environment:
#   API_BASE MODEL_NAME OUT_DIR (required unless STUB=1)
#   SUBSET    full [default] (~20 h) | core (~5 h) | quick (~1 h)   -- see the note for what each keeps
#   KINDS SIZES SEEDS ARMS   override the subset's lists (e.g. SIZES="120000" ARMS="A B32"). An explicit ARMS
#             runs arm by arm in exactly that order (all seeds/sizes/kinds of the first arm first).
#   THINK_CAP  per-turn thinking cap for the improved arms (tokens; default off)
#   STOP file  if "$OUT_DIR/STOP" exists before a trial, the script prints "stopped by STOP file" and exits 0
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
  full)  K=${KINDS:-ledger kv}; Z=${SIZES:-60000 120000 180000}; S=${SEEDS:-0 1}; A=${ARMS:-A B32 B131 C32 C131 D32 E32 At B32t C32t E32t} ;;
  core)  K=${KINDS:-ledger kv}; Z=${SIZES:-120000};              S=${SEEDS:-0 1}; A=${ARMS:-A B32 C32 D32 E32 At B32t E32t} ;;
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
    xa=; [[ $kind == prose ]] && gen=make_prose_ledger_tasks.py && xa="--exact-tokens --batch-tokens ${PROSE_BATCH_TOKENS:-6400}"   # KINDS=prose
    [[ $kind == sparse ]] && gen=make_sparse_prose_tasks.py && xa="--exact-tokens ${SPARSE_ARGS:-}"   # KINDS=sparse
    # shellcheck disable=SC2086
    "$PY" "$D/$gen" "$dir" --tokens $Z --seeds $S --mode "$mode" $xa > "$dir.gen.json" || { echo "task generation failed"; exit 1; }
  done
done

# graders of tasks generated before 2026-10-05 22:00 lack the STATE.txt exclusion (clm_improved);
# rewrite tests/grade.py only (the stream and expected answers are untouched)
"$PY" "$D/make_kvstream_tasks.py" "$T" --refresh-graders || { echo "grader refresh failed"; exit 1; }

# ---- plan + estimate
PLAN=$("$PY" - "$T" "$SUBSET" "$FORCE" "$CORE_KV_SEEDS" "$K" "$Z" "$S" "$A" "${ARMS:+explicit}" <<'PY'
import sys, tomllib, pathlib
T, subset, force, core_kv_seeds = pathlib.Path(sys.argv[1]), sys.argv[2], sys.argv[3] == "1", sys.argv[4].split()
kinds, sizes, seeds, arms = (x.split() for x in sys.argv[5:9])
explicit = len(sys.argv) > 9 and sys.argv[9] == "explicit"
ARMS = {"A": ("plain", "memory", 0), "B32": ("clm", "memory", 32768), "B131": ("clm", "memory", 131072),
        "C32": ("summary", "memory", 32768), "C131": ("summary", "memory", 131072),
        "D32": ("clm", "notes", 32768), "E32": ("plain", "notes", 32768),
        "B32i": ("improved", "memory", 32768), "B131i": ("improved", "memory", 131072),
        "B32ik": ("improved", "memory", 32768), "B131ik": ("improved", "memory", 131072),
        "B32in": ("improved", "memory", 32768), "B32io": ("improved", "memory", 32768),
        "E32o": ("plain", "notes", 32768), "Aw": ("plain", "memory", 0),
        "B32ir": ("improved", "memory", 32768), "Ar": ("plain", "memory", 0), "E32r": ("plain", "notes", 32768)}
for a in ("A", "B32", "C32", "E32"):  # same arm with earlier thinking dropped from every call
    ARMS[a + "t"] = ARMS[a]
bad = [a for a in arms if a not in ARMS]
if bad:
    sys.exit(f"unknown arm(s) {bad}; known: {sorted(ARMS)}")
# Measured 2026-10-05 (prefix cache on): ~3,300 written tokens per call, writing ~90 tok/s under
# 30K context falling to ~41 tok/s at 137K, reading only the new (uncached) prompt tokens at
# ~2,000 tok/s. Self-editing/summary arms re-read ~70 % of their context per call (edits near the
# top defeat the cache; B32 got 29 % cached).
OUT, RNEW = 3300.0, 2000.0
def wspeed(ctx):
    return max(41.0, min(90.0, 90.0 - (ctx - 30000.0) * 49.0 / 107000.0))
def est(arm, size, items):
    agent, mode, budget = ARMS[arm]
    item = size / max(items - 1, 1)
    calls, read, sec, out = 0, 0.0, 0.0, 0.0
    def call(ctx, new, o=OUT):
        nonlocal calls, read, sec, out
        calls += 1; read += new; out += o; sec += new / RNEW + o / wspeed(ctx)
    if budget == 0 and mode == "memory":                    # A, At: everything stays
        for i in range(items + 8):
            call(4000 + min(i, items) * (item + 1000), item + OUT)
    elif mode == "notes":                                   # D32, E32: data goes to files
        for _ in range(items + 8):
            call(12000, 3000 + OUT)
    else:
        L = budget - 2048
        ctx = min(0.6 * L, size / 2 + 4000)
        n = (2 * items + 8) if agent in ("clm", "improved") else (items + 8)
        for _ in range(n):
            call(ctx, 0.7 * ctx)
        if agent == "summary":
            for _ in range(max(0, int(size / (0.75 * L - 7000)))):
                call(0.75 * L, 0.75 * L, 6000)
    return read, out, sec
tot = 0.0
def cells():
    if explicit:
        for arm in arms:
            for seed in seeds:
                for size in sizes:
                    for kind in kinds:
                        yield seed, size, kind, arm
    else:
        for seed in seeds:
            for size in sizes:
                for kind in kinds:
                    for arm in arms:
                        yield seed, size, kind, arm
for seed, size, kind, arm in cells():
    if subset == "core" and kind == "kv" and seed not in core_kv_seeds and not explicit:
        continue
    agent, mode, budget = ARMS[arm]
    name = f"{kind}-{mode}-t{int(size)//1000}k-s{seed}"
    td = T / f"{kind}-{mode}" / name
    md = tomllib.loads((td / "task.toml").read_text())["metadata"]
    if budget and not force and md["stream_tokens"] < 0.8 * budget:
        print(f"#skip\t{arm}\t{name}\tno pressure: {md['stream_tokens']} tokens < 0.8 x {budget}")
        continue
    p, o, s = est(arm, md["stream_tokens"], md["n_items"])
    tot += s
    print(f"{arm}\t{agent}\t{budget}\t{td}\t{name}\t{md['stream_tokens']}\t{md['n_items']}\t{p:.0f}\t{o:.0f}\t{s:.0f}\t{int(arm.endswith('t'))}")
print(f"#total\t{tot:.0f}")
PY
) || { echo "planning failed"; exit 1; }
echo "== plan (SUBSET=$SUBSET${ARMS:+, arms in the given order: $ARMS}; estimate from the 2026-10-05 measurements, prefix cache on)"
echo "$PLAN" | awk -F'\t' '$1=="#skip"{print "  skip " $2 " " $3 " (" $4 ")"; next}
  $1=="#total"{printf "  estimated total: %.1f h (3,300 written tokens/call at 90->41 tok/s by context, new prompt tokens at\n  2,000 tok/s; B32 took 1.9x its estimate on 2026-10-05 because of a thinking/rollback thrash)\n", $2/3600; next}
  {printf "  %-6s %-8s budget %-6s %-24s %7s tok %3s items  ~%4.2fM new read ~%3.0fk written ~%3.0f min\n", $1,$2,$3,$5,$6,$7,$8/1e6,$9/1e3,$10/60}'
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
run_one() {  # arm agent budget task_dir job_name drop_old_thinking
  local arm=$1 agent=$2 budget=$3 td=$4 job=$5 drop=${6:-0}
  if compgen -G "$RUNS/jobs/$job/*/verifier/reward.txt" >/dev/null; then
    echo "== $job: done earlier, skipped"; return 0
  fi
  rm -rf "${RUNS:?}/jobs/$job"
  echo "== $(date +%H:%M:%S) $job (agent=$agent budget=$budget drop_old_thinking=$drop)"
  local tc=${THINK_CAP:-} et=$ENABLE_THINKING tp=${THINKING_POLICY:-}
  [[ "$arm" == *ik ]] && tc=${THINK_CAP_K:-8192}   # B32ik/B131ik: improved agent + per-turn thinking cap
  [[ "$arm" == *in ]] && tp=judgement              # B32in: thinking only where judgement is needed
  [[ "$arm" == *io ]] && tp=never                  # B32io: improved agent, thinking off on every call
  [[ "$arm" == E32o ]] && et=false                 # E32o: plain, files allowed, thinking off
  local sw=0; [[ "$arm" == Aw ]] && sw=1           # Aw: A + window line and fetch guard
  local fm=${FOLD_MODE:-}
  [[ "$arm" == B32ir ]] && fm=read && tp=judgement && tc=${THINK_CAP_R:-4096}   # B32ir: reads prose itself
  [[ "$arm" == Ar ]] && sw=1                       # Ar: keep everything + window line (reading task baseline)
  TASKS="$td" JOB_NAME="$job" CONTEXT_BUDGET="$budget" DROP_OLD_THINKING="$drop" THINK_CAP="$tc" ENABLE_THINKING="$et" THINKING_POLICY="$tp" SHOW_WINDOW="$sw" FOLD_MODE="$fm" "$D/run-context-job.sh" "$agent" "$RUNS" > "$RUNS/$job.out" 2>&1
  echo "   rc=$? $(grep -h -o '[a-z]* score [0-9.]* raw [0-9.]*.*void=[A-Za-z]*' "$RUNS/jobs/$job"/*/verifier/test-stdout.txt 2>/dev/null | head -1)"
  if ! "$PY" "$D/summarize_results.py" --brief --check "$RUNS/jobs/$job" > "$RUNS/$job.check" 2>&1; then
    echo "!!! $job: a cap, timeout, server refusal or the storage rule ended this run; it does not count:"
    grep '^!!!' "$RUNS/$job.check" | sed 's/^/    /'
    FAILED=1
  fi
}
while IFS=$'\t' read -r arm agent budget td name _tok _items _p _o _s drop; do
  [[ -z "$arm" || "$arm" == \#* ]] && continue
  if [[ -e "$O/STOP" ]]; then echo "stopped by STOP file"; exit 0; fi
  run_one "$arm" "$agent" "$budget" "$td" "${arm}__${name}" "$drop"
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
      if [[ -e "$O/STOP" ]]; then echo "stopped by STOP file"; exit 0; fi
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
