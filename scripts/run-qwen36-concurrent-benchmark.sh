#!/usr/bin/env bash
set -uo pipefail

LABEL="${1:-concurrent-fast-conservative}"
ROOT="${ROOT:-/home/steve/llm-optimizations}"
DATA_DIR="${DATA_DIR:-$ROOT/data}"
PYTHON="${PYTHON:-/home/steve/.venvs/vllm-xpu/bin/python}"
PORT="${PORT:-18080}"
BASE_URL="${BASE_URL:-http://127.0.0.1:$PORT}"
STAMP="${STAMP:-$(date -u +%Y%m%d%H%M%S)}"
CACHE_LABEL="${CACHE_LABEL:-qwen36-ablation-$LABEL}"
LOG_PATH="${LOG_PATH:-$DATA_DIR/qwen36-ablation-$LABEL-$STAMP.log}"
OUT_JSON="${OUT_JSON:-$DATA_DIR/qwen36-ablation-$LABEL-concurrent-$STAMP.json}"

CONCURRENCY="${CONCURRENCY:-4}"
REPEATS="${REPEATS:-2}"
MAX_TOKENS="${MAX_TOKENS:-512}"
READINESS_TIMEOUT_S="${READINESS_TIMEOUT_S:-1800}"

mkdir -p "$DATA_DIR"

export MODEL_PATH
export PORT
export LOG_PATH
export TORCHINDUCTOR_CACHE_DIR="${TORCHINDUCTOR_CACHE_DIR:-/mnt/fast-ai/vllm-cache-exp/$CACHE_LABEL/torchinductor}"
export VLLM_CACHE_ROOT="${VLLM_CACHE_ROOT:-/mnt/fast-ai/vllm-cache-exp/$CACHE_LABEL/vllm}"

SERVER_PID=""

cleanup() {
  local status=$?
  if [[ -n "$SERVER_PID" ]] && kill -0 "$SERVER_PID" 2>/dev/null; then
    kill -INT "$SERVER_PID" 2>/dev/null || true
    for _ in $(seq 1 60); do
      if ! kill -0 "$SERVER_PID" 2>/dev/null; then
        break
      fi
      sleep 1
    done
    if kill -0 "$SERVER_PID" 2>/dev/null; then
      kill -TERM "$SERVER_PID" 2>/dev/null || true
    fi
    wait "$SERVER_PID" 2>/dev/null || true
  fi
  exit "$status"
}
trap cleanup EXIT INT TERM

check_ready() {
  "$PYTHON" - "$BASE_URL" <<'PY'
import json
import sys
import urllib.request

base_url = sys.argv[1].rstrip("/")
try:
    with urllib.request.urlopen(base_url + "/v1/models", timeout=5) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if data.get("data"):
        raise SystemExit(0)
except Exception:
    pass
raise SystemExit(1)
PY
}

echo "[concurrent:$LABEL] stamp=$STAMP"
echo "[concurrent:$LABEL] log=$LOG_PATH"
echo "[concurrent:$LABEL] cache=$CACHE_LABEL"

"$ROOT/scripts/launch-qwen36-quark-int8-accepted.sh" &
SERVER_PID=$!

ready=0
for elapsed in $(seq 1 "$READINESS_TIMEOUT_S"); do
  if ! kill -0 "$SERVER_PID" 2>/dev/null; then
    echo "[concurrent:$LABEL] server exited before readiness" >&2
    tail -n 120 "$LOG_PATH" >&2 || true
    exit 1
  fi
  if check_ready; then
    ready=1
    echo "[concurrent:$LABEL] server ready after ${elapsed}s"
    break
  fi
  sleep 1
done

if [[ "$ready" != "1" ]]; then
  echo "[concurrent:$LABEL] server did not become ready" >&2
  tail -n 120 "$LOG_PATH" >&2 || true
  exit 1
fi

"$PYTHON" "$ROOT/scripts/benchmark-concurrent-completions.py" \
  --base-url "$BASE_URL" \
  --concurrency "$CONCURRENCY" \
  --repeats "$REPEATS" \
  --max-tokens "$MAX_TOKENS" \
  --timeout 600 \
  --out "$OUT_JSON"
rc=$?

echo "[concurrent:$LABEL] benchmark rc=$rc"
echo "[concurrent:$LABEL] out=$OUT_JSON"
exit "$rc"
