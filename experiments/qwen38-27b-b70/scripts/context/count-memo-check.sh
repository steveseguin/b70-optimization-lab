#!/usr/bin/env bash
# Check that COUNT_MEMO=1 (clm_baselines' incremental token count) changes nothing a run writes.
# CPU only, no model: the recording fake server (as lean-client-check.sh), one plain-agent Harbor job on a small
# sparse-memory task with COUNT_MEMO=0 and with 1 (same hash seed): every request body, the trajectory, every
# context snapshot and the grader's output identical. Exit 0 only if everything matches.
set -uo pipefail
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
V=${VENV:-/mnt/fast-ai/venvs/clm}/bin/python
O=${1:?usage: count-memo-check.sh <out_dir>}
PORT=${PORT:-18236}
mkdir -p "$O"; cd "$HERE"
fail=0
fake() { FAKE_VLLM_SHAPE=1 FAKE_DETERMINISTIC=1 FAKE_REASONING=alt FAKE_TEXTCALL=1 FAKE_BODY_LOG="$1" \
  "$V" fake_openai_server.py "$PORT" > "$1.server.log" 2>&1 & FP=$!; sleep 1; }
T=$O/tasks/sparse-memory-b8-s0
[[ -d $T ]] || "$V" make_sparse_prose_tasks.py "$O/tasks" --n-batches 8 --density 3 --words --probes-every 2 --probes-k 3 \
  --rules --mode memory --batch-tokens 600 --seeds 0 > /dev/null
for v in 0 1; do
  rm -rf "$O/runs-$v"; rm -f "$O/job-bodies-$v.jsonl"; fake "$O/job-bodies-$v.jsonl"
  /usr/bin/time -o "$O/job-$v.time" -f "%e %M" env COUNT_MEMO=$v LEAN_CLIENT=1 PYTHONHASHSEED=7 TASKS="$T" JOB_NAME=job-$v \
    CONTEXT_BUDGET=0 DROP_OLD_THINKING=0 ENABLE_THINKING=true MAX_TOKENS=8192 TEMPERATURE=0 TASK_TEMPLATE=open_problems \
    API_BASE="http://127.0.0.1:$PORT/v1" MODEL_NAME=qwen38-27b-fp8 EXTRA_KWARGS=emit_ctx_trajectory=false \
    ./run-context-job.sh plain "$O/runs-$v" > "$O/job-$v.out" 2>&1 || { echo "job memo=$v failed"; fail=1; }
  kill $FP; wait $FP 2>/dev/null
done
cmp -s "$O/job-bodies-0.jsonl" "$O/job-bodies-1.jsonl" \
  && echo "job: request bodies identical ($(wc -l < "$O/job-bodies-0.jsonl"))" || { echo "job: REQUEST BODIES DIFFER"; fail=1; }
for f in agent/trajectory.json agent/usage.json verifier/test-stdout.txt verifier/reward.txt; do
  a=$(ls "$O"/runs-0/jobs/job-0/*/$f 2>/dev/null); b=$(ls "$O"/runs-1/jobs/job-1/*/$f 2>/dev/null)
  [[ -n $a && -n $b ]] && cmp -s "$a" "$b" && echo "job: $f identical" || { echo "job: $f DIFFERS or missing"; fail=1; }
done
a=$(ls -d "$O"/runs-0/jobs/job-0/*/agent/context_snapshots 2>/dev/null); b=$(ls -d "$O"/runs-1/jobs/job-1/*/agent/context_snapshots 2>/dev/null)
if [[ -n $a && -n $b ]] && diff -rq "$a" "$b" > /dev/null; then echo "job: context_snapshots identical ($(ls "$a" | wc -l) files)"
else echo "job: context_snapshots DIFFER or missing"; fail=1; fi
echo "job wall s and peak KiB: memo=0 $(cat "$O/job-0.time"); memo=1 $(cat "$O/job-1.time")"
(( fail )) && echo "COUNT MEMO CHECK FAILED" || echo "COUNT MEMO CHECK PASSED"
exit $fail
