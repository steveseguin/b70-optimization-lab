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
START_STAGGER_S="${START_STAGGER_S:-6}"

read -r -a gpu_indices <<< "$GPU_INDICES_RAW"
if [[ "${#gpu_indices[@]}" -eq 0 ]]; then
  echo "GPU_INDICES must name at least one GPU" >&2
  exit 2
fi

mkdir -p "$PID_DIR"

gpu_env_value() {
  local base="$1"
  local gpu="$2"
  local default_value="$3"
  local var_name="${base}_GPU${gpu}"
  if [[ -n "${!var_name+x}" ]]; then
    printf '%s\n' "${!var_name}"
  else
    printf '%s\n' "$default_value"
  fi
}

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
for idx in "${!gpu_indices[@]}"; do
  gpu="${gpu_indices[$idx]}"
  port=$((BASE_PORT + gpu))
  gpu_ctx_size="$(gpu_env_value CTX_SIZE "$gpu" "${CTX_SIZE:-32768}")"
  gpu_parallel="$(gpu_env_value PARALLEL "$gpu" "${PARALLEL:-1}")"
  gpu_cache_ram_mib="$(gpu_env_value CACHE_RAM_MIB "$gpu" "${CACHE_RAM_MIB:-0}")"
  endpoints+=("http://$HOST:$port/v1")
  echo "[gemma4-quad] starting replica gpu=$gpu port=$port ctx=$gpu_ctx_size parallel=$gpu_parallel cache_ram_mib=$gpu_cache_ram_mib"
  (
    cd "$repo_dir"
    GPU_INDEX="$gpu" \
      PORT="$port" \
      HOST="$HOST" \
      GEMMA4_26B_PROFILE="$GEMMA4_26B_PROFILE" \
      CTX_SIZE="$gpu_ctx_size" \
      PARALLEL="$gpu_parallel" \
      CACHE_RAM_MIB="$gpu_cache_ram_mib" \
      OUT_DIR="$OUT_DIR" \
      scripts/serve-gemma4-26b-q8-production.sh
  ) &
  pid="$!"
  pids+=("$pid")
  echo "$pid" > "$PID_DIR/gpu${gpu}-port${port}.pid"
  if [[ "$idx" -lt "$((${#gpu_indices[@]} - 1))" && "$START_STAGGER_S" != "0" ]]; then
    sleep "$START_STAGGER_S"
  fi
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
