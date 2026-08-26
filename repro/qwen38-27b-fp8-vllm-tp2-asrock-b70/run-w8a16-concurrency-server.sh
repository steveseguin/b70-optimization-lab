#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
image=${IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-block-w8a16-20260826}
model_dir=${MODEL_DIR:?set MODEL_DIR to the downloaded Qwen3.8-27B-FP8 directory}
cache_dir=${VLLM_CACHE_DIR:?set VLLM_CACHE_DIR to a writable cache directory}
container=${CONTAINER_NAME:-qwen38-fp8-block-w8a16-tp2-p128}
port=${PORT:-18116}

"${script_dir}/verify-model-direct.sh" "${model_dir}"
command -v docker >/dev/null || { printf 'docker is required\n' >&2; exit 1; }
docker image inspect "${image}" >/dev/null 2>&1 || {
  printf 'image is missing: %s\nRun build-w8a16-image.sh first.\n' "${image}" >&2
  exit 1
}
if docker ps -a --format '{{.Names}}' | grep -Fxq "${container}"; then
  printf 'container already exists: %s\n' "${container}" >&2
  exit 1
fi
mkdir -p "${cache_dir}"

exec docker run --rm --name "${container}" \
  --device /dev/dri:/dev/dri \
  --volume /dev/dri:/dev/dri \
  --shm-size 8g \
  --publish "127.0.0.1:${port}:8000" \
  --volume "${model_dir}:/model:ro" \
  --volume "${cache_dir}:/root/.cache/vllm" \
  --env VLLM_XPU_FP8_BLOCK_W8A16=1 \
  --env PYTORCH_ALLOC_CONF=expandable_segments:True \
  --env FI_PROVIDER=tcp \
  --env FI_TCP_IFACE=lo \
  --env CCL_ATL_TRANSPORT=ofi \
  --env CCL_ZE_IPC_EXCHANGE=pidfd \
  --env CCL_SEND=direct \
  --env CCL_RECV=direct \
  --env CCL_TOPO_P2P_ACCESS=1 \
  --env CCL_SYCL_ALLREDUCE_SIMPLE_THRESHOLD=4294967296 \
  --env CCL_SYCL_ALLGATHERV_SIMPLE_THRESHOLD=4294967296 \
  --env CCL_SYCL_REDUCE_SCATTER_SIMPLE_THRESHOLD=4294967296 \
  --env ZE_AFFINITY_MASK=0,1 \
  --env ONEAPI_DEVICE_SELECTOR=level_zero:0,1 \
  --env VLLM_TARGET_DEVICE=xpu \
  --env VLLM_WORKER_MULTIPROC_METHOD=spawn \
  --env VLLM_XPU_ENABLE_XPU_GRAPH=1 \
  "${image}" \
  --model /model \
  --served-model-name qwen38-fp8-block-w8a16 \
  --host 0.0.0.0 --port 8000 \
  --tensor-parallel-size 2 \
  --dtype float16 --quantization fp8 --kv-cache-dtype auto \
  --gpu-memory-utilization 0.96 \
  --max-model-len 256 --block-size 64 \
  --max-num-seqs 128 --max-num-batched-tokens 256 \
  --no-enable-prefix-caching --enable-prompt-tokens-details \
  --language-model-only \
  --compilation-config '{"cudagraph_mode":"PIECEWISE","cudagraph_capture_sizes":[1],"max_cudagraph_capture_size":1}'
