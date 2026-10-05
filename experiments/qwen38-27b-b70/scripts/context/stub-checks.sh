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
#                   preserve_thinking=false (v), no delivered item lost. Its context readouts give the
#                   sizes for 8 and 9.
#   8 imp-protect   budget between "after fold" and "after fold + one item", room check switched off:
#                   every delivery overflows, the rollback must keep it (i): items_lost 0,
#                   seen_whole == delivered, protected rollbacks >= 1, reward 1.0
#   9 imp-gate      budget for one item but not two, headroom 0; the stub runs `next` again before
#                   folding: refused with "NOT RUN", then it folds and retries (ii): refusals >= 1,
#                   items_lost 0, reward 1.0
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
FAKE_PLAN=improved-fold FAKE_CORRUPT=1 start_stub "$O/stub-imp-base.log"; ijob imp-base 200000 "$SLR"
n_all=$(grep -c '^fake-req:' "$O/stub-imp-base.log"); n_ok=$(grep '^fake-req:' "$O/stub-imp-base.log" | grep -c '"preserve_thinking": false')
msg="reward=$reward void=$void ended_by=$ended_by state_rejected=$state_rejected items_lost=$items_lost preserve_false=$n_ok/$n_all after_fold=$after_fold after_item=$after_item"
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
stop_stub

echo; "$PY" "$D/summarize_results.py" --brief "$O/runs" | tee "$O/summary.txt"
echo "== $FAILS check(s) failed"
[[ $FAILS == 0 ]]
