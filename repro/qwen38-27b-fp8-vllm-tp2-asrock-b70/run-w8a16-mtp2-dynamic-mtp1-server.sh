#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
image=${IMAGE:-neural-download/vllm-openai-xpu:f01e-kernel-1e90-w8a16-r122}
model_dir=${MODEL_DIR:?set MODEL_DIR to the downloaded Qwen3.8-27B-FP8 directory}
cache_dir=${VLLM_CACHE_DIR:?set VLLM_CACHE_DIR to a new writable cache directory}
container=${CONTAINER_NAME:-qwen38-fp8-w8a16-mtp2-dynamic-mtp1-r1}
port=${PORT:-18128}
image_id=sha256:61bd8edb385c03b40cdadaba068608355b144a5011722597e7ca437f37346ecd
kernel_head=1e90ffa672ba02f17a909da11838a4c55b199783

"${script_dir}/verify-model-direct.sh" "${model_dir}"
command -v docker >/dev/null || { printf 'docker is required\n' >&2; exit 1; }
docker image inspect "${image}" >/dev/null 2>&1 || {
  printf 'image is missing: %s\nBuild the pinned kernel and W8A16 overlays first.\n' "${image}" >&2
  exit 1
}
[[ "$(docker image inspect "${image}" --format '{{.Id}}')" == "${image_id}" ]] || {
  printf 'image ID does not match the preregistered runtime\n' >&2
  exit 1
}
[[ "$(docker image inspect "${image}" --format '{{ index .Config.Labels "neural.download.kernel.head" }}')" == "${kernel_head}" ]] || {
  printf 'image does not contain the required mixed-batch XPU kernel\n' >&2
  exit 1
}
if docker ps -a --format '{{.Names}}' | grep -Fxq "${container}"; then
  printf 'container already exists: %s\n' "${container}" >&2
  exit 1
fi
mkdir -p "${cache_dir}"

exec docker run --rm --name "${container}" \
  --memory 9g --memory-swap 12g \
  --device /dev/dri:/dev/dri --group-add render \
  --cap-add SYS_PTRACE --security-opt label=disable \
  --ipc=host --shm-size=8g \
  --publish "127.0.0.1:${port}:8000" \
  --volume "${model_dir}:/model:ro" \
  --volume "${cache_dir}:/root/.cache/vllm" \
  --env ZE_AFFINITY_MASK=0,1 \
  --env ONEAPI_DEVICE_SELECTOR=level_zero:0,1 \
  --env VLLM_TARGET_DEVICE=xpu \
  --env VLLM_WORKER_MULTIPROC_METHOD=spawn \
  --env VLLM_XPU_ENABLE_XPU_GRAPH=1 \
  --env VLLM_XPU_FP8_BLOCK_W8A16=1 \
  --env PYTORCH_ALLOC_CONF=expandable_segments:True \
  --env CCL_ATL_TRANSPORT=ofi --env FI_PROVIDER=tcp --env FI_TCP_IFACE=lo \
  --env CCL_ZE_IPC_EXCHANGE=pidfd \
  --env CCL_SEND=direct --env CCL_RECV=direct \
  --env CCL_TOPO_P2P_ACCESS=1 \
  --env CCL_SYCL_ALLREDUCE_SIMPLE_THRESHOLD=4294967296 \
  --env CCL_SYCL_ALLGATHERV_SIMPLE_THRESHOLD=4294967296 \
  --env CCL_SYCL_REDUCE_SCATTER_SIMPLE_THRESHOLD=4294967296 \
  "${image}" \
  --model /model --served-model-name qwen38-fp8-w8a16-mtp2-dynamic-mtp1 \
  --host 0.0.0.0 --port 8000 \
  --tensor-parallel-size 2 \
  --dtype float16 --quantization fp8 --kv-cache-dtype auto \
  --gpu-memory-utilization 0.96 \
  --max-model-len 256 --block-size 64 \
  --max-num-seqs 128 --max-num-batched-tokens 512 \
  --no-enable-prefix-caching --enable-prompt-tokens-details \
  --language-model-only \
  --speculative-config '{"method":"qwen3_next_mtp","num_speculative_tokens":2,"num_speculative_tokens_per_batch_size":[[1,1,2],[2,128,1]]}' \
  --compilation-config '{"cudagraph_mode":"PIECEWISE","cudagraph_capture_sizes":[1],"max_cudagraph_capture_size":1}'
