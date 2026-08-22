#!/usr/bin/env bash
set -euo pipefail

image="${IMAGE:-vllm/vllm-openai-xpu@sha256:f01e24f6c7ff01f1e0662234255a1372297d1dbd89d003cf13c8fad3eab1ba4f}"
model_dir="${MODEL_DIR:-/mnt/fast-ai/llm-models/qwen3.8-27b-fp8}"
cache_dir="${VLLM_CACHE_DIR:-/mnt/fast-ai/vllm-cache/q38-official-fp8-f01e/vllm}"
container="${CONTAINER_NAME:-qwen38-fp8-tp2}"
port="${PORT:-18087}"
max_num_seqs="${MAX_NUM_SEQS:-4}"

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
"${script_dir}/verify-model-direct.sh" "${model_dir}"
command -v docker >/dev/null || { printf 'docker is required\n' >&2; exit 1; }

if docker ps -a --format '{{.Names}}' | grep -Fxq "${container}"; then
    printf 'Container already exists: %s\n' "${container}" >&2
    exit 1
fi

mkdir -p "${cache_dir}"

exec docker run --rm --name "${container}" \
    --memory 9g --memory-swap 12g \
    --device /dev/dri:/dev/dri \
    --group-add render \
    --cap-add SYS_PTRACE \
    --security-opt label=disable \
    --ipc=host --shm-size=8g \
    -p "127.0.0.1:${port}:8000" \
    -v "${model_dir}:/model:ro" \
    -v "${cache_dir}:/root/.cache/vllm" \
    -e ZE_AFFINITY_MASK=0,1 \
    -e ONEAPI_DEVICE_SELECTOR=level_zero:0,1 \
    -e VLLM_TARGET_DEVICE=xpu \
    -e VLLM_WORKER_MULTIPROC_METHOD=spawn \
    -e VLLM_XPU_ENABLE_XPU_GRAPH=1 \
    -e PYTORCH_ALLOC_CONF=expandable_segments:True \
    -e CCL_ATL_TRANSPORT=ofi \
    -e FI_PROVIDER=tcp \
    -e FI_TCP_IFACE=lo \
    -e CCL_ZE_IPC_EXCHANGE=pidfd \
    -e CCL_SEND=direct \
    -e CCL_RECV=direct \
    -e CCL_TOPO_P2P_ACCESS=0 \
    -e CCL_SYCL_ALLREDUCE_SIMPLE_THRESHOLD=4294967296 \
    -e CCL_SYCL_ALLGATHERV_SIMPLE_THRESHOLD=4294967296 \
    -e CCL_SYCL_REDUCE_SCATTER_SIMPLE_THRESHOLD=4294967296 \
    -e REPRO_MAX_NUM_SEQS="${max_num_seqs}" \
    --entrypoint bash \
    "${image}" -lc \
    'exec vllm serve /model --served-model-name qwen38-fp8 --host 0.0.0.0 --port 8000 --tensor-parallel-size 2 --dtype float16 --quantization fp8 --kv-cache-dtype auto --gpu-memory-utilization 0.80 --max-model-len 4096 --block-size 64 --max-num-seqs "${REPRO_MAX_NUM_SEQS}" --max-num-batched-tokens 256 --no-enable-prefix-caching --enable-prompt-tokens-details --language-model-only --compilation-config '\''{"cudagraph_mode":"PIECEWISE","cudagraph_capture_sizes":[1],"max_cudagraph_capture_size":1}'\'''
