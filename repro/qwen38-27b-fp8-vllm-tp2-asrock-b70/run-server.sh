#!/usr/bin/env bash
set -euo pipefail

image="${IMAGE:-vllm/vllm-openai-xpu@sha256:f01e24f6c7ff01f1e0662234255a1372297d1dbd89d003cf13c8fad3eab1ba4f}"
model_dir="${MODEL_DIR:?set MODEL_DIR to the downloaded Qwen3.8-27B-FP8 directory}"
cache_dir="${VLLM_CACHE_DIR:?set VLLM_CACHE_DIR to a writable cache directory}"
container="${CONTAINER_NAME:-qwen38-fp8-tp2}"
port="${PORT:-18087}"
max_num_seqs="${MAX_NUM_SEQS:-4}"
max_model_len="${MAX_MODEL_LEN:-4096}"
max_num_batched_tokens="${MAX_NUM_BATCHED_TOKENS:-256}"
ccl_p2p_access="${CCL_P2P_ACCESS:-0}"
fp8_block_w8a16="${VLLM_XPU_FP8_BLOCK_W8A16:-0}"
xpu_graph="${VLLM_XPU_ENABLE_XPU_GRAPH:-1}"
inductor_deterministic="${TORCHINDUCTOR_DETERMINISTIC:-0}"

[[ "${max_num_seqs}" =~ ^[1-9][0-9]*$ ]] || { printf 'MAX_NUM_SEQS must be positive\n' >&2; exit 1; }
[[ "${max_model_len}" =~ ^[1-9][0-9]*$ ]] || { printf 'MAX_MODEL_LEN must be positive\n' >&2; exit 1; }
[[ "${max_num_batched_tokens}" =~ ^[1-9][0-9]*$ ]] || { printf 'MAX_NUM_BATCHED_TOKENS must be positive\n' >&2; exit 1; }
[[ "${ccl_p2p_access}" == 0 || "${ccl_p2p_access}" == 1 ]] || { printf 'CCL_P2P_ACCESS must be 0 or 1\n' >&2; exit 1; }
[[ "${fp8_block_w8a16}" == 0 || "${fp8_block_w8a16}" == 1 ]] || { printf 'VLLM_XPU_FP8_BLOCK_W8A16 must be 0 or 1\n' >&2; exit 1; }
[[ "${xpu_graph}" == 0 || "${xpu_graph}" == 1 ]] || { printf 'VLLM_XPU_ENABLE_XPU_GRAPH must be 0 or 1\n' >&2; exit 1; }
[[ "${inductor_deterministic}" == 0 || "${inductor_deterministic}" == 1 ]] || { printf 'TORCHINDUCTOR_DETERMINISTIC must be 0 or 1\n' >&2; exit 1; }

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
"${script_dir}/verify-model-direct.sh" "${model_dir}"
command -v docker >/dev/null || { printf 'docker is required\n' >&2; exit 1; }

if docker ps -a --format '{{.Names}}' | grep -Fxq "${container}"; then
    printf 'Container already exists: %s\n' "${container}" >&2
    exit 1
fi

mkdir -p "${cache_dir}"

w8a16_env=()
if [[ "${fp8_block_w8a16}" == 1 ]]; then
    w8a16_env=(-e VLLM_XPU_FP8_BLOCK_W8A16=1)
fi

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
    -e VLLM_XPU_ENABLE_XPU_GRAPH="${xpu_graph}" \
    -e TORCHINDUCTOR_DETERMINISTIC="${inductor_deterministic}" \
    "${w8a16_env[@]}" \
    -e PYTORCH_ALLOC_CONF=expandable_segments:True \
    -e CCL_ATL_TRANSPORT=ofi \
    -e FI_PROVIDER=tcp \
    -e FI_TCP_IFACE=lo \
    -e CCL_ZE_IPC_EXCHANGE=pidfd \
    -e CCL_SEND=direct \
    -e CCL_RECV=direct \
    -e CCL_TOPO_P2P_ACCESS="${ccl_p2p_access}" \
    -e CCL_SYCL_ALLREDUCE_SIMPLE_THRESHOLD=4294967296 \
    -e CCL_SYCL_ALLGATHERV_SIMPLE_THRESHOLD=4294967296 \
    -e CCL_SYCL_REDUCE_SCATTER_SIMPLE_THRESHOLD=4294967296 \
    -e REPRO_MAX_NUM_SEQS="${max_num_seqs}" \
    -e REPRO_MAX_MODEL_LEN="${max_model_len}" \
    -e REPRO_MAX_BATCHED_TOKENS="${max_num_batched_tokens}" \
    --entrypoint bash \
    "${image}" -lc \
    'exec vllm serve /model --served-model-name qwen38-fp8 --host 0.0.0.0 --port 8000 --tensor-parallel-size 2 --dtype float16 --quantization fp8 --kv-cache-dtype auto --gpu-memory-utilization 0.80 --max-model-len "${REPRO_MAX_MODEL_LEN}" --block-size 64 --max-num-seqs "${REPRO_MAX_NUM_SEQS}" --max-num-batched-tokens "${REPRO_MAX_BATCHED_TOKENS}" --no-enable-prefix-caching --enable-prompt-tokens-details --language-model-only --compilation-config '\''{"cudagraph_mode":"PIECEWISE","cudagraph_capture_sizes":[1],"max_cudagraph_capture_size":1}'\'''
