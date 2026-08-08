#!/usr/bin/env bash
# Maintainer-hardened launcher derived from PR #18.
# The contributor's exact measured launcher is preserved under reported/.
set -euo pipefail

IMAGE="${IMAGE:-intel/llm-scaler-vllm@sha256:3f0a8c60fbaf376ec09538f093cba91f171238b99c117445c0bcc6096272ec3e}"
MODEL_REPO="${MODEL_REPO:?Set MODEL_REPO to the local Hugging Face cache repository}"
REVISION="${REVISION:-95a723d08a9490559dae23d0cff1d9466213d989}"
NAME="${NAME:-community-qwen36-35b-fp8-b2-tp2}"
PORT="${PORT:-18018}"
MAX_LEN="${MAX_LEN:-131072}"
MAX_SEQS="${MAX_SEQS:-12}"
GPU_MEMORY_UTILIZATION="${GPU_MEMORY_UTILIZATION:-0.95}"
MTP="${MTP:-1}"
DRY_RUN="${DRY_RUN:-0}"
MODEL="/model/snapshots/${REVISION}"
MODEL_SNAPSHOT="${MODEL_REPO}/snapshots/${REVISION}"

[[ "${IMAGE}" =~ @sha256:[0-9a-f]{64}$ ]] || {
  echo "IMAGE must be pinned by sha256 digest" >&2
  exit 2
}
[[ "${REVISION}" =~ ^[0-9a-f]{40}$ ]] || { echo "REVISION must be a 40-character commit" >&2; exit 2; }
[[ "${NAME}" =~ ^[a-zA-Z0-9][a-zA-Z0-9_.-]*$ ]] || { echo "Unsafe container NAME" >&2; exit 2; }
[[ "${PORT}" =~ ^[0-9]+$ ]] && ((PORT >= 1024 && PORT <= 65535)) || { echo "Invalid PORT" >&2; exit 2; }
[[ "${MAX_LEN}" =~ ^[0-9]+$ ]] && ((MAX_LEN > 0)) || { echo "Invalid MAX_LEN" >&2; exit 2; }
[[ "${MAX_SEQS}" =~ ^[0-9]+$ ]] && ((MAX_SEQS > 0)) || { echo "Invalid MAX_SEQS" >&2; exit 2; }
[[ "${GPU_MEMORY_UTILIZATION}" =~ ^0\.[0-9]+$ ]] || { echo "Invalid GPU_MEMORY_UTILIZATION" >&2; exit 2; }
[[ "${MTP}" == "0" || "${MTP}" == "1" ]] || { echo "MTP must be 0 or 1" >&2; exit 2; }
[[ "${DRY_RUN}" == "0" || "${DRY_RUN}" == "1" ]] || { echo "DRY_RUN must be 0 or 1" >&2; exit 2; }

if [[ "${DRY_RUN}" == "0" ]]; then
  [[ -f "${MODEL_SNAPSHOT}/config.json" && -f "${MODEL_SNAPSHOT}/model.safetensors.index.json" ]] || {
    echo "Incomplete model snapshot: ${MODEL_SNAPSHOT}" >&2
    exit 2
  }
  python3 - "${MODEL_SNAPSHOT}" <<'PY'
import json
import pathlib
import sys

snapshot = pathlib.Path(sys.argv[1])
index = json.loads((snapshot / "model.safetensors.index.json").read_text())
missing = sorted({name for name in index["weight_map"].values() if not (snapshot / name).is_file()})
if missing:
    raise SystemExit(f"Incomplete model snapshot: {len(missing)} indexed shard(s) missing")
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
  --shm-size=200g
  --group-add "${RENDER_GID}"
  --publish "127.0.0.1:${PORT}:${PORT}"
  --volume "${MODEL_REPO}:/model:ro"
  --env ZE_AFFINITY_MASK=0,1
  --env CCL_ATL_TRANSPORT=ofi
  --env FI_PROVIDER=tcp
  --env FI_TCP_IFACE=lo
  --env CCL_TOPO_P2P_ACCESS=0
  --env CCL_ZE_IPC_EXCHANGE=pidfd
  --env CCL_SEND=direct
  --env CCL_RECV=direct
  --env CCL_SYCL_ALLREDUCE_SIMPLE_THRESHOLD=4294967296
  --env CCL_SYCL_REDUCE_SCATTER_SIMPLE_THRESHOLD=4294967296
  --env CCL_SYCL_ALLGATHERV_SIMPLE_THRESHOLD=4294967296
  --env CCL_SYCL_ALLTOALL_TMP_BUF=1
  --env VLLM_TARGET_DEVICE=xpu
  --env VLLM_ALLOW_LONG_MAX_MODEL_LEN=1
  --env VLLM_WORKER_MULTIPROC_METHOD=spawn
  --env PYTORCH_ALLOC_CONF=expandable_segments:True
  --entrypoint vllm
  "${IMAGE}"
  serve "${MODEL}"
  --served-model-name qwen36-35b-fp8
  --host 0.0.0.0
  --port "${PORT}"
  --tensor-parallel-size 2
  --dtype float16
  --kv-cache-dtype fp8_e4m3
  --gpu-memory-utilization "${GPU_MEMORY_UTILIZATION}"
  --max-model-len "${MAX_LEN}"
  --block-size 64
  --max-num-seqs "${MAX_SEQS}"
  --max-num-batched-tokens 8192
  --disable-sliding-window
  --limit-mm-per-prompt '{"image":0,"video":0}'
  --enable-auto-tool-choice
  --tool-call-parser qwen3_coder
  --reasoning-parser qwen3
  --enforce-eager
  --default-chat-template-kwargs '{"enable_thinking":true,"preserve_thinking":true}'
  --override-generation-config '{"temperature":0.6,"top_p":0.95,"top_k":20,"min_p":0.0,"presence_penalty":0.0,"repetition_penalty":1.0}'
)

if [[ "${MTP}" == "1" ]]; then
  command+=(--speculative-config '{"method":"mtp","num_speculative_tokens":2}')
fi

if [[ "${DRY_RUN}" == "1" ]]; then
  printf '%q ' "${command[@]}"
  printf '\n'
  exit 0
fi

exec "${command[@]}"
