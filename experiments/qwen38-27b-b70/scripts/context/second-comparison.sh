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
#   B32ira B32ir + archive-on-drop and `recall` (rule class "archive allowed"); FOLD_BATCHES=N for any
#          improved arm fetches/folds N items per command
#   B32iq  quoted events: B32ira, but the model never writes STATE.txt; per item it sends `name | op |
#          amount | "exact quote"` lines to `ctxfold --events`, which checks each quote is verbatim in the
#          item, checks the counters, does the arithmetic, archives and drops the item (QUOTED=1)
#   KINDS=sparse  sparse prose (make_sparse_prose_tasks.py), options from SPARSE_ARGS (e.g. "--density 6 --words")
#   PROSE_BATCH_TOKENS  prose batch size at generation [6400] (use a new OUT_DIR when changing it)
#   W16 D16 C16 B16ir B16ira B16ira-free   live-cap study at budget 16,384 (16K, fast scale; same arms as 48)
#   W32 P32                                 32K lossy floors (window-drop, compaction) beside B32ir / B32ira / C32
#   B32ira-free                             B32ira with free-text notes (clm_freenotes, cap STATE_MAX_TOKENS) instead of name-value lines
#   B32iraR                                 B32ira + permanent `RULE: ...` lines in STATE.txt for standing rules and methods (clm_rules)
#   B32iraR4                                B32iraR with FOLD_BATCHES=4 (fetch and fold four items per command)
#   B32iraRH                                B32iraR + a version history of the pinned state kept by the harness (clm_history):
#                                           `recall --state-at N NAME` answers "what did X hold at the end of item N"; own rule class
#   N32 N200                                the plain sliding-window agent (W) whose cut turns go to the archive, with NOTES (RULES /
#                                           STATE / OPEN) rewritten by one tool-less model call at each cut and `recall` (clm_keeper):
#                                           no per-item protocol, the policy a serving-side proxy could apply to any agent
#   N32j                                    N32 with thinking only where a question, refusal or error is in view; the notes call thinks
#   N32f                                    N32j whose notes call does not think and whose cut goes down to 50 % (fewer, cheaper notes calls)
#   N200j                                   N32j at the 200K cap
#   N64j                                    N32j at a 64K live window
#   N32j35                                  N32j cutting down to 35 % of the window instead of 60 % (about half as many notes calls)
#   N32d                                    N32j with changes-only notes: the notes call writes only the lines that changed, with the
#                                           working on the line and no thinking; the harness applies them and checks the sums (campaign 10)
#   N32dth                                  N32d with a notes call that thinks;  N32d35: N32d cutting down to 35 %
#   N32e N32e35 N32e25                      N32d after its first run (39/39, but 8 of 23 cuts fell back to the full rewrite): working may
#                                           start from a number the turns being cut state (a set followed by a change, written on one
#                                           line), and OPEN is at most three short lines; ..35 / ..25: the cut goes down to 35 / 25 %
#   N32c35 N32c25 N32c15                    N32e with the deeper cut noted in pieces of at most 11,000 tokens of turns (about six items),
#                                           one no-thinking call each: N32e35 lost 3 of 39 reading eleven items in one call
#   N32x N32x8                              N32e with in-place notes: every six items (N32x8: eight) the notes call is the live conversation
#                                           plus one message (already read by the server), and every turn in view is then moved out,
#                                           so nothing is read twice; the ordinary cut stays as the safety net
#   N32xth N32xth6                          N32x with a notes call that thinks, every ten items (N32xth) or every six (N32xth6): an audit of the
#                                           no-thinking changes against the truth found wrong values in the NOTES of every such run
#   N32y                                    N32xth after its first run (39/39 in 9 min 49 s): a doubtful in-place reply is asked for again in place
#                                           with thinking instead of handing the turns to the ordinary cut, and a STATE value is read as the
#                                           last number in it ("-58 - 35 = -93, then set to 82" is 82); same settings, the arm for both seeds and 1M
#   N32z                                    N32y plus the mention check: a name of a STATE line that the items being moved out mention, outside a
#                                           question, without a line in CHANGES is asked about once (N32y seed 1 missed one removal that way)
#   N32w N32w6                              N32z with the count check: a name's lines in CHANGES must account for as many changes as the items being
#                                           moved out mention it (N32z seed 0: three counters wrong in the NOTES, two of them the second of two
#                                           changes in one item); N32w6 takes notes every six items instead of ten
#   N32v                                    N32w plus: a bare new number in CHANGES must be one the items state; a worked-out value has to show its
#                                           working, which the harness checks (N32w seed 0 wrote `rumi16: -132` for 29 - 73). The 1M arm.
#   N32u                                    N32v where "a value the items state" means: stated in a sentence that names the thing, or the one after
#                                           it (N32v seed 1 wrote `zija81: -62` for 134 - 16; a 62 elsewhere in the items let it pass)
#   N32u6 N32ur                             N32u taking notes every six items instead of ten;  N32u plus the retrieved sentences at each question
#                                           (store holds every item): the keeper with retrieval as well as `recall`
#   N32t                                    N32u after its hard-stream run looped (one refused command sent 362 times): from the third refused repeat
#                                           in a row the refusal says to stop and answer, and that one call is sampled (0.5 rising to 1.0)
#   N32s                                    N32t after its hard-stream run circled between three searches: `recall` shows each match with the sentence
#                                           after it, and a search sent a third time since the last item arrived is refused like a repeat
#   N32sr                                   N32s plus the retrieved sentences at each question, and a rule named in any reply of one notes call is kept
#                                           (N32s lost the standing rule when a second, asked-for reply left it out): everything together
#   N32k N32kr                              campaign 11 (2026-10-12): the keeper with in-place notes (N32u's settings) and the same with retrieval at
#                                           each question (N32sr's settings), on the code after the second review (lab commit 080ebd6b9 and later)
#   N32g N32gr X32g                         N32p / N32pr / X32q with the code of 2026-10-12 14:45: the note-check rewrite of that day (packed
#                                           lines followed exactly or asked about) and changes said without their number: a line without working
#                                           is followed when the turns name the thing in a sentence without any number and the new value is the
#                                           old one times 2..10, the old one with a whole fraction of itself added or taken, or the old one with
#                                           another thing's value added or taken; and (15:10) two rules from scoring the checks against the
#                                           true ledger (tools/ctxkeeper/check_score.py): a set written as a sum with a remark that says "set" is
#                                           asked about, and a sum that gives its written result with one sign turned round is read that way
#   N32h                                    the first version of that rule (14:18), which also took another thing's value as the NEW value: the
#                                           model's misreading of "received exactly what X stood at" as a set passed without a question
#   X32q                                    X32p with the proxy code of 2026-10-12 10:00: a question that arrived in a tool result and is still open
#                                           is never cut out of view. (N32p / N32pr were first run after that commit: for the harness they also
#                                           include the open question kept across the ordinary cut and `recall --before N` with nearest matches.)
#   N32p N32pr X32p                         N32n / N32nr / X32n2 with the code of 2026-10-12 09:00 (after the second 1M proxy run): an amount in
#                                           working may be another thing's value or a small factor; a questioned notes reply never falls back to
#                                           the full rewrite (the first reply stands) and a line whose number the turns do not state is left out;
#                                           a misspelled name is put right; X32p's proxy also runs `recall` in item numbers (--recall-label, set
#                                           by whoever starts the proxy) and shows the matches nearest to where the search was anchored
#   N32n N32nr X32n                         N32m / N32mr / X32m with the code of 2026-10-12 07:00 (after the 1M proxy run): a notes line that packs
#                                           several changes is counted and followed part by part, a change noted before is no change, amounts in
#                                           working must be stated for the thing; X32n's proxy also keeps the searches of a turn that ended
#                                           empty, labels a search hit with its item, and is started with --max-recalls 16 --notes-scan (runner)
#   N32m N32mr X32m                         N32k / N32kr / X32i after the merge fix of 2026-10-12 03:50: when a notes reply is asked for again, the
#                                           new reply replaces only the lines of the names it mentions (X32i seed 1 lost nine items' changes to a
#                                           one-line second reply); the proxy also logs every notes reply
#   NOTE on the N32x..N32sr names: each is one state of clm_keeper.py on the night it ran, not a switch. With today's code
#   N32xth, N32y share one setting, N32z has mention_check=true, N32w/N32v count, N32u/N32t/N32s near (identical now), and
#   N32ur/N32sr are identical; re-running a name reproduces today's code under that name, not the run on record. The runs
#   on record: lab commits 20ef39323 (campaign 10) and b7d6413b8 (campaign 10b), evidence data/2026-10-11-context-campaign10.
#   N32er                                   N32e plus the retrieved sentences (store holds every item)
#   R32                                     retrieval only ("RAG"): the plain window agent, cut items go to a store, and at each question
#                                           the 20 best-matching stored sentences per question are shown, each with the sentence
#                                           after it (BM25 over sentences indexed with their item number, rag_retrieve.py);
#                                           no notes, no pinned rules, no search tool
#   R32a N32ra                              R32 / N32r whose store holds every item from the moment it arrives (the items still in view
#                                           are searched too), so the retrieved list for a question is complete on its own
#   R32a40                                  R32a with up to 40 sentences per question (the 1M stream: 20 cover 187 of 228 questions, 40 cover 220)
#   R32b R32b40                             R32a / R32a40 with the store kept by the harness only (no archive files in the sandbox): in R32 and
#                                           R32a the model found the archive directory itself and answered the final list with scripts over it
#   R32c40                                  R32b40 with room for 70,000 characters of retrieved text instead of 30,000 (the window is cut deeper to
#                                           make room): at 1M a probe item asks seven questions, and 40 sentences each do not fit in 30,000
#   N32r                                    rules-only notes + retrieval: only new rules are noted at a cut (no thinking), values are
#                                           worked out from the retrieved sentences and `recall`
#   N32jr N32dr                             N32j / N32d plus the retrieved sentences at each question
#   X32b                                    X32 with tools/ctxkeeper as of commit c16585171 (notes call effort and retry, search limit,
#                                           stable history fingerprint); a separate name so the first runs stay on record
#   X32i                                    X32 through tools/ctxkeeper started with --notes-mode inplace: the proxy takes notes in place (the request
#                                           the server has just read plus one message), applies the changes itself and moves the noted turns out
#   X32                                     the plain agent with no context budget (it sends its whole history), served through the
#                                           tools/ctxkeeper proxy at CTXKEEPER_BASE: the keeper policy as a product, not as a harness
#   W48 D48 C48 B48ir B48ira B48ira-free   live-cap study at budget 49,152 (48K): W = truncate (clm_baselines
#          TruncateAgent: drop oldest turns once over the limit, down to 75 %), D = compact (CompactAgent: at 75 %
#          stub all but the newest 3 tool outputs and strip earlier thinking, then drop oldest if still over),
#          C = summary at 75 %, B..ir/ira as B32ir/B32ira, B..ira-free as longmemeval-run.sh B32ira-free
#          (clm_freenotes.ClmFreeNotesAgent, state_max_tokens STATE_MAX_TOKENS [6144]). W, D are LOSSY baselines.
#   W200 D200 C200 B200ir B200ira B200ira-free   the same at budget 204,800 (200K cap)
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
        "B32ir": ("improved", "memory", 32768), "Ar": ("plain", "memory", 0), "E32r": ("plain", "notes", 32768),
        "B32ira": ("improved", "memory", 32768), "B32iq": ("improved", "memory", 32768)}
for cap, b in (("16", 16384), ("48", 49152), ("200", 204800)):  # live-cap study: lossy baselines vs the improved agent (16K = fast scale, 2026-10-10)
    ARMS.update({"W" + cap: ("truncate", "memory", b), "D" + cap: ("compact", "memory", b),
                 "C" + cap: ("summary", "memory", b), "B" + cap + "ir": ("improved", "memory", b),
                 "B" + cap + "ira": ("improved", "memory", b), "B" + cap + "ira-free": ("improved", "memory", b)})
ARMS.update({"W32": ("truncate", "memory", 32768), "P32": ("compact", "memory", 32768)})  # 32K lossy floors beside B32ir/B32ira/C32 (D32 is taken)
ARMS["B32ira-free"] = ("improved", "memory", 32768)   # free-text notes + archive at 32K (general form of B32ira; 2026-10-11)
ARMS["B32iraR"] = ("improved", "memory", 32768)       # B32ira + permanent RULE lines in STATE.txt (clm_rules; 2026-10-11)
ARMS["B32iraR4"] = ("improved", "memory", 32768)      # B32iraR fetching and folding 4 items per command (speed lever)
ARMS["B32iraRH"] = ("improved", "memory", 32768)      # B32iraR + state history kept by the harness (`recall --state-at N`; own rule class)
ARMS["N32"] = ("truncate", "memory", 32768)           # sliding window + archive of the cut items + NOTES at each cut + recall (clm_keeper)
ARMS["N200"] = ("truncate", "memory", 204800)         # the same at the 200K cap
ARMS["N32j"] = ("truncate", "memory", 32768)          # N32 thinking only on calls that hold a question or an error; the notes call thinks
ARMS["N32f"] = ("truncate", "memory", 32768)          # N32j with a notes call that does not think and a deeper cut (to 50 %): the fast setting
ARMS["N200j"] = ("truncate", "memory", 204800)        # N32j at the 200K cap
ARMS["N64j"] = ("truncate", "memory", 65536)          # N32j at a 64K live window
for a in ("N32j35", "N32d", "N32dth", "N32d35", "N32e", "N32e35", "N32e25", "N32c35", "N32c25", "N32c15", "N32x", "N32x8", "N32xth", "N32xth6", "N32y", "N32z", "N32w", "N32w6", "N32v", "N32u", "N32u6", "N32ur", "N32t", "N32s", "N32sr", "N32k", "N32kr", "N32m", "N32mr", "N32n", "N32nr", "N32p", "N32pr", "N32h", "N32g", "N32gr", "R32", "R32a", "R32a40", "R32b", "R32b40", "R32c40", "N32r", "N32ra", "N32jr", "N32dr", "N32er"):   # campaign 10 (see the header)
    ARMS[a] = ("truncate", "memory", 32768)
ARMS["X32"] = ("plain", "memory", 0)                  # the plain agent with no budget of its own, served through tools/ctxkeeper
ARMS["X32b"] = ("plain", "memory", 0)                 # X32 again after the proxy fixes of 2026-10-11 (same arm; a new name keeps both results)
ARMS["X32i"] = ("plain", "memory", 0)                 # X32 with the proxy started with --notes-mode inplace (2026-10-12; the runner sets the proxy's options)
ARMS["X32m"] = ("plain", "memory", 0)                 # X32i after the merge fix (an asked-for notes reply no longer replaces the one before it)
ARMS["X32n"] = ("plain", "memory", 0)                 # X32m with the proxy code and options of 2026-10-12 07:00 (see the header)
ARMS["X32q"] = ("plain", "memory", 0)                 # X32p plus: an open question survives every cut (see the header)
ARMS["X32g"] = ("plain", "memory", 0)                 # X32q with the proxy code of 2026-10-12 14:45 (see the header)
ARMS["X32p"] = ("plain", "memory", 0)                 # X32n2 with the proxy code of 2026-10-12 09:00 (see the header); the proxy is started by hand with --recall-label
ARMS["X32n2"] = ("plain", "memory", 0)                # X32n after the fix of 2026-10-12 06:55: what the kept message says about a result already noted is not noted twice
ARMS["X32ir"] = ("plain", "memory", 0)                # the same with retrieval in the proxy as well, once it has that (reserved)
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
  local ar=0 qt=0
  [[ "$arm" == B32ir || "$arm" == B32ira || "$arm" == B32iq ]] && fm=read && tp=judgement && tc=${THINK_CAP_R:-4096}   # B32ir: reads prose itself
  [[ "$arm" == B32ira ]] && ar=1                   # B32ira: + archive-on-drop and `recall`
  [[ "$arm" == B32iq ]] && ar=1 && qt=1            # B32iq: + quoted events (`ctxfold --events`)
  [[ "$arm" == Ar ]] && sw=1                       # Ar: keep everything + window line (reading task baseline)
  local xa=() extra=""
  if [[ "$arm" =~ ^B(16|48|200)(ir|ira|ira-free)$ || "$arm" == B32ira-free ]]; then   # live-cap arms: as B32ir / B32ira / longmemeval B32ira-free
    fm=read; tp=judgement; tc=${THINK_CAP_R:-4096}
    [[ "$arm" == *ira* ]] && ar=1
    if [[ "$arm" == *-free ]]; then
      extra="state_max_tokens=${STATE_MAX_TOKENS:-6144}"
      xa=(-a clm_freenotes:ClmFreeNotesAgent)      # harbor: the last --agent wins; run-context-job.sh passes "$@" last
    fi
  fi
  local fb=${FOLD_BATCHES:-}
  local api=$API_BASE
  if [[ "$arm" == X32 || "$arm" == X32b || "$arm" == X32i || "$arm" == X32m || "$arm" == X32n || "$arm" == X32n2 || "$arm" == X32p || "$arm" == X32q || "$arm" == X32g || "$arm" == X32ir ]]; then   # the keeper policy as a proxy: the agent sends everything, the proxy keeps the window
    api=${CTXKEEPER_BASE:?arm X32 needs CTXKEEPER_BASE, the URL of a running tools/ctxkeeper proxy (http://host:port/v1)}
  fi
  if [[ "$arm" == B32iraR || "$arm" == B32iraR4 || "$arm" == B32iraRH ]]; then   # B32ira + pinned RULE lines (standing rules and methods stay in view)
    fm=read; tp=judgement; tc=${THINK_CAP_R:-4096}; ar=1
    xa=(-a clm_rules:ClmRulesAgent)
    [[ "$arm" == B32iraRH ]] && xa=(-a clm_history:ClmHistoryAgent)   # + every accepted STATE.txt version, read with `recall --state-at N`
    [[ "$arm" == B32iraR4 ]] && fb=4               # four items per command: half the calls per item become an eighth
  fi
  if [[ "$arm" == N32 || "$arm" == N200 || "$arm" == N32j || "$arm" == N32f || "$arm" == N200j ]]; then   # sliding window that archives what it cuts, keeps NOTES, offers recall
    xa=(-a clm_keeper:KeeperAgent)
    [[ "$arm" == N32j || "$arm" == N200j ]] && extra="thinking_policy=judgement notes_thinking=true"
    [[ "$arm" == N32f ]] && extra="thinking_policy=judgement notes_thinking=false truncate_target_ratio=0.5"
  fi
  local jt="thinking_policy=judgement notes_thinking=true" jf="thinking_policy=judgement notes_thinking=false"
  case "$arm" in                                   # campaign 10: cheaper notes, and retrieval ("RAG") alone and added
    N64j)   xa=(-a clm_keeper:KeeperAgent); extra="$jt" ;;
    N32j35) xa=(-a clm_keeper:KeeperAgent); extra="$jt truncate_target_ratio=0.35" ;;
    N32d|N32e) xa=(-a clm_keeper:KeeperAgent); extra="$jf notes_mode=delta" ;;   # N32e: after the two fixes of 18:30 (see the header)
    N32e35) xa=(-a clm_keeper:KeeperAgent); extra="$jf notes_mode=delta truncate_target_ratio=0.35" ;;
    N32e25) xa=(-a clm_keeper:KeeperAgent); extra="$jf notes_mode=delta truncate_target_ratio=0.25" ;;
    N32c35) xa=(-a clm_keeper:KeeperAgent); extra="$jf notes_mode=delta truncate_target_ratio=0.35 notes_chunk_tokens=11000" ;;
    N32c25) xa=(-a clm_keeper:KeeperAgent); extra="$jf notes_mode=delta truncate_target_ratio=0.25 notes_chunk_tokens=11000" ;;
    N32c15) xa=(-a clm_keeper:KeeperAgent); extra="$jf notes_mode=delta truncate_target_ratio=0.15 notes_chunk_tokens=11000" ;;
    N32x)   xa=(-a clm_keeper:KeeperAgent); extra="$jf notes_mode=delta notes_inplace=true notes_chunk_tokens=11000" ;;
    N32x8)  xa=(-a clm_keeper:KeeperAgent); extra="$jf notes_mode=delta notes_inplace=true notes_chunk_tokens=11000 inplace_turn_tokens=13000" ;;
    N32y)   xa=(-a clm_keeper:KeeperAgent); extra="$jt notes_mode=delta notes_inplace=true notes_chunk_tokens=11000 inplace_turn_tokens=17000" ;;
    N32z)   xa=(-a clm_keeper:KeeperAgent); extra="$jt notes_mode=delta notes_inplace=true notes_chunk_tokens=11000 inplace_turn_tokens=17000 mention_check=true" ;;
    N32v)   xa=(-a clm_keeper:KeeperAgent); extra="$jt notes_mode=delta notes_inplace=true notes_chunk_tokens=11000 inplace_turn_tokens=17000 mention_check=count" ;;
    N32u)   xa=(-a clm_keeper:KeeperAgent); extra="$jt notes_mode=delta notes_inplace=true notes_chunk_tokens=11000 inplace_turn_tokens=17000 mention_check=near" ;;
    N32t)   xa=(-a clm_keeper:KeeperAgent); extra="$jt notes_mode=delta notes_inplace=true notes_chunk_tokens=11000 inplace_turn_tokens=17000 mention_check=near" ;;
    N32s)   xa=(-a clm_keeper:KeeperAgent); extra="$jt notes_mode=delta notes_inplace=true notes_chunk_tokens=11000 inplace_turn_tokens=17000 mention_check=near" ;;
    N32sr)  xa=(-a clm_keeper:KeeperAgent); extra="$jt notes_mode=delta notes_inplace=true notes_chunk_tokens=11000 inplace_turn_tokens=17000 mention_check=near auto_retrieve=20 retrieve_scope=all" ;;
    N32k)   xa=(-a clm_keeper:KeeperAgent); extra="$jt notes_mode=delta notes_inplace=true notes_chunk_tokens=11000 inplace_turn_tokens=17000 mention_check=near" ;;
    N32kr)  xa=(-a clm_keeper:KeeperAgent); extra="$jt notes_mode=delta notes_inplace=true notes_chunk_tokens=11000 inplace_turn_tokens=17000 mention_check=near auto_retrieve=20 retrieve_scope=all" ;;
    N32m)   xa=(-a clm_keeper:KeeperAgent); extra="$jt notes_mode=delta notes_inplace=true notes_chunk_tokens=11000 inplace_turn_tokens=17000 mention_check=near" ;;
    N32mr)  xa=(-a clm_keeper:KeeperAgent); extra="$jt notes_mode=delta notes_inplace=true notes_chunk_tokens=11000 inplace_turn_tokens=17000 mention_check=near auto_retrieve=20 retrieve_scope=all" ;;
    N32n)   xa=(-a clm_keeper:KeeperAgent); extra="$jt notes_mode=delta notes_inplace=true notes_chunk_tokens=11000 inplace_turn_tokens=17000 mention_check=near" ;;
    N32nr)  xa=(-a clm_keeper:KeeperAgent); extra="$jt notes_mode=delta notes_inplace=true notes_chunk_tokens=11000 inplace_turn_tokens=17000 mention_check=near auto_retrieve=20 retrieve_scope=all" ;;
    N32p)   xa=(-a clm_keeper:KeeperAgent); extra="$jt notes_mode=delta notes_inplace=true notes_chunk_tokens=11000 inplace_turn_tokens=17000 mention_check=near" ;;
    N32h)   xa=(-a clm_keeper:KeeperAgent); extra="$jt notes_mode=delta notes_inplace=true notes_chunk_tokens=11000 inplace_turn_tokens=17000 mention_check=near" ;;
    N32g)   xa=(-a clm_keeper:KeeperAgent); extra="$jt notes_mode=delta notes_inplace=true notes_chunk_tokens=11000 inplace_turn_tokens=17000 mention_check=near" ;;
    N32pr)  xa=(-a clm_keeper:KeeperAgent); extra="$jt notes_mode=delta notes_inplace=true notes_chunk_tokens=11000 inplace_turn_tokens=17000 mention_check=near auto_retrieve=20 retrieve_scope=all" ;;
    N32gr)  xa=(-a clm_keeper:KeeperAgent); extra="$jt notes_mode=delta notes_inplace=true notes_chunk_tokens=11000 inplace_turn_tokens=17000 mention_check=near auto_retrieve=20 retrieve_scope=all" ;;
    N32u6)  xa=(-a clm_keeper:KeeperAgent); extra="$jt notes_mode=delta notes_inplace=true notes_chunk_tokens=11000 inplace_turn_tokens=9500 mention_check=near" ;;
    N32ur)  xa=(-a clm_keeper:KeeperAgent); extra="$jt notes_mode=delta notes_inplace=true notes_chunk_tokens=11000 inplace_turn_tokens=17000 mention_check=near auto_retrieve=20 retrieve_scope=all" ;;
    N32w)   xa=(-a clm_keeper:KeeperAgent); extra="$jt notes_mode=delta notes_inplace=true notes_chunk_tokens=11000 inplace_turn_tokens=17000 mention_check=count" ;;
    N32w6)  xa=(-a clm_keeper:KeeperAgent); extra="$jt notes_mode=delta notes_inplace=true notes_chunk_tokens=11000 inplace_turn_tokens=9500 mention_check=count" ;;
    N32xth) xa=(-a clm_keeper:KeeperAgent); extra="$jt notes_mode=delta notes_inplace=true notes_chunk_tokens=11000 inplace_turn_tokens=17000" ;;
    N32xth6) xa=(-a clm_keeper:KeeperAgent); extra="$jt notes_mode=delta notes_inplace=true notes_chunk_tokens=11000" ;;
    N32er)  xa=(-a clm_keeper:KeeperAgent); extra="$jf notes_mode=delta auto_retrieve=20 retrieve_scope=all" ;;
    N32dth) xa=(-a clm_keeper:KeeperAgent); extra="$jt notes_mode=delta" ;;
    N32d35) xa=(-a clm_keeper:KeeperAgent); extra="$jf notes_mode=delta truncate_target_ratio=0.35" ;;
    R32)    xa=(-a clm_keeper:KeeperAgent); extra="$jf notes_mode=none auto_retrieve=20 recall_tool=false" ;;
    R32a)   xa=(-a clm_keeper:KeeperAgent); extra="$jf notes_mode=none auto_retrieve=20 recall_tool=false retrieve_scope=all" ;;
    R32a40) xa=(-a clm_keeper:KeeperAgent); extra="$jf notes_mode=none auto_retrieve=40 recall_tool=false retrieve_scope=all" ;;
    R32b)   xa=(-a clm_keeper:KeeperAgent); extra="$jf notes_mode=none auto_retrieve=20 recall_tool=false retrieve_scope=all archive_files=false" ;;
    R32b40) xa=(-a clm_keeper:KeeperAgent); extra="$jf notes_mode=none auto_retrieve=40 recall_tool=false retrieve_scope=all archive_files=false" ;;
    R32c40) xa=(-a clm_keeper:KeeperAgent); extra="$jf notes_mode=none auto_retrieve=40 recall_tool=false retrieve_scope=all archive_files=false retrieve_max_chars=70000" ;;
    N32r)   xa=(-a clm_keeper:KeeperAgent); extra="$jf notes_mode=rules auto_retrieve=20" ;;
    N32ra)  xa=(-a clm_keeper:KeeperAgent); extra="$jf notes_mode=rules auto_retrieve=20 retrieve_scope=all" ;;
    N32jr)  xa=(-a clm_keeper:KeeperAgent); extra="$jt auto_retrieve=20" ;;
    N32dr)  xa=(-a clm_keeper:KeeperAgent); extra="$jf notes_mode=delta auto_retrieve=20" ;;
  esac
  echo "arm=$arm agent_class=${xa[1]:-run-context-job.sh default for $agent} extra_kwargs=$extra fold_batches=${fb:-1}" > "$RUNS/$job.arm.txt"
  TASKS="$td" JOB_NAME="$job" CONTEXT_BUDGET="$budget" DROP_OLD_THINKING="$drop" THINK_CAP="$tc" ENABLE_THINKING="$et" THINKING_POLICY="$tp" SHOW_WINDOW="$sw" FOLD_MODE="$fm" ARCHIVE="$ar" QUOTED="$qt" FOLD_BATCHES="$fb" API_BASE="$api" EXTRA_KWARGS="${EXTRA_KWARGS:-} $extra" "$D/run-context-job.sh" "$agent" "$RUNS" "${xa[@]}" > "$RUNS/$job.out" 2>&1
  local rc=$?
  if (( rc != 0 )); then
    echo "!!! $job: launcher exited with status $rc; this run does not count"
    FAILED=1
  fi
  echo "   rc=$rc $(grep -h -o '[a-z]* score [0-9.]* raw [0-9.]*.*void=[A-Za-z]*' "$RUNS/jobs/$job"/*/verifier/test-stdout.txt 2>/dev/null | head -1)"
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
"$PY" "$D/summarize_results.py" --json "$O/summary.json" "$RUNS"/jobs/[A-ENPRWX]* | tee "$O/summary.txt"
[[ $FAILED == 0 ]] || { echo "!!! at least one trial was ended by a cap/timeout/rule; see the lines above"; exit 1; }
