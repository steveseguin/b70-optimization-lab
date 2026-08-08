#!/usr/bin/env bash
# Maintainer-hardened TP1 launcher derived from PR #18.
# The contributor's exact tag-based, privileged launcher is under reported/.
set -euo pipefail

IMAGE="${IMAGE:?Set IMAGE to an intel/llm-scaler-vllm image pinned by sha256 digest}"
MODEL_HOST_DIR="${MODEL_HOST_DIR:?Set MODEL_HOST_DIR to a complete BF16 checkpoint}"
SERVED_NAME="${SERVED_NAME:-qwen36-27b-int4-community}"
NAME="${NAME:-community-qwen36-int4-b2-tp1}"
PORT="${PORT:-18019}"
GPU_ID="${GPU_ID:-0}"
MAX_LEN="${MAX_LEN:-131072}"
MAX_SEQS="${MAX_SEQS:-2}"
GPU_UTIL="${GPU_UTIL:-0.95}"
DRY_RUN="${DRY_RUN:-0}"

[[ "${IMAGE}" =~ @sha256:[0-9a-f]{64}$ ]] || { echo "IMAGE must be pinned by sha256 digest" >&2; exit 2; }
[[ "${SERVED_NAME}" =~ ^[a-zA-Z0-9][a-zA-Z0-9_.-]*$ ]] || { echo "Unsafe SERVED_NAME" >&2; exit 2; }
[[ "${NAME}" =~ ^[a-zA-Z0-9][a-zA-Z0-9_.-]*$ ]] || { echo "Unsafe NAME" >&2; exit 2; }
[[ "${GPU_ID}" =~ ^[0-9]+$ ]] || { echo "Invalid GPU_ID" >&2; exit 2; }
[[ "${PORT}" =~ ^[0-9]+$ ]] && ((PORT >= 1024 && PORT <= 65535)) || { echo "Invalid PORT" >&2; exit 2; }
[[ "${MAX_LEN}" =~ ^[0-9]+$ ]] && ((MAX_LEN > 0)) || { echo "Invalid MAX_LEN" >&2; exit 2; }
[[ "${MAX_SEQS}" =~ ^[0-9]+$ ]] && ((MAX_SEQS > 0)) || { echo "Invalid MAX_SEQS" >&2; exit 2; }
[[ "${GPU_UTIL}" =~ ^0\.[0-9]+$ ]] || { echo "Invalid GPU_UTIL" >&2; exit 2; }
[[ "${DRY_RUN}" == "0" || "${DRY_RUN}" == "1" ]] || { echo "DRY_RUN must be 0 or 1" >&2; exit 2; }

if [[ "${DRY_RUN}" == "0" ]]; then
  python3 - "${MODEL_HOST_DIR}" <<'PY'
import json
import pathlib
import sys

model = pathlib.Path(sys.argv[1])
config = model / "config.json"
if not config.is_file() or config.stat().st_size == 0:
    raise SystemExit("Incomplete model directory: config.json is missing or empty")
index = model / "model.safetensors.index.json"
if index.is_file():
    payload = json.loads(index.read_text(encoding="utf-8"))
    missing = sorted(
        name for name in set(payload["weight_map"].values()) if not (model / name).is_file()
    )
    if missing:
        raise SystemExit(f"Incomplete model directory: {len(missing)} indexed shard(s) missing")
elif not any(model.glob("*.safetensors")):
    raise SystemExit("Incomplete model directory: no safetensors weights found")
PY
  if docker container inspect "${NAME}" >/dev/null 2>&1; then
    echo "Container ${NAME} already exists; stop/remove it explicitly after checking ownership" >&2
    exit 2
  fi
fi

RENDER_GID="${RENDER_GID:-$(getent group render | cut -d: -f3)}"
[[ "${RENDER_GID}" =~ ^[0-9]+$ ]] || { echo "Could not resolve render group; set RENDER_GID" >&2; exit 2; }

command=(
  docker run --rm -d
  --name "${NAME}"
  --device=/dev/dri
  --shm-size=32g
  --group-add "${RENDER_GID}"
  --publish "127.0.0.1:${PORT}:${PORT}"
  --volume "${MODEL_HOST_DIR}:/model:ro"
  --env "ZE_AFFINITY_MASK=${GPU_ID}"
  --env VLLM_OFFLOAD_WEIGHTS_BEFORE_QUANT=1
  --env VLLM_ALLOW_LONG_MAX_MODEL_LEN=1
  --env VLLM_WORKER_MULTIPROC_METHOD=spawn
  --env VLLM_XPU_ENABLE_XPU_GRAPH=0
  --env VLLM_XPU_USE_SAMPLER_KERNEL=0
  --env PYTORCH_ALLOC_CONF=expandable_segments:True
  --env UR_L0_ENABLE_RELAXED_ALLOCATION_LIMITS=1
  --entrypoint vllm
  "${IMAGE}"
  serve /model
  --served-model-name "${SERVED_NAME}"
  --host 0.0.0.0
  --port "${PORT}"
  --tensor-parallel-size 1
  --dtype float16
  --quantization sym_int4
  --max-model-len "${MAX_LEN}"
  --gpu-memory-utilization "${GPU_UTIL}"
  --max-num-seqs "${MAX_SEQS}"
  --max-num-batched-tokens 4096
  --kv-cache-dtype fp8_e4m3
  --enable-auto-tool-choice
  --tool-call-parser qwen3_xml
  --reasoning-parser qwen3
  --enforce-eager
  --override-generation-config '{"temperature":0.6,"top_p":0.95,"top_k":20,"min_p":0.0,"presence_penalty":0.0,"repetition_penalty":1.0}'
  --default-chat-template-kwargs '{"enable_thinking":true,"preserve_thinking":true}'
)

if [[ "${DRY_RUN}" == "1" ]]; then
  printf '%q ' "${command[@]}"
  printf '\n'
  exit 0
fi

exec "${command[@]}"
