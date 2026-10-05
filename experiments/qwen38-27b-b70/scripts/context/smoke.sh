#!/usr/bin/env bash
# Cheapest end-to-end check: one tiny kvstream task (1 batch of 8 SETs, 3 GETs; ~1k tokens of
# data, ~4-8 LM calls per agent) for each agent in AGENTS [clm summary plain].
#
#   API_BASE=http://127.0.0.1:8000/v1 smoke.sh <out_dir>      # against a real server
#   STUB=1 smoke.sh <out_dir>                                 # against fake_openai_server.py
#
# STUB=1 starts the fake server on a free port, points API_BASE at it, and kills it (by pid)
# on exit. The stub's scripted replies exercise wiring only; its score is meaningless.
set -euo pipefail
OUT_DIR=${1:?usage: smoke.sh <out_dir>}
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PY=${VENV:-/mnt/fast-ai/venvs/clm}/bin/python
mkdir -p "$OUT_DIR"
OUT_DIR=$(cd "$OUT_DIR" && pwd)

"$PY" "$HERE/make_kvstream_tasks.py" "$OUT_DIR/tasks" --smoke >/dev/null

STUB_PID=
cleanup() { [[ -n "$STUB_PID" ]] && kill "$STUB_PID" 2>/dev/null && echo "stub $STUB_PID stopped"; true; }
trap cleanup EXIT
if [[ "${STUB:-0}" == 1 ]]; then
  PORT=$("$PY" -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1])')
  "$PY" "$HERE/fake_openai_server.py" "$PORT" > "$OUT_DIR/stub.log" 2>&1 &
  STUB_PID=$!
  for _ in $(seq 50); do curl -sf "http://127.0.0.1:$PORT/v1/models" >/dev/null && break; sleep 0.1; done
  export API_BASE="http://127.0.0.1:$PORT/v1"
  echo "stub pid $STUB_PID at $API_BASE"
fi

export TASKS="$OUT_DIR/tasks/kvstream-smoke"
export MAX_STEPS=${MAX_STEPS:-12}
rc=0
for a in ${AGENTS:-clm summary plain}; do
  JOB_NAME="smoke-$a-$(date +%Y%m%d-%H%M%S)" "$HERE/run-context-job.sh" "$a" "$OUT_DIR" || rc=$?
done
exit $rc
