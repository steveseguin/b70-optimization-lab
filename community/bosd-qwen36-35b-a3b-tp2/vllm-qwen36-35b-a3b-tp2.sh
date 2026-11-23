#!/usr/bin/env bash
# Dual-B70 vLLM-XPU TP2 serving of Qwen3.6-35B-A3B GPTQ-Int4.
#
# Key point of this entry: the ONLY change from a working `1.5` launch that
# matters is the image tag. On intel/llm-scaler-vllm:1.5 (vLLM 0.26.1) the
# engine finishes init and then the APIServer never binds (/health stays 000).
# On intel/llm-scaler-vllm:0.31.0-b1-experimental (vLLM 0.31.0) the same command
# brings up a live OpenAI endpoint. See README.md "Key finding: image, not flags".
#
# Host note: with 62 GB host RAM, STOP all other GPU services first — two TP2
# workers staging ~20.8 GiB checkpoint shards each will OOM otherwise.
set -euo pipefail

IMG="${IMG:-docker.io/intel/llm-scaler-vllm:0.31.0-b1-experimental}"
MODEL="${MODEL:?set MODEL to your local Qwen3.6-35B-A3B GPTQ-Int4 weights dir}"
PORT="${PORT:-8000}"
NAME="${NAME:-tp2}"

# --ipc host and --shm-size are mutually exclusive; do NOT add --shm-size here.
exec podman run -d --name "$NAME" \
  --device /dev/dri --security-opt label=disable --privileged --net host --ipc host \
  -e ZE_AFFINITY_MASK=1,2 -e ZE_FLAT_DEVICE_HIERARCHY=COMPOSITE \
  -e CCL_ENABLE_SYCL_KERNELS=0 \
  -e CCL_ATL_TRANSPORT=ofi \
  -e CCL_ZE_IPC_EXCHANGE=pidfd \
  -e CCL_TOPO_FABRIC_VERTEX_CONNECTION_CHECK=0 \
  -e VLLM_WORKER_MULTIPROC_METHOD=spawn \
  -e SYCL_UR_USE_LEVEL_ZERO_V2=0 \
  -e UR_L0_ENABLE_RELAXED_ALLOCATION_LIMITS=1 \
  -e ZES_ENABLE_SYSMAN=1 \
  -v "$MODEL":/model:ro \
  "$IMG" \
    /model --quantization gptq --dtype float16 \
    --tensor-parallel-size 2 --distributed-executor-backend mp \
    --max-model-len 8192 --gpu-memory-utilization 0.85 \
    --enforce-eager --port "$PORT" --served-model-name tp2-test

# Readiness: poll until `/health` → 200, then `/v1/models` lists `tp2-test`.
#   curl -s localhost:$PORT/health
#   curl -s localhost:$PORT/v1/models
