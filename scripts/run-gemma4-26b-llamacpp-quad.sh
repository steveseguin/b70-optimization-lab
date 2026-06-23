#!/usr/bin/env bash
set -euo pipefail

BASE_PORT="${BASE_PORT:-18260}"
OUT_DIR="${OUT_DIR:-/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers}"
PID_DIR="${PID_DIR:-$OUT_DIR/pids}"
mkdir -p "$PID_DIR"

for gpu in 0 1 2 3; do
  port=$((BASE_PORT + gpu))
  echo "starting Gemma 4 26B Q8 replica: gpu=$gpu port=$port"
  (
    cd "$(dirname "$0")/.."
    GPU_INDEX="$gpu" PORT="$port" OUT_DIR="$OUT_DIR" \
      scripts/run-gemma4-26b-llamacpp-replica.sh
  ) &
  echo "$!" > "$PID_DIR/gpu${gpu}-port${port}.pid"
done

echo "PID files: $PID_DIR"
echo "Use: xargs -r kill < <(cat $PID_DIR/*.pid)"
wait
