#!/usr/bin/env bash
set -euo pipefail

mode=${EXECUTION_MODE:?set EXECUTION_MODE to eager or compiled}
image=${IMAGE:-neural-download/vllm-openai-xpu:qwen38-autoround-current-deterministic-r1}
expected_image_id=${EXPECTED_IMAGE_ID:?set EXPECTED_IMAGE_ID to the locally rebuilt image ID}
expected_core_extension_sha256=${EXPECTED_CORE_EXTENSION_SHA256:?set EXPECTED_CORE_EXTENSION_SHA256}
model=${MODEL_DIR:?set MODEL_DIR to the verified AutoRound model directory}
cache=${VLLM_CACHE_DIR:?set VLLM_CACHE_DIR to a new empty cache directory}
container=${CONTAINER_NAME:?set CONTAINER_NAME to a unique name}
port=${PORT:?set PORT to a unique host port}
served_model=${SERVED_MODEL_NAME:-qwen38-autoround-deterministic-mtp0}

case "$mode" in eager|compiled) ;; *) printf 'EXECUTION_MODE must be eager or compiled\n' >&2; exit 2;; esac
[[ "$port" =~ ^[1-9][0-9]*$ ]] || { printf 'PORT must be positive\n' >&2; exit 2; }
[[ -d "$model" && ! -L "$model" ]] || { printf 'MODEL_DIR must be a real directory\n' >&2; exit 1; }
[[ "$(findmnt -n -o FSTYPE -T "$model")" == ext4 ]] || { printf 'MODEL_DIR must be on ext4\n' >&2; exit 1; }
[[ ! -e "$cache" ]] || { printf 'cache path must be new: %s\n' "$cache" >&2; exit 1; }
[[ "$(docker image inspect "$image" --format '{{.Id}}')" == "$expected_image_id" ]] || {
  printf 'image identity mismatch\n' >&2; exit 1;
}
[[ "$(docker image inspect "$image" --format '{{ index .Config.Labels "neural.download.kernel.head" }}')" == \
  1e90ffa672ba02f17a909da11838a4c55b199783 ]] || {
  printf 'kernel source identity mismatch\n' >&2; exit 1;
}
[[ "$(docker image inspect "$image" --format '{{ index .Config.Labels "neural.download.kernel.patch.sha256" }}')" == \
  8a2f1cc49d516eeb9093e0b99c4c5ed6b74f76196417fa8951e1f8c3e7405168 ]] || {
  printf 'INT4 determinism patch identity mismatch\n' >&2; exit 1;
}
[[ "$(docker image inspect "$image" --format '{{ index .Config.Labels "neural.download.kernel.core-extension.sha256" }}')" == \
  "$expected_core_extension_sha256" ]] || {
  printf 'core extension label mismatch\n' >&2; exit 1;
}

expected_files=$(mktemp)
actual_files=$(mktemp)
cleanup_tmp() { rm -f -- "$expected_files" "$actual_files"; }
trap cleanup_tmp EXIT
cat >"$expected_files" <<'EOF'
7c36e4a8dab4bfc06b1d5be2d8466e8cdc94099dd5409424fecc6dd8ffc2c208  /opt/venv/lib/python3.12/site-packages/vllm/model_executor/kernels/linear/scaled_mm/xpu.py
f3273ccfb41be44c3c02080c26df10e8b200060366b900d940803f4221224c59  /opt/venv/lib/python3.12/site-packages/vllm/_xpu_ops.py
7afb4de8b87d7f180d696f7cadad8b9d48d9ab7b706ae19616425c4f9456fb19  /opt/venv/lib/python3.12/site-packages/vllm/model_executor/layers/mamba/gdn/qwen_gdn_linear_attn.py
5ab2ea5d9e049e6b53e2d56d1e3419ce01d1988e8be5295bab1f912a7fdbf74d  /opt/venv/lib/python3.12/site-packages/vllm/distributed/device_communicators/xpu_communicator.py
50cf5f4f9c72f679e4318cd3e3e021a844f59ac188a891d9a4f9638188f4bce8  /opt/venv/lib/python3.12/site-packages/vllm/model_executor/layers/layernorm.py
EOF
printf '%s  %s\n' "$expected_core_extension_sha256" \
  /opt/venv/lib/python3.12/site-packages/vllm_xpu_kernels/_C.abi3.so \
  >>"$expected_files"
docker run --rm --entrypoint sha256sum "$image" \
  /opt/venv/lib/python3.12/site-packages/vllm/model_executor/kernels/linear/scaled_mm/xpu.py \
  /opt/venv/lib/python3.12/site-packages/vllm/_xpu_ops.py \
  /opt/venv/lib/python3.12/site-packages/vllm/model_executor/layers/mamba/gdn/qwen_gdn_linear_attn.py \
  /opt/venv/lib/python3.12/site-packages/vllm/distributed/device_communicators/xpu_communicator.py \
  /opt/venv/lib/python3.12/site-packages/vllm/model_executor/layers/layernorm.py \
  /opt/venv/lib/python3.12/site-packages/vllm_xpu_kernels/_C.abi3.so \
  >"$actual_files"
cmp -s "$expected_files" "$actual_files" || { printf 'patched image file identities mismatch\n' >&2; exit 1; }
docker run --rm --entrypoint strings "$image" \
  /opt/venv/lib/python3.12/site-packages/vllm_xpu_kernels/_C.abi3.so \
  | grep -Fq VLLM_XPU_ONEDNN_INT4_DETERMINISM_PAD || {
    printf 'INT4 determinism marker missing\n' >&2; exit 1;
  }

docker ps -a --format '{{.Names}}' | grep -Fxq "$container" && { printf 'container exists\n' >&2; exit 1; }
ss -ltn | grep -Eq ":${port}[[:space:]]" && { printf 'port occupied\n' >&2; exit 1; }
(( $(awk '/MemAvailable/ {print $2}' /proc/meminfo) >= 80 * 1024 * 1024 )) || {
  printf 'less than 80 GiB host memory available\n' >&2; exit 1;
}

exec 7>/tmp/b70-benchmark.lock
flock -n 7 || { printf 'benchmark lock held\n' >&2; exit 1; }
exec 8>/tmp/b70-gpu2.lock
flock -n 8 || { printf 'GPU2 lock held\n' >&2; exit 1; }
exec 9>/tmp/b70-gpu3.lock
flock -n 9 || { printf 'GPU3 lock held\n' >&2; exit 1; }

mkdir -p "$cache"
mode_args=()
if [[ "$mode" == eager ]]; then mode_args=(--enforce-eager); fi

trap - EXIT
cleanup_tmp
exec docker run --rm --name "$container" \
  --ulimit core=0 --memory 96g --memory-swap 104g \
  --device /dev/dri:/dev/dri --group-add render --cap-add SYS_PTRACE \
  --security-opt label=disable --ipc=host --shm-size=16g \
  --publish "127.0.0.1:${port}:8000" \
  --volume "$model:/model:ro" --volume "$cache:/root/.cache/vllm" \
  --env ZE_AFFINITY_MASK=2,3 --env ONEAPI_DEVICE_SELECTOR=level_zero:2,3 \
  --env VLLM_TARGET_DEVICE=xpu --env VLLM_WORKER_MULTIPROC_METHOD=spawn \
  --env VLLM_NO_USAGE_STATS=1 --env PYTHONHASHSEED=0 \
  --env VLLM_XPU_ENABLE_XPU_GRAPH=0 --env VLLM_XPU_GRAPH=0 \
  --env VLLM_XPU_FP8_BLOCK_W8A16=0 \
  --env VLLM_XPU_ONEDNN_INT4_DETERMINISM_PAD=1 \
  --env VLLM_XPU_QWEN_GEMMA_RMSNORM_PACKED_SERIAL_EXACT=1 \
  --env VLLM_XPU_GDN_SPEC_PERSISTENT_SCRATCH=1 \
  --env VLLM_XPU_GDN_NATIVE_FALLBACK=1 \
  --env TORCHINDUCTOR_DETERMINISTIC=1 \
  --env PYTORCH_ALLOC_CONF=expandable_segments:True \
  --env CCL_ATL_TRANSPORT=ofi --env FI_PROVIDER=tcp --env FI_TCP_IFACE=lo \
  --env CCL_ZE_IPC_EXCHANGE=pidfd --env CCL_SEND=direct --env CCL_RECV=direct \
  --env CCL_TOPO_P2P_ACCESS=1 \
  --env CCL_SYCL_ALLREDUCE_SIMPLE_THRESHOLD=4294967296 \
  --env CCL_SYCL_ALLGATHERV_SIMPLE_THRESHOLD=4294967296 \
  --env CCL_SYCL_REDUCE_SCATTER_SIMPLE_THRESHOLD=4294967296 \
  "$image" --model /model --tokenizer /model --served-model-name "$served_model" \
  --host 0.0.0.0 --port 8000 --trust-remote-code \
  --tensor-parallel-size 2 --dtype float16 --kv-cache-dtype auto \
  --gpu-memory-utilization 0.80 --max-model-len 1024 --block-size 64 \
  --max-num-seqs 1 --max-num-batched-tokens 1024 \
  --no-enable-prefix-caching --enable-prompt-tokens-details \
  --language-model-only "${mode_args[@]}" \
  --compilation-config '{"cudagraph_mode":"NONE"}'
