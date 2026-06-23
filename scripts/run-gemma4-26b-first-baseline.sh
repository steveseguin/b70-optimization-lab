#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GPU_INDEX="${GPU_INDEX:-0}"
PORT="${PORT:-18260}"
BASE_URL="${BASE_URL:-http://127.0.0.1:${PORT}}"
MODEL_ALIAS="${MODEL_ALIAS:-gemma4-26b-a4b-q8}"
CTX_SIZE="${CTX_SIZE:-8192}"
UBATCH_SIZE="${UBATCH_SIZE:-64}"
CANARY_REPEATS="${CANARY_REPEATS:-32}"
BENCH_REPEATS="${BENCH_REPEATS:-8}"
PROMPT_TOKENS="${PROMPT_TOKENS:-512}"
MAX_TOKENS="${MAX_TOKENS:-512}"
READINESS_TIMEOUT_S="${READINESS_TIMEOUT_S:-900}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
LABEL="${LABEL:-gemma4-26b-q8-llamacpp-gpu${GPU_INDEX}-ctx${CTX_SIZE}-${STAMP}}"
RUN_DIR="${RUN_DIR:-$ROOT/data/$LABEL}"
SERVER_OUT_DIR="${SERVER_OUT_DIR:-/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers}"
SERVER_LOG="$SERVER_OUT_DIR/${LABEL}.server.log"
SUMMARY_OUT="$RUN_DIR/summary.json"

mkdir -p "$RUN_DIR" "$SERVER_OUT_DIR"

server_pid=""
cleanup() {
  if [[ -n "$server_pid" ]]; then
    kill "$server_pid" 2>/dev/null || true
    wait "$server_pid" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

cd "$ROOT"

echo "[gemma4-baseline] label=$LABEL"
echo "[gemma4-baseline] base_url=$BASE_URL"
echo "[gemma4-baseline] server_log=$SERVER_LOG"

GPU_INDEX="$GPU_INDEX" \
PORT="$PORT" \
MODEL_ALIAS="$MODEL_ALIAS" \
CTX_SIZE="$CTX_SIZE" \
UBATCH_SIZE="$UBATCH_SIZE" \
LOG="$SERVER_LOG" \
scripts/run-gemma4-26b-llamacpp-replica.sh &
server_pid="$!"

deadline=$((SECONDS + READINESS_TIMEOUT_S))
until curl -fsS "$BASE_URL/v1/models" > "$RUN_DIR/models.json" 2> /dev/null; do
  if (( SECONDS >= deadline )); then
    echo "[gemma4-baseline] server did not become ready after ${READINESS_TIMEOUT_S}s" >&2
    tail -80 "$SERVER_LOG" >&2 || true
    exit 1
  fi
  if ! kill -0 "$server_pid" 2>/dev/null; then
    echo "[gemma4-baseline] server exited before readiness" >&2
    tail -80 "$SERVER_LOG" >&2 || true
    exit 1
  fi
  sleep 5
done

echo "[gemma4-baseline] server ready"

python3 scripts/gemma4-text-canary.py \
  --base-url "$BASE_URL" \
  --model "$MODEL_ALIAS" \
  --api-mode chat \
  --repeats "$CANARY_REPEATS" \
  --out "$RUN_DIR/chat-canary.json"

python3 scripts/bench-openai-single-decode.py \
  --base-url "$BASE_URL" \
  --model "$MODEL_ALIAS" \
  --api-mode chat \
  --prompt-tokens "$PROMPT_TOKENS" \
  --max-tokens "$MAX_TOKENS" \
  --repeats "$BENCH_REPEATS" \
  --out "$RUN_DIR/p${PROMPT_TOKENS}o${MAX_TOKENS}.json"

python3 - "$RUN_DIR" "$LABEL" "$SERVER_LOG" "$SUMMARY_OUT" <<'PY'
import json
import sys
from pathlib import Path

run_dir = Path(sys.argv[1])
label = sys.argv[2]
server_log = sys.argv[3]
summary_out = Path(sys.argv[4])
canary = json.loads((run_dir / "chat-canary.json").read_text())
bench = json.loads(next(run_dir.glob("p*o*.json")).read_text())
out = {
    "label": label,
    "server_log": server_log,
    "run_dir": str(run_dir),
    "canary_pass_all": canary["summary"]["pass_all"],
    "canary_rows_completed": canary["summary"]["rows_completed"],
    "bench_summary": bench["summary"],
    "bench_run_identity": bench["run_identity"],
}
summary_out.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
print(json.dumps(out, indent=2, sort_keys=True))
PY

echo "[gemma4-baseline] summary=$SUMMARY_OUT"
