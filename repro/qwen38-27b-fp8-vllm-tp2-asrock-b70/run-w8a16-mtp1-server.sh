#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
image=${IMAGE:-neural-download/vllm-openai-xpu:f01e-kernel-1e90-w8a16-r122}
model_dir=${MODEL_DIR:?set MODEL_DIR to the downloaded Qwen3.8-27B-FP8 directory}
cache_dir=${VLLM_CACHE_DIR:?set VLLM_CACHE_DIR to a new writable cache directory}
container=${CONTAINER_NAME:-qwen38-fp8-block-w8a16-mtp1-tp2-p128}
port=${PORT:-18124}
served_model=${SERVED_MODEL_NAME:-qwen38-fp8-block-w8a16-mtp1}
speculative_config=${SPECULATIVE_CONFIG:-'{"method":"qwen3_next_mtp","num_speculative_tokens":1}'}
# Match the independently compiled R54 target oracle. These settings must live
# inside vLLM's compile context; environment-only determinism was insufficient.
compilation_config=${COMPILATION_CONFIG:-'{"cudagraph_mode":"PIECEWISE","cudagraph_capture_sizes":[1],"max_cudagraph_capture_size":1,"inductor_compile_config":{"combo_kernels":false,"benchmark_combo_kernel":false,"deterministic":true,"triton.autotune_pointwise":false,"benchmark_epilogue_fusion":false}}'}
max_num_seqs=${MAX_NUM_SEQS:-128}
max_model_len=${MAX_MODEL_LEN:-256}
max_num_batched_tokens=${MAX_NUM_BATCHED_TOKENS:-512}
gpu_memory_utilization=${GPU_MEMORY_UTILIZATION:-0.96}
container_memory=${CONTAINER_MEMORY:-9g}
container_memory_swap=${CONTAINER_MEMORY_SWAP:-12g}
xpu_graph=${VLLM_XPU_ENABLE_XPU_GRAPH:-1}
enforce_eager=${ENFORCE_EAGER:-0}
fp8_block_w8a16=${VLLM_XPU_FP8_BLOCK_W8A16:-1}
fp8_packed_serial_exact=${VLLM_XPU_FP8_PACKED_SERIAL_EXACT:-0}
fa_serial_spec_decode=${VLLM_XPU_FA_SERIAL_SPEC_DECODE:-0}
fa_serial_spec_no_causal=${VLLM_XPU_FA_SERIAL_SPEC_NO_CAUSAL:-0}
batch_invariant=${VLLM_BATCH_INVARIANT:-0}
qwen_gemma_rmsnorm_batch_invariant=${VLLM_XPU_QWEN_GEMMA_RMSNORM_BATCH_INVARIANT:-0}
qwen_gemma_rmsnorm_packed_serial_exact=${VLLM_XPU_QWEN_GEMMA_RMSNORM_PACKED_SERIAL_EXACT:-0}
gdn_serial_exact=${VLLM_XPU_GDN_NATIVE_SPEC_RECURRENT_SERIAL_EXACT:-0}
gdn_conv_serial_exact=${VLLM_XPU_GDN_NATIVE_SPEC_CONV_SERIAL_EXACT:-0}
gdn_delta_serial_exact=${VLLM_XPU_GDN_NATIVE_SPEC_DELTA_SERIAL_EXACT:-0}
gdn_multi_request_split=${VLLM_XPU_GDN_NATIVE_SPEC_MULTI_REQUEST_SPLIT:-0}
gdn_spec_metadata_trace=${VLLM_XPU_GDN_NATIVE_SPEC_METADATA_TRACE:-0}
gdn_spec_evolving_metadata_trace=${VLLM_XPU_GDN_NATIVE_SPEC_EVOLVING_METADATA_TRACE:-0}
gdn_persistent_scratch=${VLLM_XPU_GDN_SPEC_PERSISTENT_SCRATCH:-0}
gdn_native_fallback=${VLLM_XPU_GDN_NATIVE_FALLBACK:-1}
mtp_suppress_bonus=${VLLM_XPU_MTP_SUPPRESS_BONUS_TOKEN:-0}
mtp_draft_eager=${VLLM_XPU_MTP_DRAFT_EAGER:-0}
inductor_deterministic=${TORCHINDUCTOR_DETERMINISTIC:-0}
inductor_max_autotune=${VLLM_ENABLE_INDUCTOR_MAX_AUTOTUNE:-1}
inductor_coordinate_descent=${VLLM_ENABLE_INDUCTOR_COORDINATE_DESCENT_TUNING:-1}
python_hash_seed=${PYTHONHASHSEED:-}
kernel_head=${EXPECTED_KERNEL_HEAD:-1e90ffa672ba02f17a909da11838a4c55b199783}
expected_image_id=${EXPECTED_IMAGE_ID:-}
profiler_config=${PROFILER_CONFIG:-}
profiler_dir=${PROFILER_DIR:-}
compile_allreduce_custom_op=${VLLM_XPU_COMPILE_ALLREDUCE_CUSTOM_OP:-0}
draft_lm_head_int4=${VLLM_XPU_DRAFT_LM_HEAD_INT4:-0}
draft_lm_head_int4_group_size=${VLLM_XPU_DRAFT_LM_HEAD_INT4_GROUP_SIZE:-128}
draft_lm_head_int4_scale_dtype=${VLLM_XPU_DRAFT_LM_HEAD_INT4_SCALE_DTYPE:-bf16}
draft_lm_head_int4_chunk_rows=${VLLM_XPU_DRAFT_LM_HEAD_INT4_CHUNK_ROWS:-2048}
lm_head_batch_invariant=${VLLM_XPU_LM_HEAD_BATCH_INVARIANT:-0}
lm_head_batch_repair_rows=${VLLM_XPU_LM_HEAD_BATCH_REPAIR_ROWS:-0}
lm_head_batch_repair_margin=${VLLM_XPU_LM_HEAD_BATCH_REPAIR_MARGIN:-0.25}
lm_head_global_batch_repair_margin=${VLLM_XPU_LM_HEAD_GLOBAL_BATCH_REPAIR_MARGIN:-0}

for value_name in max_num_seqs max_model_len max_num_batched_tokens; do
  value=${!value_name}
  [[ "${value}" =~ ^[1-9][0-9]*$ ]] || {
    printf '%s must be positive\n' "${value_name^^}" >&2
    exit 1
  }
done
[[ "${gpu_memory_utilization}" =~ ^0\.[0-9]+$ ]] || {
  printf 'GPU_MEMORY_UTILIZATION must be between 0 and 1\n' >&2
  exit 1
}
[[ "${container_memory}" =~ ^[1-9][0-9]*[gGmM]$ ]] || {
  printf 'CONTAINER_MEMORY must be a positive Docker memory value such as 9g\n' >&2
  exit 1
}
[[ "${container_memory_swap}" =~ ^[1-9][0-9]*[gGmM]$ ]] || {
  printf 'CONTAINER_MEMORY_SWAP must be a positive Docker memory value such as 12g\n' >&2
  exit 1
}
[[ "${xpu_graph}" == 0 || "${xpu_graph}" == 1 ]] || {
  printf 'VLLM_XPU_ENABLE_XPU_GRAPH must be 0 or 1\n' >&2
  exit 1
}
[[ "${enforce_eager}" == 0 || "${enforce_eager}" == 1 ]] || {
  printf 'ENFORCE_EAGER must be 0 or 1\n' >&2
  exit 1
}
for value_name in fp8_block_w8a16 fp8_packed_serial_exact \
  fa_serial_spec_decode fa_serial_spec_no_causal batch_invariant \
  qwen_gemma_rmsnorm_batch_invariant \
  qwen_gemma_rmsnorm_packed_serial_exact \
  gdn_serial_exact gdn_conv_serial_exact gdn_delta_serial_exact \
  gdn_multi_request_split gdn_spec_metadata_trace \
  gdn_spec_evolving_metadata_trace \
  gdn_persistent_scratch gdn_native_fallback \
  mtp_suppress_bonus mtp_draft_eager; do
  value=${!value_name}
  [[ "${value}" == 0 || "${value}" == 1 ]] || {
    printf '%s must be 0 or 1\n' "${value_name^^}" >&2
    exit 1
  }
done
if [[ "${gdn_multi_request_split}" == 1 ]]; then
  gdn_split_stage_count=$((gdn_conv_serial_exact + gdn_delta_serial_exact))
  [[ "${gdn_serial_exact}" == 0 && "${gdn_split_stage_count}" -ge 1 ]] || {
    printf 'VLLM_XPU_GDN_NATIVE_SPEC_MULTI_REQUEST_SPLIT requires one or both split GDN stages and disables the legacy combined recurrent gate\n' >&2
    exit 1
  }
fi
[[ "${inductor_deterministic}" == 0 || "${inductor_deterministic}" == 1 ]] || {
  printf 'TORCHINDUCTOR_DETERMINISTIC must be 0 or 1\n' >&2
  exit 1
}
for value_name in inductor_max_autotune inductor_coordinate_descent; do
  value=${!value_name}
  [[ "${value}" == 0 || "${value}" == 1 ]] || {
    printf '%s must be 0 or 1\n' "${value_name^^}" >&2
    exit 1
  }
done
[[ "${draft_lm_head_int4}" == 0 || "${draft_lm_head_int4}" == 1 ]] || {
  printf 'VLLM_XPU_DRAFT_LM_HEAD_INT4 must be 0 or 1\n' >&2
  exit 1
}
[[ "${lm_head_batch_invariant}" == 0 || "${lm_head_batch_invariant}" == 1 ]] || {
  printf 'VLLM_XPU_LM_HEAD_BATCH_INVARIANT must be 0 or 1\n' >&2
  exit 1
}
[[ "${lm_head_batch_repair_rows}" =~ ^[0-9]+$ ]] || {
  printf 'VLLM_XPU_LM_HEAD_BATCH_REPAIR_ROWS must be a non-negative integer\n' >&2
  exit 1
}
[[ "${lm_head_batch_repair_margin}" =~ ^[0-9]+([.][0-9]+)?$ ]] || {
  printf 'VLLM_XPU_LM_HEAD_BATCH_REPAIR_MARGIN must be a non-negative number\n' >&2
  exit 1
}
[[ "${lm_head_global_batch_repair_margin}" =~ ^[0-9]+([.][0-9]+)?$ ]] || {
  printf 'VLLM_XPU_LM_HEAD_GLOBAL_BATCH_REPAIR_MARGIN must be a non-negative number\n' >&2
  exit 1
}
[[ "${draft_lm_head_int4_group_size}" =~ ^[1-9][0-9]*$ ]] || {
  printf 'VLLM_XPU_DRAFT_LM_HEAD_INT4_GROUP_SIZE must be positive\n' >&2
  exit 1
}
[[ "${draft_lm_head_int4_chunk_rows}" =~ ^[1-9][0-9]*$ ]] || {
  printf 'VLLM_XPU_DRAFT_LM_HEAD_INT4_CHUNK_ROWS must be positive\n' >&2
  exit 1
}
case "${draft_lm_head_int4_scale_dtype}" in
  bf16|bfloat16|fp16|float16|half|fp32|float32) ;;
  *)
    printf 'VLLM_XPU_DRAFT_LM_HEAD_INT4_SCALE_DTYPE is invalid\n' >&2
    exit 1
    ;;
esac
[[ -z "${python_hash_seed}" || "${python_hash_seed}" =~ ^[0-9]+$ ]] || {
  printf 'PYTHONHASHSEED must be an unsigned integer when set\n' >&2
  exit 1
}

"${script_dir}/verify-model-direct.sh" "${model_dir}"
command -v docker >/dev/null || { printf 'docker is required\n' >&2; exit 1; }
docker image inspect "${image}" >/dev/null 2>&1 || {
  printf 'image is missing: %s\nBuild the kernel and W8A16 overlays first.\n' "${image}" >&2
  exit 1
}
if [[ -n "${expected_image_id}" && "$(docker image inspect "${image}" --format '{{.Id}}')" != "${expected_image_id}" ]]; then
  printf 'image identity mismatch: expected %s\n' "${expected_image_id}" >&2
  exit 1
fi
[[ "$(docker image inspect "${image}" --format '{{ index .Config.Labels "neural.download.kernel.head" }}')" == "${kernel_head}" ]] || {
  printf 'image does not contain the required mixed-batch XPU kernel: %s\n' "${kernel_head}" >&2
  exit 1
}
if docker ps -a --format '{{.Names}}' | grep -Fxq "${container}"; then
  printf 'container already exists: %s\n' "${container}" >&2
  exit 1
fi
mkdir -p "${cache_dir}"

eager_args=()
if [[ "${enforce_eager}" == 1 ]]; then
  eager_args=(--enforce-eager)
fi
hash_seed_args=()
if [[ -n "${python_hash_seed}" ]]; then
  hash_seed_args=(--env "PYTHONHASHSEED=${python_hash_seed}")
fi
profiler_mount_args=()
profiler_cli_args=()
if [[ -n "${profiler_config}" ]]; then
  [[ -n "${profiler_dir}" ]] || {
    printf 'PROFILER_DIR is required when PROFILER_CONFIG is set\n' >&2
    exit 1
  }
  mkdir -p "${profiler_dir}"
  profiler_mount_args=(--volume "${profiler_dir}:/profiles")
  profiler_cli_args=(--profiler-config "${profiler_config}")
elif [[ -n "${profiler_dir}" ]]; then
  printf 'PROFILER_CONFIG is required when PROFILER_DIR is set\n' >&2
  exit 1
fi

exec docker run --rm --name "${container}" \
  --ulimit core=0 \
  --memory "${container_memory}" --memory-swap "${container_memory_swap}" \
  --device /dev/dri:/dev/dri --group-add render \
  --cap-add SYS_PTRACE --security-opt label=disable \
  --ipc=host --shm-size=8g \
  --publish "127.0.0.1:${port}:8000" \
  --volume "${model_dir}:/model:ro" \
  --volume "${cache_dir}:/root/.cache/vllm" \
  "${profiler_mount_args[@]}" \
  --env ZE_AFFINITY_MASK=0,1 \
  --env ONEAPI_DEVICE_SELECTOR=level_zero:0,1 \
  --env VLLM_TARGET_DEVICE=xpu \
  --env VLLM_WORKER_MULTIPROC_METHOD=spawn \
  --env VLLM_XPU_ENABLE_XPU_GRAPH="${xpu_graph}" \
  --env VLLM_XPU_FP8_BLOCK_W8A16="${fp8_block_w8a16}" \
  --env VLLM_XPU_FP8_PACKED_SERIAL_EXACT="${fp8_packed_serial_exact}" \
  --env VLLM_XPU_FA_SERIAL_SPEC_DECODE="${fa_serial_spec_decode}" \
  --env VLLM_XPU_FA_SERIAL_SPEC_NO_CAUSAL="${fa_serial_spec_no_causal}" \
  --env VLLM_BATCH_INVARIANT="${batch_invariant}" \
  --env VLLM_XPU_QWEN_GEMMA_RMSNORM_BATCH_INVARIANT="${qwen_gemma_rmsnorm_batch_invariant}" \
  --env VLLM_XPU_QWEN_GEMMA_RMSNORM_PACKED_SERIAL_EXACT="${qwen_gemma_rmsnorm_packed_serial_exact}" \
  --env VLLM_XPU_GDN_NATIVE_SPEC_RECURRENT_SERIAL_EXACT="${gdn_serial_exact}" \
  --env VLLM_XPU_GDN_NATIVE_SPEC_CONV_SERIAL_EXACT="${gdn_conv_serial_exact}" \
  --env VLLM_XPU_GDN_NATIVE_SPEC_DELTA_SERIAL_EXACT="${gdn_delta_serial_exact}" \
  --env VLLM_XPU_GDN_NATIVE_SPEC_MULTI_REQUEST_SPLIT="${gdn_multi_request_split}" \
  --env VLLM_XPU_GDN_NATIVE_SPEC_METADATA_TRACE="${gdn_spec_metadata_trace}" \
  --env VLLM_XPU_GDN_NATIVE_SPEC_EVOLVING_METADATA_TRACE="${gdn_spec_evolving_metadata_trace}" \
  --env VLLM_XPU_GDN_SPEC_PERSISTENT_SCRATCH="${gdn_persistent_scratch}" \
  --env VLLM_XPU_GDN_NATIVE_FALLBACK="${gdn_native_fallback}" \
  --env VLLM_XPU_MTP_SUPPRESS_BONUS_TOKEN="${mtp_suppress_bonus}" \
  --env VLLM_XPU_MTP_DRAFT_EAGER="${mtp_draft_eager}" \
  --env TORCHINDUCTOR_DETERMINISTIC="${inductor_deterministic}" \
  --env VLLM_ENABLE_INDUCTOR_MAX_AUTOTUNE="${inductor_max_autotune}" \
  --env VLLM_ENABLE_INDUCTOR_COORDINATE_DESCENT_TUNING="${inductor_coordinate_descent}" \
  --env VLLM_XPU_COMPILE_ALLREDUCE_CUSTOM_OP="${compile_allreduce_custom_op}" \
  --env VLLM_XPU_DRAFT_LM_HEAD_INT4="${draft_lm_head_int4}" \
  --env VLLM_XPU_DRAFT_LM_HEAD_INT4_GROUP_SIZE="${draft_lm_head_int4_group_size}" \
  --env VLLM_XPU_DRAFT_LM_HEAD_INT4_SCALE_DTYPE="${draft_lm_head_int4_scale_dtype}" \
  --env VLLM_XPU_DRAFT_LM_HEAD_INT4_CHUNK_ROWS="${draft_lm_head_int4_chunk_rows}" \
  --env VLLM_XPU_LM_HEAD_BATCH_INVARIANT="${lm_head_batch_invariant}" \
  --env VLLM_XPU_LM_HEAD_BATCH_REPAIR_ROWS="${lm_head_batch_repair_rows}" \
  --env VLLM_XPU_LM_HEAD_BATCH_REPAIR_MARGIN="${lm_head_batch_repair_margin}" \
  --env VLLM_XPU_LM_HEAD_GLOBAL_BATCH_REPAIR_MARGIN="${lm_head_global_batch_repair_margin}" \
  "${hash_seed_args[@]}" \
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
  --gpu-memory-utilization "${gpu_memory_utilization}" \
  --max-model-len "${max_model_len}" --block-size 64 \
  --max-num-seqs "${max_num_seqs}" --max-num-batched-tokens "${max_num_batched_tokens}" \
  --no-enable-prefix-caching --enable-prompt-tokens-details \
  --language-model-only \
  "${eager_args[@]}" \
  --speculative-config "${speculative_config}" \
  --compilation-config "${compilation_config}" \
  "${profiler_cli_args[@]}"
