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
stop_stub

echo; "$PY" "$D/summarize_results.py" --brief "$O"/runs/jobs/* | tee "$O/summary.txt"
echo "== $FAILS check(s) failed"
[[ $FAILS == 0 ]]
