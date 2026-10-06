#!/usr/bin/env bash
# Stub checks of the context harness that second-comparison.sh STUB=1 does not cover. No model, no GPU;
# Harbor + docker (one trial at a time), the fake server on a free port. Prints one PASS/FAIL line per
# check and exits 1 on any FAIL.
#
#   stub-checks.sh <out_dir>
#
#   1 smoke         STUB=1 smoke.sh (legacy tiny task, agents clm/summary/plain)
#   2 summary-fires SummaryAgent at a tiny budget (4096, reserve 512, max_tokens 1024) on a v2 kv task
#                   of ~5 small batches: at least one summary must succeed; no cap/timeout end
#   3 clm-files     ClmAgent at the same tiny budget: no cap/timeout end, not VOID; prints every file
#                   the run created or changed in the container (is the mirror the only harness file?)
#   4 drop-plain    PlainAgent, no budget, DROP_OLD_THINKING=1: requests carry preserve_thinking=false
#   5 drop-clm      ClmAgentT (DROP_OLD_THINKING=1), tiny budget: loads, requests carry it, not invalid
#   6 drop-summary  SummaryAgent, tiny budget, DROP_OLD_THINKING=1: the tool-less summary request also
#                   carries preserve_thinking=false
#   improved agent (clm_improved.py) on a tiny ledger task (~5 items of 30 updates, 8 counters), with
#   the fake server's scripted "fold into STATE.txt" agent:
#   7 imp-base      big budget; also corrupts STATE.txt once: reward 1.0, not VOID although STATE.txt
#                   names the counters (iv), the bad edit restored (iii), every request carries
#                   preserve_thinking=true with no thinking left on earlier assistant turns (v, v3), no delivered item lost. Its context readouts give the
#                   sizes for 8 and 9.
#   8 imp-protect   budget between "after fold" and "after fold + one item", room check switched off:
#                   every delivery overflows, the rollback must keep it (i): items_lost 0,
#                   seen_whole == delivered, protected rollbacks >= 1, reward 1.0
#   9 imp-gate      budget for one item but not two, headroom 0; the stub runs `next` again before
#                   folding: refused with "NOT RUN", then it folds and retries (ii): refusals >= 1,
#                   items_lost 0, reward 1.0
#  13 imp-judgement  THINKING_POLICY=judgement (arm B32in): thinking on until ctxfold has folded once,
#                   after a ctxfold refusal and for the final item; off on routine fetch/fold calls;
#                   and no call's messages (pinned state aside) differ from the previous call's except
#                   after a context edit (prefix stability)
#  14 imp-never      THINKING_POLICY=never (B32io): every request has enable_thinking=false
#  20 imp-archive    archive-on-drop + recall (B32ira) with retention questions: verbatim archive accepted by the
#                   grader, archive writes refused, recall works, reward 1.0 incl. retention answers
#  21 imp-fold2      FOLD_BATCHES=2: two items per fetch and per fold; reward 1.0
#  19 imp-answers    writing /app/answers.json before the final item is refused (answers guard); reward 1.0
#  18 imp-guards     read mode: repeated command refused, STATE line vanishing without an item rejected and
#                   restored, `next` written as text recovered as a tool call; reward 1.0
#  17 imp-read       read mode (B32ir) on a tiny sparse-prose task: `ctxfold --drop` refuses an incomplete
#                   STATE.txt once, thinking on until the first drop and after the refusal, off on routine
#                   batches, reward 1.0, not VOID
#  16 aw             plain agent + SHOW_WINDOW on a 7,000-token stub window: every tool result ends with
#                   the window line (sizes from the server's usage), a `next` that would not leave room to
#                   work and answer is refused with "you cannot fetch more; write ... answers.json now",
#                   and the run ends by submitting
#  15 e32o           plain agent, files allowed, ENABLE_THINKING=false: every request has it false
#  12 imp-ctxfold    the harness fold helper: a FOLD.py with the real seed-1 DEL bug must be refused by its
#                   selftest, the fixed one must fold every item (reward 1.0, not VOID)
#  11 imp-loopguard no think cap, every first reply cut with no command: after 2 in a row the agent
#                   forces an action (continuation with a 2,048-token thinking allowance)
#  10 imp-thinkcap  THINK_CAP=64 and a stub that cuts every first reply inside the thinking: the
#                   continuation (continue_final_message, add_generation_prompt=false) must carry the
#                   action; every first request has max_tokens 64; reward 1.0
set -uo pipefail
D=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PY=${VENV:-/mnt/fast-ai/venvs/clm}/bin/python
O=${1:?usage: stub-checks.sh <out_dir>}
mkdir -p "$O"; O=$(cd "$O" && pwd)
FAILS=0
pass() { echo "PASS $1${2:+: $2}"; }
fail() { echo "FAIL $1${2:+: $2}"; FAILS=$((FAILS + 1)); }

STUB_PID=
stop_stub() { [[ -n "$STUB_PID" ]] && kill "$STUB_PID" 2>/dev/null && wait "$STUB_PID" 2>/dev/null; STUB_PID=; true; }
trap stop_stub EXIT
start_stub() {  # log_file
  stop_stub
  local port
  port=$("$PY" -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1])')
  "$PY" "$D/fake_openai_server.py" "$port" > "$1" 2>&1 &
  STUB_PID=$!
  for _ in $(seq 50); do curl -sf "http://127.0.0.1:$port/v1/models" >/dev/null && break; sleep 0.1; done
  export API_BASE="http://127.0.0.1:$port/v1"
}
row() {  # job -> "reward invalid void summaries summary_failed ended_by"
  "$PY" - "$O/runs/jobs/$1" "$D" <<'PY'
import sys; sys.path.insert(0, sys.argv[2])
from pathlib import Path
import summarize_results as s
t = [p for p in Path(sys.argv[1]).iterdir() if (p / "agent").exists()][0]
r = s.trial_row(t)
print(r["reward"], r["invalid"], r["void"], r["summaries"], r["summary_failed"], r["ended_by"])
PY
}
job() {  # name agent budget drop -> runs one Harbor trial on the tiny-budget task
  local name=$1 agent=$2 budget=$3 drop=$4
  rm -rf "${O:?}/runs/jobs/$name"
  TASKS="$TASK" JOB_NAME="$name" CONTEXT_BUDGET="$budget" BUDGET_RESERVE=512 MAX_TOKENS=1024 \
    DROP_OLD_THINKING="$drop" TASK_TEMPLATE=open_problems \
    "$D/run-context-job.sh" "$agent" "$O/runs" > "$O/runs/$name.out" 2>&1
}

if [[ "${ONLY_IMPROVED:-0}" != 1 ]]; then
# 1 smoke
if STUB=1 "$D/smoke.sh" "$O/smoke" > "$O/smoke.out" 2>&1; then pass smoke; else fail smoke "see $O/smoke.out"; fi

# tiny-budget v2 task: kv memory-only, batches of 20 SETs (~1.3K tokens), ~5 batches
"$PY" "$D/make_kvstream_tasks.py" "$O/tasks" --tokens 6000 --batch-size 20 --mode memory --seeds 0 > "$O/tasks.json"
TASK=$(ls -d "$O"/tasks/kv-memory-t6k-s0)
mkdir -p "$O/runs"

# 2 summary fires
start_stub "$O/stub-2.log"; job summary-tiny summary 4096 0
read -r rw inv vd ns nf eb < <(row summary-tiny)
if [[ $inv == False && $ns -ge 1 ]]; then pass summary-fires "summaries=$ns failed=$nf ended_by=$eb reward=$rw"
else fail summary-fires "summaries=$ns failed=$nf ended_by=$eb invalid=$inv"; fi

# 3 clm files
start_stub "$O/stub-3.log"; job clm-tiny clm 4096 0
read -r rw inv vd ns nf eb < <(row clm-tiny)
files=$("$PY" -c "import json,glob; d=json.load(open(glob.glob('$O/runs/jobs/clm-tiny/*/verifier/details.json')[0])); print(' '.join(d.get('new_files', [])))")
if [[ $inv == False && $vd == False ]]; then pass clm-files "ended_by=$eb; new files in container: $files"
else fail clm-files "invalid=$inv void=$vd ended_by=$eb; new files: $files"; fi

# 4-6 drop old thinking
for c in "drop-plain plain 0" "drop-clm clm 4096" "drop-summary summary 4096"; do
  set -- $c
  start_stub "$O/stub-$1.log"; job "$1" "$2" "$3" 1
  read -r rw inv vd ns nf eb < <(row "$1")
  n_all=$(grep -c '^fake-req:' "$O/stub-$1.log")
  n_ok=$(grep '^fake-req:' "$O/stub-$1.log" | grep -c '"preserve_thinking": false')
  n_sum=$(grep '^fake-req:' "$O/stub-$1.log" | grep '"has_tools": false' | grep -c '"preserve_thinking": false')
  msg="requests $n_ok/$n_all with preserve_thinking=false; ended_by=$eb"
  if [[ $1 == drop-summary ]]; then
    msg="$msg; summary requests with it: $n_sum (summaries=$ns)"
    [[ $inv == False && $n_all -gt 0 && $n_ok == "$n_all" && $n_sum -ge 1 ]] && pass "$1" "$msg" || fail "$1" "$msg"
  else
    [[ $inv == False && $n_all -gt 0 && $n_ok == "$n_all" ]] && pass "$1" "$msg" || fail "$1" "$msg"
  fi
done

fi  # ONLY_IMPROVED
mkdir -p "$O/runs"
# ---------------- improved agent (clm_improved.py) ----------------
"$PY" "$D/make_ledger_tasks.py" "$O/tasks-ledger" --tokens 7000 --batch-size 30 --n-counters 8 \
  --mode memory --seeds 0 > "$O/tasks-ledger.json"
LTASK=$(ls -d "$O"/tasks-ledger/ledger-memory-t7k-s0)
info() {  # job -> key=value lines for the improved checks
  "$PY" - "$O/runs/jobs/$1" "$D" <<'PY'
import sys, json; sys.path.insert(0, sys.argv[2])
from pathlib import Path
import summarize_results as s
ts = s.expand([Path(sys.argv[1])])
if not ts:
    print("reward=None"); print("invalid=True"); print("ended_by=no_trial"); sys.exit(0)
t = ts[0]
r = s.trial_row(t)
for k in ("reward", "invalid", "void", "ended_by", "items_lost", "delivered", "seen_whole",
          "gate_refusals", "protected_rollbacks", "state_rejected", "think_cap_cont"):
    print(f"{k}={r.get(k)}")
# context readouts after a fold ("folded ...") and after a delivered item ("ITEM ...")
import re, statistics
fold, item = [], []
for m in json.load(open(t / "agent" / "trajectory.ctx.json"))["segments"]:
    for st in m["steps"]:
        for res in ((st.get("observation") or {}).get("results") or []):
            c = res.get("content") or ""
            mm = re.search(r"\[context: ~(\d+)/", c)
            if mm:
                (fold if c.startswith("folded") else item if c.startswith("ITEM ") else []).append(int(mm.group(1)))
print(f"after_fold={int(statistics.median(fold)) if fold else 0}")
print(f"after_item={int(statistics.median(item)) if item else 0}")
PY
}
ijob() {  # name budget extra_kwargs think_cap
  rm -rf "${O:?}/runs/jobs/$1"
  TASKS="$LTASK" JOB_NAME="$1" CONTEXT_BUDGET="$2" BUDGET_RESERVE=512 MAX_TOKENS=1024 TASK_TEMPLATE=open_problems \
    EXTRA_KWARGS="$3" THINK_CAP="${4:-}" "$D/run-context-job.sh" improved "$O/runs" > "$O/runs/$1.out" 2>&1
  unset reward invalid void ended_by items_lost delivered seen_whole gate_refusals protected_rollbacks \
    state_rejected think_cap_cont after_fold after_item
  eval "$(info "$1")"
  : "${reward:=None}" "${invalid:=True}" "${void:=None}" "${ended_by:=none}" "${items_lost:=None}"
}

# 7 base (+ corrupt STATE.txt once)
SLR='state_line_regex=^[a-z]+[0-9]{2}\s-?[0-9]+$'   # the stub's state format "name value"
FAKE_PLAN=improved-fold FAKE_CORRUPT=1 FAKE_REASONING=1 start_stub "$O/stub-imp-base.log"; ijob imp-base 200000 "$SLR"
# v3: the improved agent strips earlier thinking itself and sends preserve_thinking=true (stable
# render). Every request must carry preserve_thinking=true AND no assistant turn before the newest
# message may still hold thinking text (the stub's replies all carry some: FAKE_REASONING=1).
n_all=$(grep -c '^fake-req:' "$O/stub-imp-base.log")
n_ok=$(grep '^fake-req:' "$O/stub-imp-base.log" | grep '"preserve_thinking": true' | grep -c '"asst_with_reasoning": 0')
msg="reward=$reward void=$void ended_by=$ended_by state_rejected=$state_rejected items_lost=$items_lost preserve_true_and_stripped=$n_ok/$n_all after_fold=$after_fold after_item=$after_item"
[[ $invalid == False && $void == False && $reward == 1.0 && ${state_rejected:-0} -ge 1 && $items_lost == 0 && $n_all -gt 0 && $n_ok == "$n_all" ]] \
  && pass imp-base "$msg" || fail imp-base "$msg"
X=${after_fold:-0}; Y=${after_item:-0}
if (( X > 0 && Y > X )); then
  # 8 protect: limit halfway between "after fold" and "after fold + item"; room check off
  FAKE_PLAN=improved-fold start_stub "$O/stub-imp-protect.log"
  ijob imp-protect $(( X + (Y - X) / 2 + 512 )) "guard_command_regex=a^ $SLR"
  msg="limit=$(( X + (Y - X) / 2 )) reward=$reward ended_by=$ended_by items_lost=$items_lost delivered=$delivered seen_whole=$seen_whole protected=$protected_rollbacks"
  [[ $invalid == False && $reward == 1.0 && $items_lost == 0 && $delivered == "$seen_whole" && ${protected_rollbacks:-0} -ge 1 ]] \
    && pass imp-protect "$msg" || fail imp-protect "$msg"
  # 9 gate: room for one item, not two; the stub probes `next` before folding
  FAKE_PLAN=improved-probe start_stub "$O/stub-imp-gate.log"
  ijob imp-gate $(( Y + (Y - X) / 2 + 512 )) "guard_headroom=0 $SLR"
  msg="limit=$(( Y + (Y - X) / 2 )) reward=$reward ended_by=$ended_by refusals=$gate_refusals items_lost=$items_lost"
  [[ $invalid == False && $reward == 1.0 && $items_lost == 0 && ${gate_refusals:-0} -ge 1 ]] \
    && pass imp-gate "$msg" || fail imp-gate "$msg"
else
  fail imp-protect "no context readouts from imp-base (after_fold=$X after_item=$Y)"
  fail imp-gate "no context readouts from imp-base"
fi
# 10 thinking cap
FAKE_PLAN=improved-fold FAKE_THINKCAP=1 start_stub "$O/stub-imp-thinkcap.log"; ijob imp-thinkcap 200000 "$SLR" 64
L="$O/stub-imp-thinkcap.log"
n_first=$(grep '^fake-req:' "$L" | grep '"has_tools": true' | grep -vc '"continue_final_message": true')
n_first64=$(grep '^fake-req:' "$L" | grep '"has_tools": true' | grep -v '"continue_final_message": true' | grep -c '"max_tokens": 64')
n_cont=$(grep '^fake-req:' "$L" | grep '"continue_final_message": true' | grep -c '"add_generation_prompt": false')
msg="reward=$reward ended_by=$ended_by continuations=$think_cap_cont first_requests=$n_first (max_tokens 64: $n_first64) continue_requests=$n_cont"
[[ $invalid == False && $reward == 1.0 && ${think_cap_cont:-0} -ge 1 && $n_first == "$n_first64" && $n_cont -ge 1 ]] \
  && pass imp-thinkcap "$msg" || fail imp-thinkcap "$msg"
# 11 loop guard: think cap OFF, the stub cuts every first reply inside the thinking (no command);
# after 2 such replies in a row the agent must force an action with the continuation
FAKE_PLAN=improved-fold FAKE_THINKCAP=1 start_stub "$O/stub-imp-loopguard.log"; ijob imp-loopguard 200000 "$SLR" ""
lg=$("$PY" -c "import json,glob; print(json.load(open(glob.glob('$O/runs/jobs/imp-loopguard/*/agent/improved_stats.json')[0])).get('loop_guard_calls'))" 2>/dev/null)
msg="reward=$reward ended_by=$ended_by loop_guard_calls=$lg continuations=$think_cap_cont"
[[ $invalid == False && $reward == 1.0 && ${lg:-0} -ge 1 ]] && pass imp-loopguard "$msg" || fail imp-loopguard "$msg"
# 12 ctxfold: a buggy FOLD.py (the real seed-1 DEL bug) must be refused, the fixed one folds every item
FAKE_PLAN=improved-ctxfold start_stub "$O/stub-imp-ctxfold.log"; ijob imp-ctxfold 200000 ""
cf=$("$PY" - "$O/runs/jobs/imp-ctxfold" "$D" <<'PY'
import sys; sys.path.insert(0, sys.argv[2])
from pathlib import Path
import summarize_results as s
ts = s.expand([Path(sys.argv[1])])
r = s.trial_row(ts[0]) if ts else {}
print(r.get("ctxfold_calls"), r.get("ctxfold_refused"))
PY
)
read -r cf_calls cf_ref <<< "$cf"
msg="reward=$reward void=$void ended_by=$ended_by items_lost=$items_lost ctxfold_calls=$cf_calls refused=$cf_ref"
[[ $invalid == False && $void == False && $reward == 1.0 && $items_lost == 0 && ${cf_ref:-0} -ge 1 && ${cf_calls:-0} -ge 2 ]] \
  && pass imp-ctxfold "$msg" || fail imp-ctxfold "$msg"
# 13 thinking only where judgement is needed (B32in) + prefix stability
FAKE_PLAN=improved-ctxfold start_stub "$O/stub-imp-judgement.log"
THINKING_POLICY=judgement ijob imp-judgement 200000 ""
jl=$("$PY" - "$O/stub-imp-judgement.log" "$O/runs/jobs/imp-judgement" <<'PY'
import json, sys, glob, re
reqs = [json.loads(l[len("fake-req: "):]) for l in open(sys.argv[1]) if l.startswith("fake-req: ")]
reqs = [r for r in reqs if r.get("has_tools")]
bad, off, on, fold_ok = [], 0, 0, False
for i, r in enumerate(reqs):
    th = (r.get("chat_template_kwargs") or {}).get("enable_thinking")
    head, tail = r.get("last_tool_head", ""), r.get("last_tool_tail", "")
    if head.startswith("ctxfold: folded"):
        fold_ok = True
    want = None
    if not fold_ok or head.startswith("ctxfold: REFUSED") or "This was the last item" in tail:
        want = True
    elif head.startswith("ctxfold: folded") or re.match(r"ITEM \d+/\d+ \(UPDATE\)", head):
        want = False
    if want is not None and th != want:
        bad.append((i, head[:30], th))
    off += th is False
    on += th is True
    if (r.get("chat_template_kwargs") or {}).get("reasoning_effort") != "medium":
        bad.append((i, "no reasoning_effort=medium (stable system prompt)", th))
st = json.load(open(glob.glob(sys.argv[2] + "/*/agent/improved_stats.json")[0]))
# Expected breaks of the message prefix: only the calls right after a context edit, i.e. after each
# successful `ctxfold` (it removes the folded item turns). Not breaks by construction: the first call
# (no predecessor), the pinned state changing (it is excluded from the comparison), thinking
# toggles (the messages are unchanged; the system line is kept identical by reasoning_effort=medium).
folds = sum(1 for r in reqs if r.get("last_tool_head", "").startswith("ctxfold: folded"))
calls = st.get("prefix_calls") or 0
after_edit = st.get("prefix_unstable_after_edit") or 0
unexpected = (st.get("prefix_unstable_no_edit") or 0) + max(0, after_edit - folds) + \
    (0 if (st.get("prefix_stable") or 0) + after_edit == max(calls - 1, 0) else 1)
print(len(bad), off, on, unexpected, st.get("prefix_stable"), calls, st.get("thinking_toggles"), after_edit, folds)
print("bad:", bad[:4], "first_unstable:", st.get("first_unstable_no_edit"), file=sys.stderr)
PY
)
read -r j_bad j_off j_on j_unst j_stab j_calls j_tog j_aed j_folds <<< "$jl"
msg="reward=$reward ended_by=$ended_by thinking off=$j_off on=$j_on wrong_choice=$j_bad prefix: stable=$j_stab of $((j_calls-1)) transitions, broken after an edit=$j_aed (ctxfold edits=$j_folds), unexpected=$j_unst; toggles=$j_tog"
[[ $invalid == False && $reward == 1.0 && $j_bad == 0 && ${j_off:-0} -ge 2 && ${j_on:-0} -ge 2 && $j_unst == 0 ]] \
  && pass imp-judgement "$msg" || fail imp-judgement "$msg"

# 14 thinking off on every call (B32io)
FAKE_PLAN=improved-ctxfold start_stub "$O/stub-imp-never.log"
THINKING_POLICY=never ijob imp-never 200000 ""
n_t=$(grep '^fake-req:' "$O/stub-imp-never.log" | grep -c '"has_tools": true')
n_off=$(grep '^fake-req:' "$O/stub-imp-never.log" | grep '"has_tools": true' | grep -c '"enable_thinking": false')
msg="reward=$reward ended_by=$ended_by requests with enable_thinking=false: $n_off/$n_t"
[[ $invalid == False && $reward == 1.0 && $n_t -gt 0 && $n_off == "$n_t" ]] && pass imp-never "$msg" || fail imp-never "$msg"

# 15 E32o: plain agent, files allowed, thinking off on every call
"$PY" "$D/make_ledger_tasks.py" "$O/tasks-ledger-notes" --tokens 7000 --batch-size 30 --n-counters 8 \
  --mode notes --seeds 0 > "$O/tasks-ledger-notes.json"
start_stub "$O/stub-e32o.log"
rm -rf "${O:?}/runs/jobs/e32o"
TASKS=$(ls -d "$O"/tasks-ledger-notes/ledger-notes-t7k-s0) JOB_NAME=e32o CONTEXT_BUDGET=32768 BUDGET_RESERVE=2048 \
  MAX_TOKENS=1024 ENABLE_THINKING=false TASK_TEMPLATE=open_problems "$D/run-context-job.sh" plain "$O/runs" > "$O/runs/e32o.out" 2>&1
read -r rw inv vd ns nf eb < <(row e32o)
n_t=$(grep '^fake-req:' "$O/stub-e32o.log" | grep -c '"has_tools": true')
n_off=$(grep '^fake-req:' "$O/stub-e32o.log" | grep '"has_tools": true' | grep -c '"enable_thinking": false')
msg="reward=$rw ended_by=$eb requests with enable_thinking=false: $n_off/$n_t"
[[ $inv == False && $rw == 1.0 && $n_t -gt 0 && $n_off == "$n_t" ]] && pass e32o "$msg" || fail e32o "$msg"
# 16 Aw: plain agent with SHOW_WINDOW on a tiny window (7,000 tokens, max_tokens 1,024): every tool
# result carries the window line, and a `next` that cannot fit is refused ("NOT RUN"); the stub then
# answers from what it has
FAKE_MAX_MODEL_LEN=7000 start_stub "$O/stub-aw.log"
rm -rf "${O:?}/runs/jobs/aw"
TASKS="$LTASK" JOB_NAME=aw CONTEXT_BUDGET=0 MAX_TOKENS=1024 SHOW_WINDOW=1 TASK_TEMPLATE=open_problems \
  "$D/run-context-job.sh" plain "$O/runs" > "$O/runs/aw.out" 2>&1
read -r rw inv vd ns nf eb < <(row aw)
aw=$("$PY" - "$O/runs/jobs/aw" <<'PY'
import json, sys, glob
t = glob.glob(sys.argv[1] + "/*/agent")[0]
ws = json.load(open(t + "/window_stats.json"))
ctx = json.load(open(t + "/trajectory.ctx.json"))
obs = [res.get("content") or "" for seg in ctx["segments"] for st in seg["steps"]
       for res in ((st.get("observation") or {}).get("results") or [])]
print(ws["window_refusals"], sum(1 for o in obs if "tokens used;" in o), len(obs),
      sum(1 for o in obs if "cannot fetch more" in o), int(bool(ws.get("last_server_total"))))
PY
)
read -r aw_ref aw_lines aw_obs aw_say aw_srv <<< "$aw"
msg="ended_by=$eb reward=$rw refusals=$aw_ref window_lines=$aw_lines/$aw_obs says_cannot_fetch=$aw_say uses_server_count=$aw_srv"
[[ $inv == False && $eb == submit && ${aw_ref:-0} -ge 1 && $aw_obs -gt 0 && $aw_lines == "$aw_obs" && ${aw_say:-0} -ge 1 \
   && $aw_srv == 1 ]] && pass aw "$msg" || fail aw "$msg"
# 17 read mode (arm B32ir) on a tiny sparse-prose task: STATE.txt as name lines, `ctxfold --drop` must refuse
# an incomplete STATE once, thinking on until the first successful drop and after the refusal, off on
# routine batches; reward 1.0; STATE.txt (counter names) must not void the run
"$PY" "$D/make_sparse_prose_tasks.py" "$O/tasks-sparse" --n-batches 4 --density 6 --batch-tokens 600 \
  --n-counters 8 --pronouns --seeds 0 > "$O/tasks-sparse.json"
STASK=$(ls -d "$O"/tasks-sparse/sparse-memory-b4-s0)
FAKE_PLAN=improved-read FAKE_REFERENCE="$STASK/tests/reference.json" start_stub "$O/stub-read.log"
LTASK_SAVE=$LTASK; LTASK=$STASK
FOLD_MODE=read THINKING_POLICY=judgement ijob imp-read 200000 ""
LTASK=$LTASK_SAVE
rd=$("$PY" - "$O/stub-read.log" "$O/runs/jobs/imp-read" <<'PY'
import json, sys, glob
reqs = [json.loads(l[len("fake-req: "):]) for l in open(sys.argv[1]) if l.startswith("fake-req: ")]
reqs = [r for r in reqs if r.get("has_tools")]
bad, ok_seen = 0, False
for r in reqs:
    th = (r.get("chat_template_kwargs") or {}).get("enable_thinking")
    head = r.get("last_tool_head", "")
    if head.startswith("ctxfold: removed items"):
        ok_seen = True
    want = True if (not ok_seen or head.startswith("ctxfold: REFUSED")) else \
        (False if head.startswith("ctxfold: removed") else None)
    bad += want is not None and th != want
t = glob.glob(sys.argv[2] + "/*/agent")[0]
ctx = json.load(open(t + "/trajectory.ctx.json"))
obs = [res.get("content") or "" for seg in ctx["segments"] for st in seg["steps"]
       for res in ((st.get("observation") or {}).get("results") or [])]
print(sum("ctxfold: REFUSED" in o for o in obs), sum("ctxfold: removed items" in o for o in obs), bad)
PY
)
read -r rd_ref rd_drop rd_bad <<< "$rd"
msg="reward=$reward void=$void ended_by=$ended_by drop_refused=$rd_ref drops=$rd_drop wrong_thinking_choice=$rd_bad items_lost=$items_lost"
[[ $invalid == False && $void == False && $reward == 1.0 && ${rd_ref:-0} -ge 1 && ${rd_drop:-0} -ge 4 && $rd_bad == 0 ]] \
  && pass imp-read "$msg" || fail imp-read "$msg"
# 18 harness guards for the read mode: a repeated command is refused, a STATE line vanishing (with no item
# in context) is rejected and restored, `next` written as text is recovered as a tool call
FAKE_PLAN=improved-read FAKE_GUARDS=1 FAKE_TEXTCALL=1 FAKE_REFERENCE="$STASK/tests/reference.json" start_stub "$O/stub-guards.log"
LTASK_SAVE=$LTASK; LTASK=$STASK
FOLD_MODE=read THINKING_POLICY=judgement ijob imp-guards 200000 ""
LTASK=$LTASK_SAVE
gd=$("$PY" - "$O/runs/jobs/imp-guards" <<'PY'
import json, sys, glob
t = glob.glob(sys.argv[1] + "/*/agent")[0]
st = json.load(open(t + "/improved_stats.json"))
print(st.get("repeats_refused", 0), st.get("state_rejected", 0), st.get("text_calls_recovered", 0))
PY
)
read -r g_rep g_rej g_txt <<< "$gd"
msg="reward=$reward ended_by=$ended_by repeats_refused=$g_rep state_rejected=$g_rej text_calls_recovered=$g_txt"
[[ $invalid == False && $reward == 1.0 && ${g_rep:-0} -ge 1 && ${g_rej:-0} -ge 1 && ${g_txt:-0} -ge 1 ]] \
  && pass imp-guards "$msg" || fail imp-guards "$msg"
# 19 answers guard: writing /app/answers.json before the final item is refused; the run completes
FAKE_PLAN=improved-read FAKE_EARLY_ANSWER=1 FAKE_REFERENCE="$STASK/tests/reference.json" start_stub "$O/stub-early.log"
LTASK_SAVE=$LTASK; LTASK=$STASK
FOLD_MODE=read THINKING_POLICY=judgement ijob imp-answers 200000 ""
LTASK=$LTASK_SAVE
ar=$("$PY" -c "import json,glob; print(json.load(open(glob.glob('$O/runs/jobs/imp-answers/*/agent/improved_stats.json')[0])).get('answers_refused',0))")
msg="reward=$reward void=$void ended_by=$ended_by answers_refused=$ar"
[[ $invalid == False && $void == False && $reward == 1.0 && ${ar:-0} -ge 1 ]] && pass imp-answers "$msg" || fail imp-answers "$msg"
# 20 archive-on-drop + recall (arm B32ira) on a tiny sparse task with retention questions: dropped items are
# archived verbatim, `recall` reads them, writing into the archive is refused, the grader accepts the archive
# (rule ok+archive, not VOID), reward 1.0 including the retention questions
"$PY" "$D/make_sparse_prose_tasks.py" "$O/tasks-sparse-s" --n-batches 4 --density 6 --batch-tokens 600 \
  --n-counters 8 --surprise 4 --seeds 0 > "$O/tasks-sparse-s.json"
SSTASK=$(ls -d "$O"/tasks-sparse-s/sparse-memory-b4-s0)
FAKE_PLAN=improved-read FAKE_ARCHIVE=1 FAKE_REFERENCE="$SSTASK/tests/reference.json" start_stub "$O/stub-archive.log"
LTASK_SAVE=$LTASK; LTASK=$SSTASK
FOLD_MODE=read THINKING_POLICY=judgement ARCHIVE=1 ijob imp-archive 200000 ""
LTASK=$LTASK_SAVE
ac=$("$PY" - "$O/runs/jobs/imp-archive" <<'PY'
import json, sys, glob
t = glob.glob(sys.argv[1] + "/*/agent/improved_stats.json")[0].rsplit("/agent/", 1)[0]   # the trial dir
st = json.load(open(t + "/agent/improved_stats.json"))
dt = json.load(open(t + "/verifier/details.json"))
print(st.get("recall_calls", 0), st.get("archive_write_refused", 0), (dt.get("archive") or {}).get("verbatim", 0),
      (dt.get("archive") or {}).get("files", 0), (dt.get("surprise") or {}).get("correct", 0), (dt.get("surprise") or {}).get("n", 0))
PY
)
read -r a_rec a_ref a_ver a_files a_sc a_sn <<< "$ac"
msg="reward=$reward void=$void recall_calls=$a_rec archive_write_refused=$a_ref archive_verbatim=$a_ver/$a_files surprise=$a_sc/$a_sn"
[[ $invalid == False && $void == False && $reward == 1.0 && ${a_rec:-0} -ge 2 && ${a_ref:-0} -ge 1 && ${a_ver:-0} -ge 4 \
   && $a_ver == "$a_files" && ${a_sn:-0} -ge 1 && $a_sc == "$a_sn" ]] && pass imp-archive "$msg" || fail imp-archive "$msg"

# 21 FOLD_BATCHES=2: two items per fetch and per fold (`next && next`), room check scaled; reward 1.0
FAKE_PLAN=improved-read FAKE_FOLD2=1 FAKE_REFERENCE="$STASK/tests/reference.json" start_stub "$O/stub-fold2.log"
LTASK_SAVE=$LTASK; LTASK=$STASK
FOLD_MODE=read THINKING_POLICY=judgement FOLD_BATCHES=2 ijob imp-fold2 200000 ""
LTASK=$LTASK_SAVE
f2=$("$PY" - "$O/runs/jobs/imp-fold2" <<'PY'
import json, sys, glob, re
t = glob.glob(sys.argv[1] + "/*/agent")[0]
ctx = json.load(open(t + "/trajectory.ctx.json"))
obs = [r.get("content") or "" for seg in ctx["segments"] for st in seg["steps"]
       for r in ((st.get("observation") or {}).get("results") or [])]
drops = [o for o in obs if o.startswith("ctxfold: removed items")]
two = sum(1 for o in drops if re.search(r"\[\d+, \d+\]", o))
print(len(drops), two, json.load(open(t + "/improved_stats.json")).get("fold_batches"))
PY
)
read -r f_drops f_two f_fb <<< "$f2"
msg="reward=$reward ended_by=$ended_by drops=$f_drops two_item_drops=$f_two fold_batches=$f_fb items_lost=$items_lost"
[[ $invalid == False && $reward == 1.0 && ${f_two:-0} -ge 1 && $f_fb == 2 && $items_lost == 0 ]] && pass imp-fold2 "$msg" || fail imp-fold2 "$msg"
stop_stub

echo; "$PY" "$D/summarize_results.py" --brief "$O/runs" | tee "$O/summary.txt"
echo "== $FAILS check(s) failed"
[[ $FAILS == 0 ]]
