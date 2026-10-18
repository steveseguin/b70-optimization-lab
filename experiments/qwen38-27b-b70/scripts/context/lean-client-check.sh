#!/usr/bin/env bash
# Check that LEAN_CLIENT=1 (lean_litellm/, the ~20 MB stand-in for litellm) changes nothing a server can see.
# CPU only, no model: a recording fake server in the served vLLM 0.29 reply shape (fake_openai_server.py,
# FAKE_VLLM_SHAPE=1 FAKE_DETERMINISTIC=1 FAKE_REASONING=alt FAKE_TEXTCALL=1 FAKE_BODY_LOG=...).
#   1. lean_client_probe.py under three hash seeds, each with real litellm and with the stand-in: every request body
#      byte-identical, and the same message.model_dump(), usage fields and error classes.
#   2. one plain-agent Harbor job on a small sparse-memory task with each client (same hash seed): every request body,
#      the saved trajectory and the grader's output identical; prints each client's peak memory.
# litellm orders a reply's provider_specific_fields by PYTHONHASHSEED (a set difference); the stand-in does the same,
# so the comparison fixes the seed. Exit 0 only if everything matches.
set -uo pipefail
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
V=${VENV:-/mnt/fast-ai/venvs/clm}/bin/python
O=${1:?usage: lean-client-check.sh <out_dir>}
PORT=${PORT:-18235}
mkdir -p "$O"; cd "$HERE"
fail=0
fake() { FAKE_VLLM_SHAPE=1 FAKE_DETERMINISTIC=1 FAKE_REASONING=alt FAKE_TEXTCALL=1 FAKE_BODY_LOG="$1" \
  "$V" fake_openai_server.py "$PORT" > "$1.server.log" 2>&1 & FP=$!; sleep 1; }
for seed in 1 2 3; do
  for v in real lean; do
    rm -f "$O/probe-bodies-$v-$seed.jsonl"; fake "$O/probe-bodies-$v-$seed.jsonl"
    PP=; [[ $v == lean ]] && PP=$HERE/lean_litellm
    OPENAI_API_KEY=EMPTY PYTHONHASHSEED=$seed PYTHONPATH=$PP "$V" lean_client_probe.py "http://127.0.0.1:$PORT/v1" \
      "http://127.0.0.1:$PORT" "$O/probe-$v-$seed.json" > "$O/probe-$v-$seed.log" 2>&1 || { echo "probe $v seed $seed failed"; fail=1; }
    kill $FP; wait $FP 2>/dev/null
  done
  cmp -s "$O/probe-bodies-real-$seed.jsonl" "$O/probe-bodies-lean-$seed.jsonl" \
    && echo "probe seed $seed: request bodies identical ($(wc -l < "$O/probe-bodies-real-$seed.jsonl"))" \
    || { echo "probe seed $seed: REQUEST BODIES DIFFER"; fail=1; }
  "$V" - "$O/probe-real-$seed.json" "$O/probe-lean-$seed.json" <<'PY' || fail=1
import json, sys
a, b = (json.load(open(p)) for p in sys.argv[1:])
assert a.pop("lean") is False and b.pop("lean") is True, "the stand-in was not (or was always) imported"
print(f"probe: responses and errors {'identical' if a == b else 'DIFFER'}")
sys.exit(0 if a == b else 1)
PY
done
T=$O/tasks/sparse-memory-b8-s0
[[ -d $T ]] || "$V" make_sparse_prose_tasks.py "$O/tasks" --n-batches 8 --density 3 --words --probes-every 2 --probes-k 3 \
  --rules --mode memory --batch-tokens 600 --seeds 0 > /dev/null
for v in real lean; do
  rm -rf "$O/runs-$v"; rm -f "$O/job-bodies-$v.jsonl"; fake "$O/job-bodies-$v.jsonl"
  L=0; [[ $v == lean ]] && L=1
  /usr/bin/time -o "$O/job-$v.time" -f "%M" env LEAN_CLIENT=$L PYTHONHASHSEED=7 TASKS="$T" JOB_NAME=job-$v CONTEXT_BUDGET=0 \
    DROP_OLD_THINKING=0 ENABLE_THINKING=true MAX_TOKENS=8192 TEMPERATURE=0 TASK_TEMPLATE=open_problems \
    API_BASE="http://127.0.0.1:$PORT/v1" MODEL_NAME=qwen38-27b-fp8 EXTRA_KWARGS=emit_ctx_trajectory=false \
    ./run-context-job.sh plain "$O/runs-$v" > "$O/job-$v.out" 2>&1 || { echo "job $v failed"; fail=1; }
  kill $FP; wait $FP 2>/dev/null
done
cmp -s "$O/job-bodies-real.jsonl" "$O/job-bodies-lean.jsonl" \
  && echo "job: request bodies identical ($(wc -l < "$O/job-bodies-real.jsonl"))" || { echo "job: REQUEST BODIES DIFFER"; fail=1; }
for f in agent/trajectory.json verifier/test-stdout.txt verifier/reward.txt; do
  a=$(ls "$O"/runs-real/jobs/job-real/*/$f 2>/dev/null); b=$(ls "$O"/runs-lean/jobs/job-lean/*/$f 2>/dev/null)
  [[ -n $a && -n $b ]] && cmp -s "$a" "$b" && echo "job: $f identical" || { echo "job: $f DIFFERS or missing"; fail=1; }
done
echo "client peak memory: litellm $(( $(cat "$O/job-real.time") / 1024 )) MiB, lean $(( $(cat "$O/job-lean.time") / 1024 )) MiB"
(( fail )) && echo "LEAN CLIENT CHECK FAILED" || echo "LEAN CLIENT CHECK PASSED"
exit $fail
