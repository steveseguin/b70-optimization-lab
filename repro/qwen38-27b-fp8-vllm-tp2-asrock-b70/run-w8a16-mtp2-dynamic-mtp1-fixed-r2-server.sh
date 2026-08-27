#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
image=${IMAGE:-neural-download/vllm-openai-xpu:f01e-kernel-1e90-w8a16-dynamic-mtp-width-r1}
model_dir=${MODEL_DIR:?set MODEL_DIR to the downloaded Qwen3.8-27B-FP8 directory}
cache_dir=${VLLM_CACHE_DIR:?set VLLM_CACHE_DIR to a new writable cache directory}
container=${CONTAINER_NAME:-qwen38-fp8-w8a16-mtp2-dynamic-mtp1-fixed-r2}
port=${PORT:-18128}
served_model=${SERVED_MODEL_NAME:-qwen38-fp8-w8a16-mtp2-dynamic-mtp1-fixed-r2}
speculative_config=${SPECULATIVE_CONFIG:-'{"method":"qwen3_next_mtp","num_speculative_tokens":2,"num_speculative_tokens_per_batch_size":[[1,1,2],[2,128,1]]}'}
max_num_seqs=${MAX_NUM_SEQS:-128}
max_model_len=${MAX_MODEL_LEN:-256}
max_num_batched_tokens=${MAX_NUM_BATCHED_TOKENS:-512}
image_id=${EXPECTED_IMAGE_ID:-sha256:9918c4477d2d3bdbd84732c5beb13619a89740f9915b1d7393fb48f1d3c8ed72}
kernel_head=1e90ffa672ba02f17a909da11838a4c55b199783
patch_sha256=68c486a9a10a2f7e85d7d88783a05f89919e931d2b81922f85be733bfb59f1b5
xpu_extension_sha256=de253fa31df9acae6020b95da8d2286f5ff15d8fe3d51b59b71496cbf9311f62
gdn_library_sha256=2c343620d689409bfa371a8b4c3db680e4786f23bc092411e7d03140f1b2a355

[[ "${max_num_seqs}" =~ ^[1-9][0-9]*$ ]] || {
  printf 'MAX_NUM_SEQS must be positive\n' >&2
  exit 1
}
[[ "${max_model_len}" =~ ^[1-9][0-9]*$ ]] || {
  printf 'MAX_MODEL_LEN must be positive\n' >&2
  exit 1
}
[[ "${max_num_batched_tokens}" =~ ^[1-9][0-9]*$ ]] || {
  printf 'MAX_NUM_BATCHED_TOKENS must be positive\n' >&2
  exit 1
}

"${script_dir}/verify-model-direct.sh" "${model_dir}"
command -v docker >/dev/null || { printf 'docker is required\n' >&2; exit 1; }
docker image inspect "${image}" >/dev/null 2>&1 || {
  printf 'image is missing: %s\nBuild the dynamic-MTP kernel overlay first.\n' "${image}" >&2
  exit 1
}
[[ "$(docker image inspect "${image}" --format '{{.Id}}')" == "${image_id}" ]] || {
  printf 'image ID does not match the preregistered R2 runtime\n' >&2
  exit 1
}
for label_and_value in \
  "neural.download.kernel.head=${kernel_head}" \
  "neural.download.kernel.patch.sha256=${patch_sha256}" \
  "neural.download.kernel.xpu-extension.sha256=${xpu_extension_sha256}" \
  "neural.download.kernel.gdn-library.sha256=${gdn_library_sha256}"; do
  label=${label_and_value%%=*}
  expected=${label_and_value#*=}
  [[ "$(docker image inspect "${image}" --format "{{ index .Config.Labels \"${label}\" }}")" == \
    "${expected}" ]] || { printf 'image label mismatch: %s\n' "${label}" >&2; exit 1; }
done
if [[ -n "${DYNAMIC_MAMBA_PATCH_SHA256:-}" ]]; then
  [[ "$(docker image inspect "${image}" --format '{{ index .Config.Labels "neural.download.vllm.dynamic-mamba-allocation.patch.sha256" }}')" == \
    "${DYNAMIC_MAMBA_PATCH_SHA256}" ]] || {
    printf 'dynamic Mamba allocation patch label mismatch\n' >&2
    exit 1
  }
fi
if [[ -n "${DYNAMIC_SD_LATCH_PATCH_SHA256:-}" ]]; then
  [[ "$(docker image inspect "${image}" --format '{{ index .Config.Labels "neural.download.vllm.dynamic-sd-latch.patch.sha256" }}')" == \
    "${DYNAMIC_SD_LATCH_PATCH_SHA256}" ]] || {
    printf 'dynamic SD latch patch label mismatch\n' >&2
    exit 1
  }
fi
if docker ps -a --format '{{.Names}}' | grep -Fxq "${container}"; then
  printf 'container already exists: %s\n' "${container}" >&2
  exit 1
fi
[[ ! -e "${cache_dir}" ]] || {
  printf 'R2 requires a new cache directory: %s\n' "${cache_dir}" >&2
  exit 1
}
mkdir -p "${cache_dir}"

container_lifecycle=(--rm)
if [[ "${KEEP_CONTAINER:-0}" == "1" ]]; then
  container_lifecycle=()
fi

dynamic_sd_env=()
if [[ "${DYNAMIC_SD_LATCH_PEAK_BATCH:-0}" == "1" ]]; then
  dynamic_sd_env=(--env VLLM_DYNAMIC_SD_LATCH_PEAK_BATCH=1)
fi

exec docker run "${container_lifecycle[@]}" --name "${container}" \
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
  "${dynamic_sd_env[@]}" \
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
  --gpu-memory-utilization 0.96 \
  --max-model-len "${max_model_len}" --block-size 64 \
  --max-num-seqs "${max_num_seqs}" --max-num-batched-tokens "${max_num_batched_tokens}" \
  --no-enable-prefix-caching --enable-prompt-tokens-details \
  --language-model-only \
  --speculative-config "${speculative_config}" \
  --compilation-config '{"cudagraph_mode":"PIECEWISE","cudagraph_capture_sizes":[1],"max_cudagraph_capture_size":1}'
