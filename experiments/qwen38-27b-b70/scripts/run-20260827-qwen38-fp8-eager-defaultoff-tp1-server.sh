#!/usr/bin/env bash
set -euo pipefail

repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)
image=${IMAGE:-neural-download/vllm-openai-xpu:f01e-kernel-1e90-w8a16-r122}
model_dir=${MODEL_DIR:?set MODEL_DIR to the downloaded Qwen3.8-27B-FP8 directory}
cache_dir=${VLLM_CACHE_DIR:?set VLLM_CACHE_DIR to a new writable non-prompt cache directory}
container=${CONTAINER_NAME:-qwen38-fp8-eager-defaultoff-tp1}
port=${PORT:-18136}
served_model=${SERVED_MODEL_NAME:-qwen38-fp8-eager-defaultoff-tp1}
max_model_len=${MAX_MODEL_LEN:-1024}
max_num_batched_tokens=${MAX_NUM_BATCHED_TOKENS:-1024}

for value_name in max_model_len max_num_batched_tokens; do
  value=${!value_name}
  [[ "${value}" =~ ^[1-9][0-9]*$ ]] || {
    printf '%s must be positive\n' "${value_name^^}" >&2
    exit 1
  }
done

"${repo}/repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/verify-model-direct.sh" "${model_dir}"
docker image inspect "${image}" >/dev/null 2>&1 || {
  printf 'image is missing: %s\n' "${image}" >&2
  exit 1
}
if docker ps -a --format '{{.Names}}' | grep -Fxq "${container}"; then
  printf 'container already exists: %s\n' "${container}" >&2
  exit 1
fi
mkdir -p "${cache_dir}"

exec docker run --rm --name "${container}" \
  --memory 12g --memory-swap 16g \
  --device /dev/dri:/dev/dri --group-add render \
  --cap-add SYS_PTRACE --security-opt label=disable \
  --ipc=host --shm-size=8g \
  --publish "127.0.0.1:${port}:8000" \
  --volume "${model_dir}:/model:ro" \
  --volume "${cache_dir}:/root/.cache/vllm" \
  --env ZE_AFFINITY_MASK=0 \
  --env ONEAPI_DEVICE_SELECTOR=level_zero:0 \
  --env VLLM_TARGET_DEVICE=xpu \
  --env VLLM_WORKER_MULTIPROC_METHOD=spawn \
  --env VLLM_XPU_ENABLE_XPU_GRAPH=0 \
  --env VLLM_XPU_GRAPH=0 \
  --env PYTORCH_ALLOC_CONF=expandable_segments:True \
  "${image}" \
  --model /model --served-model-name "${served_model}" \
  --host 0.0.0.0 --port 8000 \
  --tensor-parallel-size 1 \
  --dtype float16 --quantization fp8 --kv-cache-dtype auto \
  --gpu-memory-utilization 0.96 \
  --max-model-len "${max_model_len}" --block-size 64 \
  --max-num-seqs 1 --max-num-batched-tokens "${max_num_batched_tokens}" \
  --no-enable-prefix-caching --enable-prompt-tokens-details \
  --language-model-only --enforce-eager
