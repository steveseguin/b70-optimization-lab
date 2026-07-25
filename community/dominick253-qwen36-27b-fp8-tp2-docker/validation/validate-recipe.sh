#!/usr/bin/env bash
# Validate the community PR #9 recipe on the reference B70 lab.
#
# Runs the contributed recipe as faithfully as the host allows, then measures
# single-session decode throughput with bench-recipe.py.
#
# DELIBERATE DEVIATIONS FROM THE CONTRIBUTED COMMAND, all recorded in STATUS.md:
#
#   1. podman (rootless) instead of docker. The host has no docker installed.
#      Equivalent runtime; same pinned image.
#   2. --device=/dev/dri --group-add keep-groups instead of --privileged.
#      The earlier probe proved this is sufficient to drive both B70s, so the
#      recipe's --privileged is not needed and is not granted.
#   3. --host 127.0.0.1 instead of 0.0.0.0. With --net=host the contributed
#      command publishes an unauthenticated endpoint on every interface; this
#      lab will not do that. Loopback only.
#   4. Model mounted from this host's HF cache rather than the contributor's
#      hardcoded /home/dom path, which cannot work for anyone else.
#   5. --shm-size dropped: podman rejects it together with --ipc=host.
#
# Everything else -- quantization, dtype, KV dtype, context length, block size,
# max-num-seqs, memory utilization, eager mode, prefix caching, parsers, and
# the generation config overrides -- is exactly as contributed.

set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGE="docker.io/intel/llm-scaler-vllm:0.21.0-b1"
NAME="pr9-validate-qwen36-27b-fp8"
REV="6a9e13bd6fc8f0983b9b99948120bc37f49c13e9"
# Mount the whole repo dir, not just the snapshot: HF snapshots are symlinks
# into ../../blobs, so mounting the snapshot alone leaves them dangling inside
# the container. This matches the contributed recipe's own mount shape.
REPO="/mnt/fast-ai/llm-cache/hf/models--Qwen--Qwen3.6-27B"
SNAP="${REPO}/snapshots/${REV}"
PORT=8001
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
LOG="${HERE}/validate-${STAMP}.log"

cleanup() {
  echo "--- stopping container ---"
  podman stop -t 30 "${NAME}" >/dev/null 2>&1
  podman rm -f "${NAME}" >/dev/null 2>&1
  echo "--- container removed ---"
}
trap cleanup EXIT

{
  echo "validation run ${STAMP}"
  echo "image:  ${IMAGE}"
  echo "model:  ${SNAP}"
  echo "kernel: $(uname -r)  driver: $(lsmod | awk '/^(xe|i915) /{print $1}')"
  echo

  if [ ! -d "${SNAP}" ]; then
    echo "FATAL: model snapshot not present at ${SNAP}"
    exit 1
  fi
  echo "model files: $(find -L "${SNAP}" -type f | wc -l)"
  echo "model bytes: $(du -sbL "${SNAP}" | cut -f1)"
  echo

  echo "--- preflight: GPUs idle? ---"
  # Check real GPU consumers, not a loose string match: an earlier version
  # matched this script's own command line via the .venvs/vllm-xpu path and
  # refused to start.
  running_containers="$(podman ps -q 2>/dev/null | wc -l)"
  serve_procs="$(pgrep -f 'vllm serve' 2>/dev/null | grep -vc "^$$\$" || true)"
  gpu_mem="$(timeout 15 xpu-smi stats -d 0 2>/dev/null \
             | awk -F'|' '/GPU Memory Used/ {gsub(/ /,"",$3); print $3}')"
  echo "containers running: ${running_containers}"
  echo "vllm serve procs:   ${serve_procs}"
  echo "card0 memory used:  ${gpu_mem:-unknown} MiB"

  if [ "${running_containers}" != "0" ] || [ "${serve_procs}" != "0" ]; then
    echo "FATAL: something is already running; refusing to start"
    exit 1
  fi
  if [ -n "${gpu_mem}" ] && [ "${gpu_mem}" -gt 1024 ] 2>/dev/null; then
    echo "FATAL: card0 already holds ${gpu_mem} MiB; refusing to start"
    exit 1
  fi
  echo "no active lane detected"
  echo

  podman rm -f "${NAME}" >/dev/null 2>&1

  echo "--- starting server (TP2 on cards 0,1) ---"
  podman run -d --name "${NAME}" \
    --net=host \
    --ipc=host \
    --device=/dev/dri \
    --group-add keep-groups \
    -v "${REPO}":/model:ro \
    -e ZE_AFFINITY_MASK=0,1 \
    -e VLLM_ALLOW_LONG_MAX_MODEL_LEN=1 \
    -e VLLM_WORKER_MULTIPROC_METHOD=spawn \
    -e VLLM_OFFLOAD_WEIGHTS_BEFORE_QUANT=1 \
    -e PYTORCH_ALLOC_CONF=expandable_segments:True \
    -e CCL_TOPO_P2P_ACCESS=1 \
    -e CCL_ATL_TRANSPORT=ofi \
    -e ONEAPI_DEVICE_SELECTOR=level_zero:0,1 \
    -e TORCH_LLM_ALLREDUCE=1 \
    -e CCL_ZE_IPC_EXCHANGE=pidfd \
    -e UR_L0_ENABLE_RELAXED_ALLOCATION_LIMITS=1 \
    --entrypoint /bin/bash \
    "${IMAGE}" \
    -lc "vllm serve \
      --model /model/snapshots/${REV} \
      --served-model-name qwen36-27b-fp8 \
      --tensor-parallel-size 2 \
      --host 127.0.0.1 --port ${PORT} \
      --dtype float16 \
      --quantization fp8 \
      --kv-cache-dtype fp8_e4m3 \
      --max-model-len 262144 \
      --block-size 128 \
      --max-num-seqs 4 \
      --gpu-memory-utilization 0.92 \
      --enforce-eager \
      --no-enable-prefix-caching \
      --enable-auto-tool-choice \
      --tool-call-parser qwen3_coder \
      --reasoning-parser qwen3 \
      --trust-remote-code \
      --override-generation-config '{\"temperature\": 0.7, \"top_p\": 0.8, \"top_k\": 20, \"presence_penalty\": 1.5, \"repetition_penalty\": 1.0}' \
      --default-chat-template-kwargs '{\"enable_thinking\": true, \"preserve_thinking\": true}'"

  echo "--- waiting for /health (up to 30 min; FP8 quant of 27B is slow to load) ---"
  ready=0
  for i in $(seq 1 180); do
    if curl -fsS -m 5 "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then
      ready=1
      echo "server healthy after ~$((i * 10))s"
      break
    fi
    if ! podman container exists "${NAME}" || \
       [ "$(podman inspect -f '{{.State.Running}}' "${NAME}" 2>/dev/null)" != "true" ]; then
      echo "FATAL: container exited before becoming healthy"
      echo "--- last 60 log lines ---"
      podman logs --tail 60 "${NAME}" 2>&1
      exit 1
    fi
    sleep 10
  done

  if [ "${ready}" != "1" ]; then
    echo "FATAL: server never became healthy"
    podman logs --tail 60 "${NAME}" 2>&1
    exit 1
  fi

  echo
  echo "--- served models ---"
  curl -fsS -m 10 "http://127.0.0.1:${PORT}/v1/models" 2>&1
  echo
  echo

  echo "--- throughput measurement ---"
  python3 "${HERE}/bench-recipe.py" "${HERE}/bench-${STAMP}.json"
  rc=$?
  echo "bench rc=${rc}"

  echo
  echo "--- server log tail (for the record) ---"
  podman logs --tail 25 "${NAME}" 2>&1
} 2>&1 | tee "${LOG}"

echo "log: ${LOG}"
