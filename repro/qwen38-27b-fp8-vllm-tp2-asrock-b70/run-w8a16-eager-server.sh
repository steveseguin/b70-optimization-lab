#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
image=${IMAGE:-neural-download/vllm-openai-xpu:f01e-kernel-1e90-w8a16-r122}
model_dir=${MODEL_DIR:?set MODEL_DIR to the downloaded Qwen3.8-27B-FP8 directory}
cache_dir=${VLLM_CACHE_DIR:?set VLLM_CACHE_DIR to a writable non-prompt cache directory}
container=${CONTAINER_NAME:-qwen38-fp8-block-w8a16-mtp0-eager-tp2}
port=${PORT:-18134}
served_model=${SERVED_MODEL_NAME:-qwen38-fp8-block-w8a16-mtp0-eager}
max_model_len=${MAX_MODEL_LEN:-1024}
max_num_seqs=${MAX_NUM_SEQS:-1}
max_num_batched_tokens=${MAX_NUM_BATCHED_TOKENS:-1024}
fp8_block_w8a16=${VLLM_XPU_FP8_BLOCK_W8A16:-1}

for value_name in max_num_seqs max_model_len max_num_batched_tokens; do
  value=${!value_name}
  [[ "${value}" =~ ^[1-9][0-9]*$ ]] || {
    printf '%s must be positive\n' "${value_name^^}" >&2
    exit 1
  }
done
[[ "${fp8_block_w8a16}" == 0 || "${fp8_block_w8a16}" == 1 ]] || {
  printf 'VLLM_XPU_FP8_BLOCK_W8A16 must be 0 or 1\n' >&2
  exit 1
}

"${script_dir}/verify-model-direct.sh" "${model_dir}"
command -v docker >/dev/null || { printf 'docker is required\n' >&2; exit 1; }
docker image inspect "${image}" >/dev/null 2>&1 || {
  printf 'image is missing: %s\n' "${image}" >&2
  exit 1
}
if docker ps -a --format '{{.Names}}' | grep -Fxq "${container}"; then
  printf 'container already exists: %s\n' "${container}" >&2
  exit 1
fi
mkdir -p "${cache_dir}"

w8a16_env=()
if [[ "${fp8_block_w8a16}" == 1 ]]; then
  w8a16_env=(--env VLLM_XPU_FP8_BLOCK_W8A16=1)
fi

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
  --env VLLM_XPU_ENABLE_XPU_GRAPH=0 \
  --env VLLM_XPU_GRAPH=0 \
  "${w8a16_env[@]}" \
  --env PYTORCH_ALLOC_CONF=expandable_segments:True \
  --env CCL_ATL_TRANSPORT=ofi --env FI_PROVIDER=tcp --env FI_TCP_IFACE=lo \
  --env CCL_ZE_IPC_EXCHANGE=pidfd \
  --env CCL_SEND=direct --env CCL_RECV=direct \
  --env CCL_TOPO_P2P_ACCESS=1 \
  --env CCL_SYCL_ALLREDUCE_SIMPLE_THRESHOLD=4294967296 \
  --env CCL_SYCL_ALLGATHERV_SIMPLE_THRESHOLD=4294967296 \
  --env CCL_SYCL_REDUCE_SCATTER_SIMPLE_THRESHOLD=4294967296 \
  "${image}" \
  --model /model --served-model-name "${served_model}" \
  --host 0.0.0.0 --port 8000 \
  --tensor-parallel-size 2 \
  --dtype float16 --quantization fp8 --kv-cache-dtype auto \
  --gpu-memory-utilization 0.80 \
  --max-model-len "${max_model_len}" --block-size 64 \
  --max-num-seqs "${max_num_seqs}" --max-num-batched-tokens "${max_num_batched_tokens}" \
  --no-enable-prefix-caching --enable-prompt-tokens-details \
  --language-model-only --enforce-eager
