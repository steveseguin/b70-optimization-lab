#!/usr/bin/env bash
# run-freeagent-job.sh <task_dir> <out_dir> <job_name> — one freeagent run on a repair-marathon task:
# builds the task image if needed, starts the capped container, runs the agent (API_BASE selects the
# model endpoint: the research server directly, or the ctxkeeper proxy in front of it), then grades
# with the task's own tests/grade.py. Layout matches the harness jobs (agent/, verifier/).
set -uo pipefail
TASK=${1:?usage: run-freeagent-job.sh TASK_DIR OUT_DIR JOB_NAME}
OUT=${2:?}; JOB=${3:?}
MODEL_NAME=${MODEL_NAME:-qwen38-27b-fp8}
API_BASE=${API_BASE:?set API_BASE}
TIME_LIMIT=${TIME_LIMIT:-3300}
MAX_STEPS=${MAX_STEPS:-900}
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
IMG=freeagent-$(basename "$TASK")
C="repair-$JOB"
T0=$SECONDS

say() { echo "### $(date +%H:%M:%S) $*"; }
docker image inspect "$IMG" >/dev/null 2>&1 || docker build -q -t "$IMG" "$TASK/environment" >/dev/null
docker rm -f "$C" >/dev/null 2>&1 || true
docker run -d --name "$C" --network none --memory 256m --memory-swap 256m --cpus 2 "$IMG" sleep infinity >/dev/null
say "container $C up; agent starts (time limit ${TIME_LIMIT}s)"
mkdir -p "$OUT/jobs/$JOB/trial"
python3 "$HERE/freeagent.py" --api-base "$API_BASE" --model "$MODEL_NAME" --container "$C" \
  --instruction "$TASK/instruction.md" --out "$OUT/jobs/$JOB/trial" \
  --max-steps "$MAX_STEPS" --time-limit "$TIME_LIMIT" 2>&1 | tail -2
say "agent done in $(( (SECONDS-T0)/60 )) min $(( (SECONDS-T0)%60 )) s; grading"
docker cp "$TASK/tests/." "$C:/tests/"
docker exec "$C" mkdir -p /logs/verifier
mkdir -p "$OUT/jobs/$JOB/trial/verifier"
docker exec "$C" python3 /tests/grade.py 2>&1 | tee "$OUT/jobs/$JOB/trial/verifier/test-stdout.txt" | grep 'repair score' || true
docker cp "$C:/logs/verifier/." "$OUT/jobs/$JOB/trial/verifier/" 2>/dev/null || true
docker rm -f "$C" >/dev/null 2>&1 || true
say "job $JOB complete"
