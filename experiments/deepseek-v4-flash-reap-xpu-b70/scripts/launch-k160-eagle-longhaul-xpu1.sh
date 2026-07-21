#!/usr/bin/env bash
set -euo pipefail

root=/home/steve/llm-optimizations
python=/home/steve/.venvs/deepseek-v4-xpu/bin/python
worker="${root}/experiments/deepseek-v4-flash-reap-xpu-b70/scripts/train-k160-eagle-longhaul.py"
config="${root}/experiments/deepseek-v4-flash-reap-xpu-b70/configs/k160-eagle-longhaul-xpu1.env"
artifact_root=/media/steve/CorsairExternal/llm-optimization-artifacts/deepseek-v4-eagle-signal-20260719T210100Z/training

usage() {
  echo "usage: RUN_DIR=/absolute/run/path $0 [--foreground]" >&2
}

mode=detached
if [[ ${1:-} == --foreground ]]; then
  mode=foreground
  shift
fi
if (($#)); then
  usage
  exit 2
fi

if [[ -z ${RUN_DIR:-} ]]; then
  run_stamp=$(date -u +%Y%m%dT%H%M%SZ)
  RUN_DIR="${artifact_root}/single-card-longhaul-${run_stamp}"
fi
if [[ ${RUN_DIR} != /* ]]; then
  echo "RUN_DIR must be absolute" >&2
  exit 2
fi
export RUN_DIR

if [[ ${mode} == detached ]]; then
  mkdir -p "${RUN_DIR}"
  if [[ -e ${RUN_DIR}/STOP ]]; then
    echo "refusing to launch while STOP exists: ${RUN_DIR}/STOP" >&2
    exit 2
  fi
  exec 7>"${RUN_DIR}/supervisor.lock"
  if ! flock -n 7; then
    echo "another long-haul supervisor holds ${RUN_DIR}/supervisor.lock" >&2
    exit 73
  fi
  flock -u 7
  nohup setsid "$0" --foreground >>"${RUN_DIR}/supervisor.log" 2>&1 </dev/null &
  supervisor_pid=$!
  ready=false
  for _ in {1..100}; do
    if [[ -s ${RUN_DIR}/supervisor.pid ]] \
      && [[ $(<"${RUN_DIR}/supervisor.pid") == "${supervisor_pid}" ]] \
      && kill -0 "${supervisor_pid}" 2>/dev/null; then
      ready=true
      break
    fi
    sleep 0.1
  done
  if [[ ${ready} != true ]]; then
    echo "detached supervisor failed readiness; see ${RUN_DIR}/supervisor.log" >&2
    exit 1
  fi
  printf 'RUN_DIR=%s\nSUPERVISOR_PID=%s\nMETRICS=%s\nSTOP=%s\n' \
    "${RUN_DIR}" "${supervisor_pid}" "${RUN_DIR}/metrics.jsonl" "${RUN_DIR}/STOP"
  exit 0
fi

mkdir -p "${RUN_DIR}"
exec 9>"${RUN_DIR}/supervisor.lock"
if ! flock -n 9; then
  echo "another long-haul supervisor holds ${RUN_DIR}/supervisor.lock" >&2
  exit 73
fi
global_lock=/run/user/$(id -u)/k160-eagle-xpu1-longhaul.lock
exec 8>"${global_lock}"
if ! flock -n 8; then
  echo "another process holds the global XPU-1 long-haul lock: ${global_lock}" >&2
  exit 73
fi
printf '%s\n' "$$" >"${RUN_DIR}/supervisor.pid"

if [[ -e ${RUN_DIR}/STOP ]]; then
  echo "STOP already exists; exiting without a worker"
  exit 0
fi

# shellcheck disable=SC1090
source "${config}"
set +u
source /opt/intel/oneapi/compiler/2025.3/env/vars.sh --force >/dev/null 2>&1
source /opt/intel/oneapi/mkl/2025.3/env/vars.sh --force >/dev/null 2>&1
source /opt/intel/oneapi/dnnl/2025.3/env/vars.sh --force >/dev/null 2>&1
set -u

for name in $(compgen -v); do
  if [[ ${name} == CCL_* ]]; then
    unset "${name}"
  fi
done
unset LOCAL_RANK RANK WORLD_SIZE MASTER_ADDR MASTER_PORT LD_PRELOAD
export ZE_AFFINITY_MASK=1
export ONEAPI_DEVICE_SELECTOR='level_zero:*'
export OMP_NUM_THREADS=1

test -x "${python}"
test -f "${worker}"
test -f "${WARM_START_CHECKPOINT}"
test -d "${MODEL_ROOT}"
test -d "${TRAIN_DATA_DIR}"
test -d "${DEV_DATA_DIR}"
test -f "${TRAIN_CAPTURE_VALIDATION}"
test -f "${DEV_CAPTURE_VALIDATION}"
test -f "${DEV_REQUEST_MANIFEST}"
test -f "${DEV_REPLAY_MANIFEST}"
test -e /sys/bus/pci/devices/0000:27:00.0/drm/renderD131

worker_args=(
  "${worker}"
  --train-data-dir "${TRAIN_DATA_DIR}"
  --train-capture-validation "${TRAIN_CAPTURE_VALIDATION}"
  --dev-data-dir "${DEV_DATA_DIR}"
  --dev-capture-validation "${DEV_CAPTURE_VALIDATION}"
  --dev-request-manifest "${DEV_REQUEST_MANIFEST}"
  --dev-replay-manifest "${DEV_REPLAY_MANIFEST}"
  --model-root "${MODEL_ROOT}"
  --output-dir "${RUN_DIR}"
  --warm-start-checkpoint "${WARM_START_CHECKPOINT}"
  --initial-global-step "${INITIAL_GLOBAL_STEP}"
  --initial-anchors "${INITIAL_ANCHORS}"
  --anchors-per-epoch "${ANCHORS_PER_EPOCH}"
  --additional-steps "${ADDITIONAL_STEPS}"
  --checkpoint-every "${CHECKPOINT_EVERY}"
  --microbatch "${MICROBATCH}"
  --gradient-accumulation "${GRADIENT_ACCUMULATION}"
  --learning-rate "${LEARNING_RATE}"
  --warmup-fraction "${WARMUP_FRACTION}"
  --minimum-lr-ratio "${MINIMUM_LR_RATIO}"
  --weight-decay "${WEIGHT_DECAY}"
  --step-timeout "${STEP_TIMEOUT}"
  --eval-batch-timeout "${EVAL_BATCH_TIMEOUT}"
  --eval-batch "${EVAL_BATCH}"
  --seed "${SEED}"
)

restart_count=0
worker_pid=
terminate_worker() {
  if [[ -n ${worker_pid} ]] && kill -0 "${worker_pid}" 2>/dev/null; then
    kill -TERM "${worker_pid}" 2>/dev/null || true
    wait "${worker_pid}" 2>/dev/null || true
  fi
  exit 143
}
trap terminate_worker TERM INT HUP
while [[ ! -e ${RUN_DIR}/STOP ]]; do
  "${python}" "${worker_args[@]}" >>"${RUN_DIR}/worker.log" 2>&1 &
  worker_pid=$!
  printf '%s\n' "${worker_pid}" >"${RUN_DIR}/trainer.pid"
  set +e
  wait "${worker_pid}"
  rc=$?
  set -e
  if ((rc == 0)); then
    exit 0
  fi
  restart_count=$((restart_count + 1))
  printf '%s supervisor worker_exit rc=%s restart=%s\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${rc}" "${restart_count}" \
    >>"${RUN_DIR}/supervisor.log"
  if ((restart_count >= 20)); then
    echo "worker failed 20 times; refusing to restart" >&2
    exit "${rc}"
  fi
  sleep 15
done
