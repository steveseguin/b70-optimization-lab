#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_dir"

BASE_PORT="${BASE_PORT:-19350}"
GEMMA4_26B_PROFILE="${GEMMA4_26B_PROFILE:-service}"
HOST="${HOST:-127.0.0.1}"
OUT_DIR="${OUT_DIR:-/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers}"
PID_DIR="${PID_DIR:-$OUT_DIR/quad-pids}"
GPU_INDICES_RAW="${GPU_INDICES:-0 1 2 3}"

read -r -a gpu_indices <<< "$GPU_INDICES_RAW"
if [[ "${#gpu_indices[@]}" -eq 0 ]]; then
  echo "GPU_INDICES must name at least one GPU" >&2
  exit 2
fi

mkdir -p "$PID_DIR"

pids=()
cleanup() {
  trap - INT TERM EXIT
  for pid in "${pids[@]:-}"; do
    kill "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
}
trap cleanup INT TERM EXIT

echo "[gemma4-quad] profile=$GEMMA4_26B_PROFILE host=$HOST base_port=$BASE_PORT gpus=${gpu_indices[*]}"
endpoints=()
for gpu in "${gpu_indices[@]}"; do
  port=$((BASE_PORT + gpu))
  endpoints+=("http://$HOST:$port/v1")
  echo "[gemma4-quad] starting replica gpu=$gpu port=$port"
  (
    cd "$repo_dir"
    GPU_INDEX="$gpu" \
      PORT="$port" \
      HOST="$HOST" \
      GEMMA4_26B_PROFILE="$GEMMA4_26B_PROFILE" \
      OUT_DIR="$OUT_DIR" \
      scripts/serve-gemma4-26b-q8-production.sh
  ) &
  pid="$!"
  pids+=("$pid")
  echo "$pid" > "$PID_DIR/gpu${gpu}-port${port}.pid"
done

echo "[gemma4-quad] pid_dir=$PID_DIR"
echo "[gemma4-quad] endpoints: ${endpoints[*]}"

set +e
wait -n
rc="$?"
set -e
echo "[gemma4-quad] a replica exited rc=$rc; stopping remaining replicas"
cleanup
exit "$rc"
