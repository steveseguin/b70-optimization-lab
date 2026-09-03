#!/usr/bin/env bash
set -euo pipefail

image="${IMAGE:-vllm/vllm-openai-xpu@sha256:f01e24f6c7ff01f1e0662234255a1372297d1dbd89d003cf13c8fad3eab1ba4f}"
model_dir="${MODEL_DIR:?set MODEL_DIR to the downloaded Qwen3.8-27B-FP8 directory}"
cache_dir="${VLLM_CACHE_DIR:?set VLLM_CACHE_DIR to a writable cache directory}"
container="${CONTAINER_NAME:-qwen38-fp8-tp2}"
port="${PORT:-18087}"
served_model="${SERVED_MODEL_NAME:-qwen38-fp8}"
# Keep fresh compilations on the exact-output-stable path qualified by the
# R53/R54 four-arm matrix. The explicit inductor_compile_config fields are
# required: setting TORCHINDUCTOR_DETERMINISTIC alone did not make vLLM's
# generated compile context deterministic on this stack.
compilation_config=${COMPILATION_CONFIG:-'{"cudagraph_mode":"PIECEWISE","cudagraph_capture_sizes":[1],"max_cudagraph_capture_size":1,"inductor_compile_config":{"combo_kernels":false,"benchmark_combo_kernel":false,"deterministic":true,"triton.autotune_pointwise":false,"benchmark_epilogue_fusion":false}}'}
max_num_seqs="${MAX_NUM_SEQS:-4}"
max_model_len="${MAX_MODEL_LEN:-4096}"
max_num_batched_tokens="${MAX_NUM_BATCHED_TOKENS:-256}"
gpu_memory_utilization="${GPU_MEMORY_UTILIZATION:-0.80}"
container_memory="${CONTAINER_MEMORY:-9g}"
container_memory_swap="${CONTAINER_MEMORY_SWAP:-12g}"
ccl_p2p_access="${CCL_P2P_ACCESS:-0}"
fp8_block_w8a16="${VLLM_XPU_FP8_BLOCK_W8A16:-0}"
xpu_graph="${VLLM_XPU_ENABLE_XPU_GRAPH:-1}"
inductor_deterministic="${TORCHINDUCTOR_DETERMINISTIC:-0}"
inductor_max_autotune="${VLLM_ENABLE_INDUCTOR_MAX_AUTOTUNE:-1}"
inductor_coordinate_descent="${VLLM_ENABLE_INDUCTOR_COORDINATE_DESCENT_TUNING:-1}"
python_hash_seed="${PYTHONHASHSEED:-}"
expected_image_id="${EXPECTED_IMAGE_ID:-}"
expected_kernel_head="${EXPECTED_KERNEL_HEAD:-}"
image_contract_profile="${IMAGE_CONTRACT_PROFILE:-}"
batch_invariant="${VLLM_BATCH_INVARIANT:-0}"
qwen_gemma_rmsnorm_batch_invariant="${VLLM_XPU_QWEN_GEMMA_RMSNORM_BATCH_INVARIANT:-0}"
qwen_gemma_rmsnorm_packed_serial_exact="${VLLM_XPU_QWEN_GEMMA_RMSNORM_PACKED_SERIAL_EXACT:-0}"
gdn_serial_exact="${VLLM_XPU_GDN_NATIVE_SPEC_RECURRENT_SERIAL_EXACT:-0}"
gdn_persistent_scratch="${VLLM_XPU_GDN_SPEC_PERSISTENT_SCRATCH:-0}"
gdn_native_fallback="${VLLM_XPU_GDN_NATIVE_FALLBACK:-1}"
lm_head_chunk_rows="${VLLM_XPU_LM_HEAD_CHUNK_ROWS:-0}"
[[ "${lm_head_chunk_rows}" =~ ^[0-9]+$ && "${lm_head_chunk_rows}" -le 512 ]] || { printf 'VLLM_XPU_LM_HEAD_CHUNK_ROWS must be an integer in 0..512\n' >&2; exit 1; }

[[ "${max_num_seqs}" =~ ^[1-9][0-9]*$ ]] || { printf 'MAX_NUM_SEQS must be positive\n' >&2; exit 1; }
[[ "${max_model_len}" =~ ^[1-9][0-9]*$ ]] || { printf 'MAX_MODEL_LEN must be positive\n' >&2; exit 1; }
[[ "${max_num_batched_tokens}" =~ ^[1-9][0-9]*$ ]] || { printf 'MAX_NUM_BATCHED_TOKENS must be positive\n' >&2; exit 1; }
[[ "${gpu_memory_utilization}" =~ ^0\.[0-9]+$ ]] || { printf 'GPU_MEMORY_UTILIZATION must be between 0 and 1\n' >&2; exit 1; }
[[ "${container_memory}" =~ ^[1-9][0-9]*[gGmM]$ ]] || { printf 'CONTAINER_MEMORY must be a positive Docker memory value such as 9g\n' >&2; exit 1; }
[[ "${container_memory_swap}" =~ ^[1-9][0-9]*[gGmM]$ ]] || { printf 'CONTAINER_MEMORY_SWAP must be a positive Docker memory value such as 12g\n' >&2; exit 1; }
[[ "${ccl_p2p_access}" == 0 || "${ccl_p2p_access}" == 1 ]] || { printf 'CCL_P2P_ACCESS must be 0 or 1\n' >&2; exit 1; }
[[ "${fp8_block_w8a16}" == 0 || "${fp8_block_w8a16}" == 1 ]] || { printf 'VLLM_XPU_FP8_BLOCK_W8A16 must be 0 or 1\n' >&2; exit 1; }
[[ "${xpu_graph}" == 0 || "${xpu_graph}" == 1 ]] || { printf 'VLLM_XPU_ENABLE_XPU_GRAPH must be 0 or 1\n' >&2; exit 1; }
[[ "${inductor_deterministic}" == 0 || "${inductor_deterministic}" == 1 ]] || { printf 'TORCHINDUCTOR_DETERMINISTIC must be 0 or 1\n' >&2; exit 1; }
for value_name in inductor_max_autotune inductor_coordinate_descent; do
    value=${!value_name}
    [[ "${value}" == 0 || "${value}" == 1 ]] || {
        printf '%s must be 0 or 1\n' "${value_name^^}" >&2
        exit 1
    }
done
[[ -z "${python_hash_seed}" || "${python_hash_seed}" =~ ^[0-9]+$ ]] || {
    printf 'PYTHONHASHSEED must be an unsigned integer when set\n' >&2
    exit 1
}
for value_name in batch_invariant qwen_gemma_rmsnorm_batch_invariant \
  qwen_gemma_rmsnorm_packed_serial_exact \
  gdn_serial_exact gdn_persistent_scratch gdn_native_fallback; do
    value=${!value_name}
    [[ "${value}" == 0 || "${value}" == 1 ]] || {
        printf '%s must be 0 or 1\n' "${value_name^^}" >&2
        exit 1
    }
done

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
"${script_dir}/verify-model-direct.sh" "${model_dir}"
command -v docker >/dev/null || { printf 'docker is required\n' >&2; exit 1; }
docker image inspect "${image}" >/dev/null 2>&1 || {
    printf 'image is missing: %s\n' "${image}" >&2
    exit 1
}
if [[ -n "${image_contract_profile}" ]]; then
    "${script_dir}/verify-image-contract.sh" "${image_contract_profile}" "${image}"
fi
if [[ -n "${expected_image_id}" && "$(docker image inspect "${image}" --format '{{.Id}}')" != "${expected_image_id}" ]]; then
    printf 'image identity mismatch: expected %s\n' "${expected_image_id}" >&2
    exit 1
fi
if [[ -n "${expected_kernel_head}" && "$(docker image inspect "${image}" --format '{{ index .Config.Labels "neural.download.kernel.head" }}')" != "${expected_kernel_head}" ]]; then
    printf 'image does not contain the required XPU kernel: %s\n' "${expected_kernel_head}" >&2
    exit 1
fi

if docker ps -a --format '{{.Names}}' | grep -Fxq "${container}"; then
    printf 'Container already exists: %s\n' "${container}" >&2
    exit 1
fi

mkdir -p "${cache_dir}"

w8a16_env=()
if [[ "${fp8_block_w8a16}" == 1 ]]; then
    w8a16_env=(-e VLLM_XPU_FP8_BLOCK_W8A16=1)
fi
hash_seed_env=()
if [[ -n "${python_hash_seed}" ]]; then
    hash_seed_env=(-e "PYTHONHASHSEED=${python_hash_seed}")
fi

exec docker run --rm --name "${container}" \
    --ulimit core=0 \
    --memory "${container_memory}" --memory-swap "${container_memory_swap}" \
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
    -e VLLM_ENABLE_INDUCTOR_MAX_AUTOTUNE="${inductor_max_autotune}" \
    -e VLLM_ENABLE_INDUCTOR_COORDINATE_DESCENT_TUNING="${inductor_coordinate_descent}" \
    "${hash_seed_env[@]}" \
    "${w8a16_env[@]}" \
    -e VLLM_BATCH_INVARIANT="${batch_invariant}" \
    -e VLLM_XPU_QWEN_GEMMA_RMSNORM_BATCH_INVARIANT="${qwen_gemma_rmsnorm_batch_invariant}" \
    -e VLLM_XPU_QWEN_GEMMA_RMSNORM_PACKED_SERIAL_EXACT="${qwen_gemma_rmsnorm_packed_serial_exact}" \
    -e VLLM_XPU_GDN_NATIVE_SPEC_RECURRENT_SERIAL_EXACT="${gdn_serial_exact}" \
    -e VLLM_XPU_GDN_SPEC_PERSISTENT_SCRATCH="${gdn_persistent_scratch}" \
    -e VLLM_XPU_GDN_NATIVE_FALLBACK="${gdn_native_fallback}" \
    -e VLLM_XPU_LM_HEAD_CHUNK_ROWS="${lm_head_chunk_rows}" \
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
    -e REPRO_GPU_MEMORY_UTILIZATION="${gpu_memory_utilization}" \
    -e REPRO_SERVED_MODEL_NAME="${served_model}" \
    -e REPRO_COMPILATION_CONFIG="${compilation_config}" \
    --entrypoint bash \
    "${image}" -lc \
    'exec vllm serve /model --served-model-name "${REPRO_SERVED_MODEL_NAME}" --host 0.0.0.0 --port 8000 --tensor-parallel-size 2 --dtype float16 --quantization fp8 --kv-cache-dtype auto --gpu-memory-utilization "${REPRO_GPU_MEMORY_UTILIZATION}" --max-model-len "${REPRO_MAX_MODEL_LEN}" --block-size 64 --max-num-seqs "${REPRO_MAX_NUM_SEQS}" --max-num-batched-tokens "${REPRO_MAX_BATCHED_TOKENS}" --no-enable-prefix-caching --enable-prompt-tokens-details --language-model-only --compilation-config "${REPRO_COMPILATION_CONFIG}"'
