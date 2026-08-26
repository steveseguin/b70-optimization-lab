#!/usr/bin/env bash
set -Eeuo pipefail

campaign="qwen38-flash-next-fp8-tp4-ep4-eager-mtp0-512-r1"
ack="RUN ${campaign}"

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

if [[ "${1:-}" != "--execute" || "${2:-}" != "--ack" || "${3:-}" != "${ack}" || $# != 3 ]]; then
  printf 'First-load launcher is fail-closed. To run exactly this identity:\n' >&2
  printf '  %q --execute --ack %q\n' "$0" "${ack}" >&2
  exit 2
fi

model="${MODEL_PATH:-/mnt/usb-models/llm-models/Qwen3.8-Flash-Next-FP8}"
stage="${KERNEL_STAGE:-/mnt/usb-models/qwen38-build/runtime-core-moe-1b0e26a-b70}"
vllm_src="${VLLM_SRC:-/home/steve/src/vllm-current-main}"
kernels_src="${KERNELS_SRC:-/home/steve/src/vllm-xpu-kernels}"
python="${VLLM_PYTHON:-/home/steve/.venvs/vllm-xpu/bin/python}"
vllm_bin="${VLLM_BIN:-/home/steve/.venvs/vllm-xpu/bin/vllm}"
attempt="${ATTEMPT:-1}"
port="${PORT:-19638}"
run_parent="${RUN_PARENT:-/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70}"
cache_parent="${CACHE_PARENT:-/mnt/usb-models/llm-runtime/qwen38-flash-next-fp8-b70}"
run_dir="${run_parent}/${campaign}-attempt${attempt}"
cache_dir="${cache_parent}/${campaign}-attempt${attempt}"
server_log="${run_dir}/server.log"

expected_vllm_head="48a350bcf63e83a1d87d361415088113b038a662"
expected_kernels_head="7cf216774fb3c5eabf20d1f481d6548682604c37"
expected_model_index_sha="0419e2c2dfbb925257d7409405433a793cf7ff7d96f3eba882a815ec6d9fe7a6"
expected_model_config_sha="99c11efba4012d0f760f4e4831a8d6cafd845044e21d0aa9e6d9e70a15a90a8d"

[[ "${attempt}" =~ ^[1-9][0-9]*$ ]] || fail "ATTEMPT must be a positive integer"
[[ "${port}" =~ ^[1-9][0-9]*$ ]] || fail "PORT must be a positive integer"
[[ -x "${python}" && -x "${vllm_bin}" ]] || fail "pinned vLLM virtual environment is missing"
[[ -d "${model}" && -d "${stage}/vllm_xpu_kernels" ]] || fail "model or staged runtime is missing"
[[ -d "${vllm_src}/.git" && -d "${kernels_src}/.git" ]] || fail "source checkout is missing"
[[ ! -e "${run_dir}" ]] || fail "refusing to overwrite ${run_dir}"
[[ ! -e "${cache_dir}" ]] || fail "refusing to reuse ${cache_dir}"
[[ -z "${VLLM_PLE_CPU_OFFLOAD+x}" ]] || fail "VLLM_PLE_CPU_OFFLOAD must be absent"

[[ "$(git -C "${vllm_src}" rev-parse HEAD)" == "${expected_vllm_head}" ]] || fail "vLLM overlay head changed"
[[ "$(git -C "${kernels_src}" rev-parse HEAD)" == "${expected_kernels_head}" ]] || fail "kernel overlay head changed"
git -C "${vllm_src}" diff --quiet || fail "vLLM overlay has tracked modifications"
git -C "${kernels_src}" diff --quiet || fail "kernel overlay has tracked modifications"

[[ "$(find "${model}" -maxdepth 1 -type f | wc -l)" == 144 ]] || fail "model root inventory changed"
[[ "$(find "${model}" -maxdepth 1 -type f -name 'model-*.safetensors' | wc -l)" == 131 ]] || fail "model shard count changed"
printf '%s  %s\n' "${expected_model_index_sha}" "${model}/model.safetensors.index.json" | sha256sum -c -
printf '%s  %s\n' "${expected_model_config_sha}" "${model}/config.json" | sha256sum -c -

declare -A expected_runtime=(
  ["_C.abi3.so"]="fbdc570d3b056fbef662e5b3e72ec928ed90058a6f6c57615c4f6451da5aaa36"
  ["_moe_C.abi3.so"]="c71e818c8a3affb586b5a3437c583430a00293fbf6d93f0090f9e1748402e5a3"
  ["_xpu_C.abi3.so"]="8f11e716910289c9e53b770fab14231c040ac5b08ea7830947390ac0fb674496"
  ["_vllm_fa2_C.abi3.so"]="20b67fa13aa629f9c7ede0edbc4e53f2c6e69c729de13087014ef284470eeb51"
  ["libgdn_attn_kernels_xe_2.so"]="e7b9757a317157bb4a63159cc38ad3fc302135ca72954807d189420bbcf1595e"
  ["libgrouped_gemm_xe_2.so"]="d30e4f776088a58252da3c35f43ef060ee1872d38afd4c6b329b6f51fc50e488"
)
for binary in "${!expected_runtime[@]}"; do
  path="${stage}/vllm_xpu_kernels/${binary}"
  [[ -f "${path}" ]] || fail "staged runtime file missing: ${binary}"
  [[ "$(sha256sum "${path}" | cut -d' ' -f1)" == "${expected_runtime[${binary}]}" ]] || fail "staged runtime hash changed: ${binary}"
done

exec 7>/tmp/b70-benchmark.lock
flock -n 7 || fail "host-wide benchmark lock is held"
for gpu in 0 1 2 3; do
  eval "exec $((8 + gpu))>/tmp/b70-gpu${gpu}.lock"
  flock -n "$((8 + gpu))" || fail "GPU ${gpu} lock is held"
done
pgrep -af '(^|/)(vllm|python)( |.* )serve ' >/dev/null && fail "another vLLM server is running"
ss -ltn 2>/dev/null | grep -q ":${port} " && fail "port ${port} is already open"

mkdir -p "${run_dir}" "${cache_dir}/vllm" "${cache_dir}/torchinductor" \
  "${cache_dir}/triton" "${cache_dir}/xdg" "${cache_dir}/tmp"

source /opt/intel/oneapi/compiler/2025.3/env/vars.sh >/dev/null 2>&1
export PYTHONPATH="${stage}:${vllm_src}"
export LD_LIBRARY_PATH="${stage}/vllm_xpu_kernels:/home/steve/.venvs/vllm-xpu/lib:/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/lib${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"
export HF_HOME="${cache_dir}/hf"
export HUGGINGFACE_HUB_CACHE="${cache_dir}/hf"
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export VLLM_CACHE_ROOT="${cache_dir}/vllm"
export TORCHINDUCTOR_CACHE_DIR="${cache_dir}/torchinductor"
export TRITON_CACHE_DIR="${cache_dir}/triton"
export XDG_CACHE_HOME="${cache_dir}/xdg"
export TMPDIR="${cache_dir}/tmp"

export ZE_AFFINITY_MASK=0,1,2,3
unset ONEAPI_DEVICE_SELECTOR SYCL_DEVICE_FILTER SYCL_DEVICE_ALLOWLIST
export VLLM_TARGET_DEVICE=xpu
export VLLM_USE_V1=1
export VLLM_WORKER_MULTIPROC_METHOD=spawn
export VLLM_NO_USAGE_STATS=1
export PYTHONHASHSEED=0
export PYTORCH_ALLOC_CONF=expandable_segments:True
export OMP_NUM_THREADS=1

unset VLLM_PLE_CPU_OFFLOAD
unset VLLM_XPU_FP8_BLOCK_W8A16 VLLM_XPU_FORCE_GRAPH_WITH_COMM \
  VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE VLLM_XPU_GDN_NATIVE_FALLBACK
export XPU_GRAPH=0
export VLLM_XPU_GRAPH=0
export VLLM_XPU_ENABLE_XPU_GRAPH=0
export VLLM_XPU_FORCE_GRAPH_WITH_COMM=0
export VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE=0

export CCL_ATL_TRANSPORT=ofi
export FI_PROVIDER=tcp
export FI_TCP_IFACE=lo
export CCL_ZE_IPC_EXCHANGE=pidfd
export CCL_SEND=direct
export CCL_RECV=direct
export CCL_TOPO_P2P_ACCESS=1
export CCL_SYCL_ALLREDUCE_SIMPLE_THRESHOLD=4294967296
export CCL_SYCL_ALLGATHERV_SIMPLE_THRESHOLD=4294967296
export CCL_SYCL_REDUCE_SCATTER_SIMPLE_THRESHOLD=4294967296

export Q38_KERNEL_STAGE="${stage}"
"${python}" - <<'PY' >"${run_dir}/staged-runtime-preflight.txt"
import importlib
import os
import pathlib
import torch
import vllm_xpu_kernels

root = pathlib.Path(os.environ['Q38_KERNEL_STAGE']).resolve()
modules = [
    vllm_xpu_kernels,
    importlib.import_module('vllm_xpu_kernels._C'),
    importlib.import_module('vllm_xpu_kernels._moe_C'),
]
for module in modules:
    path = pathlib.Path(module.__file__).resolve()
    assert path.is_relative_to(root), (path, root)
    print(f'{module.__name__}={path}')
for namespace, op in [('_C', 'per_token_group_fp8_quant'), ('_moe_C', 'topk_softmax')]:
    print(torch._C._dispatch_find_schema_or_throw(f'{namespace}::{op}', '').schema())
print(f'xpu_device_count={torch.xpu.device_count()}')
assert torch.xpu.device_count() == 4
PY

{
  printf 'campaign=%s\n' "${campaign}"
  printf 'model=%s\n' "${model}"
  printf 'vllm_head=%s\n' "${expected_vllm_head}"
  printf 'kernels_head=%s\n' "${expected_kernels_head}"
  printf 'stage=%s\n' "${stage}"
  printf 'offload_backend=uva\n'
  printf 'cpu_offload_gb=12\n'
  printf 'cpu_offload_params=ple_embedding.ngram_embedding.weight\n'
  printf 'ple_cpu_process=absent\n'
  printf 'tp=4 ep=4 all2all=allgather_reducescatter\n'
  printf 'moe_backend=triton eager=1 mtp=0 max_model_len=512\n'
} >"${run_dir}/identity.txt"

sha256sum "${model}/config.json" "${model}/model.safetensors.index.json" \
  "${stage}/vllm_xpu_kernels/_C.abi3.so" \
  "${stage}/vllm_xpu_kernels/_moe_C.abi3.so" \
  "${stage}/vllm_xpu_kernels/_xpu_C.abi3.so" \
  "${stage}/vllm_xpu_kernels/_vllm_fa2_C.abi3.so" \
  "${stage}/vllm_xpu_kernels/libgdn_attn_kernels_xe_2.so" \
  "${stage}/vllm_xpu_kernels/libgrouped_gemm_xe_2.so" \
  >"${run_dir}/input-sha256sums.txt"

args=(
  "${model}"
  --host 127.0.0.1
  --port "${port}"
  --served-model-name qwen38-flash-next-fp8-tp4
  --tokenizer "${model}"
  --dtype bfloat16
  --tensor-parallel-size 4
  --pipeline-parallel-size 1
  --data-parallel-size 1
  --distributed-executor-backend mp
  --enable-expert-parallel
  --all2all-backend allgather_reducescatter
  --language-model-only
  --moe-backend triton
  --enforce-eager
  --max-model-len 512
  --max-num-seqs 1
  --max-num-batched-tokens 512
  --no-enable-prefix-caching
  --offload-backend uva
  --cpu-offload-gb 12
  --cpu-offload-params ple_embedding.ngram_embedding.weight
  --gpu-memory-utilization 0.92
  --kv-cache-dtype auto
  --block-size 64
  --generation-config vllm
  --load-format safetensors
  --no-async-scheduling
  --enable-prompt-tokens-details
  --disable-uvicorn-access-log
)
printf '%q ' "${vllm_bin}" serve "${args[@]}" >"${run_dir}/server-command.shell.txt"
printf '\n' >>"${run_dir}/server-command.shell.txt"

printf 'Launching %s; log=%s\n' "${campaign}" "${server_log}"
exec "${vllm_bin}" serve "${args[@]}" >"${server_log}" 2>&1
