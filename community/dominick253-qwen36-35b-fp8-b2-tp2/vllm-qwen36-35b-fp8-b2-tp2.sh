#!/usr/bin/env bash
# Qwen3.6-35B-A3B offline FP8 on both Intel Arc Pro B70 GPUs.
# Intel llm-scaler vLLM 0.21.0-b2, TP=2, FP8 E4M3 KV cache, port 8001.
set -euo pipefail

IMAGE="${IMAGE:-intel/llm-scaler-vllm@sha256:3f0a8c60fbaf376ec09538f093cba91f171238b99c117445c0bcc6096272ec3e}"
NAME="vllm-qwen36-35b-fp8"
MODEL_REPO="/home/dom/.cache/huggingface/hub/models--Qwen--Qwen3.6-35B-A3B-FP8"
REVISION="${REVISION:-95a723d08a9490559dae23d0cff1d9466213d989}"
MODEL="/model/snapshots/${REVISION}"
SERVED_NAME="qwen36-35b-fp8"
PORT="${PORT:-8001}"
MAX_LEN="${MAX_LEN:-131072}"
MAX_SEQS="${MAX_SEQS:-12}"
GPU_MEMORY_UTILIZATION="${GPU_MEMORY_UTILIZATION:-0.95}"
MTP="${MTP:-1}"

MODEL_SNAPSHOT="${MODEL_REPO}/snapshots/${REVISION}"
if [[ ! -f "${MODEL_SNAPSHOT}/config.json" || ! -f "${MODEL_SNAPSHOT}/model.safetensors.index.json" ]]; then
  echo "Incomplete model snapshot: ${MODEL_SNAPSHOT}" >&2
  echo "Run: hf download Qwen/Qwen3.6-35B-A3B-FP8" >&2
  exit 1
fi

python3 - "${MODEL_SNAPSHOT}" <<'PY'
import json
import pathlib
import sys

snapshot = pathlib.Path(sys.argv[1])
index = json.loads((snapshot / "model.safetensors.index.json").read_text())
missing = [name for name in sorted(set(index["weight_map"].values())) if not (snapshot / name).is_file()]
if missing:
    print(f"Incomplete model snapshot: {len(missing)} weight shards are missing", file=sys.stderr)
    for name in missing[:10]:
        print(f"  {name}", file=sys.stderr)
    sys.exit(1)
PY

SPECULATIVE_ARG=""
if [[ "${MTP}" == "1" ]]; then
  SPECULATIVE_ARG="--speculative-config '{\"method\":\"mtp\",\"num_speculative_tokens\":2}'"
fi

# Remove stale containers that previously owned port 8001.
docker rm -f "${NAME}" vllm-qwen36-35b-q8 vllm-qwen36-35b-tp2 >/dev/null 2>&1 || true

exec docker run -d \
  --name "${NAME}" \
  --restart unless-stopped \
  --privileged \
  --device=/dev/dri \
  --net=host \
  --ipc=host \
  --shm-size=200g \
  --security-opt seccomp=unconfined \
  --group-add "$(getent group render | cut -d: -f3)" \
  -v "${MODEL_REPO}":/model:ro \
  -e ZE_AFFINITY_MASK=0,1 \
  -e CCL_ATL_TRANSPORT=ofi \
  -e FI_PROVIDER=tcp \
  -e FI_TCP_IFACE=lo \
  -e CCL_TOPO_P2P_ACCESS=0 \
  -e CCL_ZE_IPC_EXCHANGE=pidfd \
  -e CCL_SEND=direct \
  -e CCL_RECV=direct \
  -e CCL_SYCL_ALLREDUCE_SIMPLE_THRESHOLD=4294967296 \
  -e CCL_SYCL_REDUCE_SCATTER_SIMPLE_THRESHOLD=4294967296 \
  -e CCL_SYCL_ALLGATHERV_SIMPLE_THRESHOLD=4294967296 \
  -e CCL_SYCL_ALLTOALL_TMP_BUF=1 \
  -e VLLM_TARGET_DEVICE=xpu \
  -e VLLM_ALLOW_LONG_MAX_MODEL_LEN=1 \
  -e VLLM_WORKER_MULTIPROC_METHOD=spawn \
  -e PYTORCH_ALLOC_CONF=expandable_segments:True \
  --entrypoint /bin/bash \
  "${IMAGE}" -lc "exec vllm serve ${MODEL} \
    --served-model-name ${SERVED_NAME} \
    --host 0.0.0.0 \
    --port ${PORT} \
    --tensor-parallel-size 2 \
    --dtype float16 \
    --kv-cache-dtype fp8_e4m3 \
    --gpu-memory-utilization ${GPU_MEMORY_UTILIZATION} \
    --max-model-len ${MAX_LEN} \
    --block-size 64 \
    --max-num-seqs ${MAX_SEQS} \
    --max-num-batched-tokens 8192 \
    --disable-sliding-window \
    --limit-mm-per-prompt '{\"image\":0,\"video\":0}' \
    --enable-auto-tool-choice \
    --tool-call-parser qwen3_coder \
    --reasoning-parser qwen3 \
    --trust-remote-code \
    --enforce-eager \
    --default-chat-template-kwargs '{\"enable_thinking\":true,\"preserve_thinking\":true}' \
    --override-generation-config '{\"temperature\":0.6,\"top_p\":0.95,\"top_k\":20,\"min_p\":0.0,\"presence_penalty\":0.0,\"repetition_penalty\":1.0}' \
    ${SPECULATIVE_ARG}"
