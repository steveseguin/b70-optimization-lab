#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG="${CONFIG:-$ROOT/experiments/qwen27-dflash-sycl-b70/harness/workers.json}"
OUT_ROOT="${OUT_ROOT:-$ROOT/data/qwen27-tp1-fourway-calibration}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_DIR="$OUT_ROOT/$STAMP"
READINESS_TIMEOUT_S="${READINESS_TIMEOUT_S:-300}"
mapfile -t ports < <(python3 -c 'import json,sys; print(*[w["port"] for w in json.load(open(sys.argv[1]))["workers"]], sep="\n")' "$CONFIG")

mkdir -p "$RUN_DIR"

cleanup() {
  python3 "$ROOT/scripts/qwen27-tp1-workerctl.py" stop \
    --config "$CONFIG" --execute >> "$RUN_DIR/controller-stop.log" 2>&1 || true
}
trap cleanup EXIT

python3 "$ROOT/scripts/qwen27-tp1-workerctl.py" validate --config "$CONFIG"
python3 "$ROOT/scripts/qwen27-tp1-workerctl.py" status --config "$CONFIG" --json \
  > "$RUN_DIR/status-before.json"
python3 "$ROOT/scripts/qwen27-tp1-workerctl.py" start --config "$CONFIG" --execute \
  > "$RUN_DIR/controller-start.log" 2>&1

deadline=$((SECONDS + READINESS_TIMEOUT_S))
for port in "${ports[@]}"; do
  until curl -fsS "http://127.0.0.1:${port}/v1/models" \
      > "$RUN_DIR/models-${port}.json" 2> "$RUN_DIR/models-${port}.err"; do
    if (( SECONDS >= deadline )); then
      echo "timed out waiting for port $port" >&2
      exit 1
    fi
    sleep 2
  done
done

pids=()
index=0
for port in "${ports[@]}"; do
  out="$RUN_DIR/gpu${index}-mtp3.json"
  BASE_URL="http://127.0.0.1:${port}" \
  MODEL="qwen36-27b-q4_0-tp1" \
  LABEL="fourway-calibration-gpu${index}-mtp3" \
  OUT="$out" \
  REQUEST_EXTRA_JSON='{"cache_prompt":false}' \
    "$ROOT/scripts/bench-qwen36-27b-mtp-gguf-realistic.sh" \
      > "$RUN_DIR/gpu${index}-bench.log" 2>&1 &
  pids+=("$!")
  index=$((index + 1))
done

status=0
for pid in "${pids[@]}"; do
  if ! wait "$pid"; then
    status=1
  fi
done

python3 "$ROOT/scripts/qwen27-tp1-workerctl.py" status --config "$CONFIG" --json \
  > "$RUN_DIR/status-after.json"

if (( status != 0 )); then
  echo "one or more calibration workers failed; see $RUN_DIR" >&2
  exit "$status"
fi

echo "$RUN_DIR"
