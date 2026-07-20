#!/usr/bin/env bash
set -euo pipefail

root=/home/steve/llm-optimizations
launcher="${root}/experiments/deepseek-v4-flash-reap-xpu-b70/scripts/serve-k160-eagle-training-capture.sh"
replay="${root}/experiments/deepseek-v4-flash-reap-xpu-b70/scripts/replay-k160-eagle-signal-corpus.py"
python=/home/steve/.venvs/deepseek-v4-xpu/bin/python

: "${EAGLE_CAPTURE_ROOT:?set EAGLE_CAPTURE_ROOT}"
: "${EAGLE_CAPTURE_NAMESPACE:?set EAGLE_CAPTURE_NAMESPACE}"
: "${EAGLE_TRAJECTORIES:?set EAGLE_TRAJECTORIES}"
: "${EAGLE_REPLAY_OUTPUT:?set EAGLE_REPLAY_OUTPUT}"
: "${EAGLE_RUN_PREFIX:?set EAGLE_RUN_PREFIX}"

arm_file="${EAGLE_CAPTURE_ARM_FILE:-${EAGLE_CAPTURE_ROOT}/${EAGLE_CAPTURE_NAMESPACE}.arm}"
rank_dir="${EAGLE_CAPTURE_ROOT}/${EAGLE_CAPTURE_NAMESPACE}/rank-000"
first_cycle="${EAGLE_RESTART_START:-0}"
max_cycles="${EAGLE_MAX_RESTARTS:-40}"
request_timeout="${EAGLE_REQUEST_TIMEOUT:-90}"
server_pid=

stop_server() {
  if [[ -n "${server_pid}" ]] && kill -0 "${server_pid}" 2>/dev/null; then
    if kill -0 -- "-${server_pid}" 2>/dev/null; then
      kill -INT -- "-${server_pid}" 2>/dev/null || true
    else
      kill -INT "${server_pid}" 2>/dev/null || true
    fi
    for _ in $(seq 1 30); do
      if ! kill -0 "${server_pid}" 2>/dev/null; then
        break
      fi
      sleep 1
    done
    if kill -0 "${server_pid}" 2>/dev/null; then
      if kill -0 -- "-${server_pid}" 2>/dev/null; then
        kill -TERM -- "-${server_pid}" 2>/dev/null || true
      else
        kill -TERM "${server_pid}" 2>/dev/null || true
      fi
      for _ in $(seq 1 10); do
        if ! kill -0 "${server_pid}" 2>/dev/null; then
          break
        fi
        sleep 1
      done
    fi
    if kill -0 "${server_pid}" 2>/dev/null; then
      if kill -0 -- "-${server_pid}" 2>/dev/null; then
        kill -KILL -- "-${server_pid}" 2>/dev/null || true
      else
        kill -KILL "${server_pid}" 2>/dev/null || true
      fi
    fi
  fi
  if [[ -n "${server_pid}" ]]; then
    wait "${server_pid}" 2>/dev/null || true
  fi
  server_pid=
}

trap stop_server EXIT INT TERM

for ((cycle = first_cycle; cycle < first_cycle + max_cycles; cycle++)); do
  if [[ -e "${arm_file}" ]]; then
    printf 'capture arm file survived a prior transaction: %s\n' "${arm_file}" >&2
    exit 2
  fi
  run_dir="${EAGLE_RUN_PREFIX}-restart$(printf '%02d' "${cycle}")"
  if [[ -e "${run_dir}" ]]; then
    printf 'refusing to reuse run directory: %s\n' "${run_dir}" >&2
    exit 2
  fi
  mkdir -p "${run_dir}"

  setsid env \
    RUN_DIR="${run_dir}" \
    VLLM_XPU_EAGLE_TRAINING_CAPTURE_DIR="${EAGLE_CAPTURE_ROOT}" \
    VLLM_XPU_EAGLE_TRAINING_CAPTURE_NAMESPACE="${EAGLE_CAPTURE_NAMESPACE}" \
    VLLM_XPU_EAGLE_TRAINING_CAPTURE_ALL_RANKS=0 \
    VLLM_XPU_EAGLE_TRAINING_CAPTURE_ARM_FILE="${arm_file}" \
    CAPTURE_GRAPH_MODE="${EAGLE_CAPTURE_GRAPH_MODE:-eager}" \
    "${launcher}" >"${run_dir}/supervisor-server.stdout.log" 2>&1 &
  server_pid=$!

  ready=0
  for _ in $(seq 1 90); do
    if curl -fsS --max-time 2 http://127.0.0.1:18080/health >/dev/null 2>&1; then
      ready=1
      break
    fi
    if ! kill -0 "${server_pid}" 2>/dev/null; then
      break
    fi
    sleep 2
  done
  if [[ "${ready}" != 1 ]]; then
    printf 'capture server failed readiness: %s\n' "${run_dir}" >&2
    exit 2
  fi

  replay_args=(
    "${python}" "${replay}"
    --trajectories "${EAGLE_TRAJECTORIES}"
    --arm-file "${arm_file}"
    --capture-rank-dir "${rank_dir}"
    --output "${EAGLE_REPLAY_OUTPUT}"
    --timeout "${request_timeout}"
    --max-model-len 2048
    --max-num-batched-tokens 2048
  )
  if [[ -e "${EAGLE_REPLAY_OUTPUT}" ]]; then
    replay_args+=(--resume)
  fi

  set +e
  "${replay_args[@]}" >"${run_dir}/replay.stdout.log" 2>&1
  replay_status=$?
  set -e
  stop_server
  if [[ -e "${arm_file}" ]]; then
    printf 'replay failed to clean arm file: %s\n' "${arm_file}" >&2
    exit 2
  fi

  cursor=0
  if [[ -e "${EAGLE_REPLAY_OUTPUT}" ]]; then
    cursor="$(wc -l <"${EAGLE_REPLAY_OUTPUT}")"
  fi
  printf '{"cycle":%d,"replay_status":%d,"durable_cursor":%d,"run_dir":"%s"}\n' \
    "${cycle}" "${replay_status}" "${cursor}" "${run_dir}"
  if [[ "${replay_status}" == 0 ]]; then
    exit 0
  fi
done

printf 'capture replay exhausted %d restart cycles\n' "${max_cycles}" >&2
exit 1
