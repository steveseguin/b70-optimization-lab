#!/usr/bin/env bash
set -Eeuo pipefail

campaign="qwen38-flash-next-fp8-tp4-ep4-eager-mtp0-512-r1"
ack="RUN ${campaign}"
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/../../.." && pwd)

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
moe_sync_trace="${Q38_MOE_SYNC_TRACE:-0}"
run_parent="${RUN_PARENT:-/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70}"
cache_parent="${CACHE_PARENT:-/mnt/usb-models/llm-runtime/qwen38-flash-next-fp8-b70}"
run_dir="${run_parent}/${campaign}-attempt${attempt}"
cache_dir="${cache_parent}/${campaign}-attempt${attempt}"
compile_cache_dir="/tmp/${campaign}-attempt${attempt}-compile"
server_log="${run_dir}/server.log"
rpc_dir="/tmp/${campaign}-attempt${attempt}-rpc"
runtime_manifest="${repo_root}/experiments/qwen38-flash-next-fp8-b70/data/runtime-stage-loadable.sha256"
validation_root="${repo_root}/data/model-intake/post-download-validation-20260826/20260826T211840Z"
moe_receipt="${repo_root}/experiments/qwen38-flash-next-fp8-b70/data/20260826-triton-block-fp8-gate.json"

expected_vllm_head="f00b56bf2423fae9dca91c7432a0bdc42451b8d1"
expected_kernels_head="7cf216774fb3c5eabf20d1f481d6548682604c37"
expected_model_index_sha="0419e2c2dfbb925257d7409405433a793cf7ff7d96f3eba882a815ec6d9fe7a6"
expected_model_config_sha="99c11efba4012d0f760f4e4831a8d6cafd845044e21d0aa9e6d9e70a15a90a8d"

[[ "${attempt}" =~ ^[1-9][0-9]*$ ]] || fail "ATTEMPT must be a positive integer"
[[ "${port}" =~ ^[1-9][0-9]*$ ]] || fail "PORT must be a positive integer"
[[ "${moe_sync_trace}" =~ ^[01]$ ]] || fail "Q38_MOE_SYNC_TRACE must be 0 or 1"
[[ -x "${python}" && -x "${vllm_bin}" ]] || fail "pinned vLLM virtual environment is missing"
[[ "$(head -1 "${vllm_bin}")" == "#!${python}" ]] || fail "vLLM wrapper does not use the pinned interpreter"
[[ -d "${model}" && -d "${stage}/vllm_xpu_kernels" ]] || fail "model or staged runtime is missing"
[[ -d "${vllm_src}/.git" && -d "${kernels_src}/.git" ]] || fail "source checkout is missing"
[[ -f "${runtime_manifest}" && -f "${validation_root}/summary.json" && -f "${moe_receipt}" ]] || fail "sealed validation input is missing"
[[ ! -e "${run_dir}" ]] || fail "refusing to overwrite ${run_dir}"
[[ ! -e "${cache_dir}" ]] || fail "refusing to reuse ${cache_dir}"
[[ ! -e "${compile_cache_dir}" ]] || fail "refusing to reuse ${compile_cache_dir}"
[[ ! -e "${rpc_dir}" ]] || fail "refusing to reuse ${rpc_dir}"
[[ -z "${VLLM_PLE_CPU_OFFLOAD+x}" ]] || fail "VLLM_PLE_CPU_OFFLOAD must be absent"

[[ "$(git -C "${vllm_src}" rev-parse HEAD)" == "${expected_vllm_head}" ]] || fail "vLLM overlay head changed"
[[ "$(git -C "${kernels_src}" rev-parse HEAD)" == "${expected_kernels_head}" ]] || fail "kernel overlay head changed"
[[ -z "$(git -C "${vllm_src}" status --porcelain)" ]] || fail "vLLM overlay is not exactly clean"
[[ -z "$(git -C "${kernels_src}" status --porcelain --untracked-files=no)" ]] || fail "kernel overlay has tracked modifications"

[[ "$(find "${model}" -maxdepth 1 -type f | wc -l)" == 144 ]] || fail "model root inventory changed"
[[ "$(find "${model}" -maxdepth 1 -type f -name 'model-*.safetensors' | wc -l)" == 131 ]] || fail "model shard count changed"
[[ "$(find "${model}" -maxdepth 1 -type f -printf '%s\n' | awk '{sum += $1} END {print sum}')" == 185563783127 ]] || fail "model byte inventory changed"
printf '%s  %s\n' "${expected_model_index_sha}" "${model}/model.safetensors.index.json" | sha256sum -c -
printf '%s  %s\n' "${expected_model_config_sha}" "${model}/config.json" | sha256sum -c -
printf '%s  %s\n' a5119c7fdb6c8703eae8b91df4a4ef9fa0e634ea755a15a6138537c1f92e649c "${validation_root}/summary.json" | sha256sum -c -
printf '%s  %s\n' 4d0b3dfe88c7b3996bd016ded52b3061bb890080182ca8fb13f279d38c761991 "${validation_root}/qwen38-flash-next-fp8-hashes.jsonl" | sha256sum -c -
printf '%s  %s\n' c9a824f7f037d503ca63d08656e5959b0feaa0a66bb8a40441861b5be88cd75f "${moe_receipt}" | sha256sum -c -
[[ "$(find "${stage}/vllm_xpu_kernels" -type f \( -name '*.py' -o -name '*.so' \) | wc -l)" == 18 ]] || fail "staged loadable file set changed"
(cd "${stage}/vllm_xpu_kernels" && sha256sum -c "${runtime_manifest}")

exec 7>/tmp/b70-benchmark.lock
flock -n 7 || fail "host-wide benchmark lock is held"
for gpu in 0 1 2 3; do
  eval "exec $((8 + gpu))>/tmp/b70-gpu${gpu}.lock"
  flock -n "$((8 + gpu))" || fail "GPU ${gpu} lock is held"
done
pgrep -af '(^|/)(vllm|python)( |.* )serve ' >/dev/null && fail "another vLLM server is running"
ss -ltn 2>/dev/null | grep -q ":${port} " && fail "port ${port} is already open"

mem_available_kib=$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)
(( mem_available_kib >= 100 * 1024 * 1024 )) || fail "less than 100 GiB host memory is available"
(( $(df --output=avail -B1 /dev/shm | tail -1) >= 32 * 1024 * 1024 * 1024 )) || fail "less than 32 GiB shared memory is available"
(( $(df --output=avail -B1 /mnt/usb-models | tail -1) >= 300 * 1024 * 1024 * 1024 )) || fail "less than 300 GiB external space is available"
[[ "$(findmnt -no FSTYPE --target /tmp)" =~ ^(ext4|tmpfs)$ ]] || fail "/tmp must be ext4 or tmpfs for vLLM IPC"

mkdir -p "${run_dir}" "${cache_dir}/vllm" "${cache_dir}/xdg" \
  "${compile_cache_dir}/torchinductor" "${compile_cache_dir}/triton" "${rpc_dir}"
chmod 700 "${rpc_dir}"

server_pid=""
cleanup() {
  set +e
  if [[ -n "${server_pid}" ]] && kill -0 "${server_pid}" 2>/dev/null; then
    kill -TERM -- "-${server_pid}" 2>/dev/null || true
    for _ in $(seq 1 20); do
      kill -0 "${server_pid}" 2>/dev/null || break
      sleep 1
    done
    kill -KILL -- "-${server_pid}" 2>/dev/null || true
    wait "${server_pid}" 2>/dev/null || true
  fi
  find "${rpc_dir}" -mindepth 1 -delete 2>/dev/null || true
  rmdir "${rpc_dir}" 2>/dev/null || true
  find "${compile_cache_dir}" -mindepth 1 -delete 2>/dev/null || true
  rmdir "${compile_cache_dir}" 2>/dev/null || true
}
trap cleanup EXIT

for inherited in $(compgen -A variable); do
  case "${inherited}" in
    VLLM_*|CCL_*|FI_*|ZE_*|SYCL_*|ONEAPI_DEVICE_SELECTOR|TRITON_*|TORCHINDUCTOR_*|PYTORCH_*|PYTHONPATH|PYTHONHOME|LD_PRELOAD)
      unset "${inherited}"
      ;;
  esac
done

export CMPLR_ROOT=/opt/intel/oneapi/compiler/2025.3
export PATH="${CMPLR_ROOT}/bin:${PATH}"
export LIBRARY_PATH="${CMPLR_ROOT}/lib:${CMPLR_ROOT}/opt/compiler/lib"
export OCL_ICD_FILENAMES="${CMPLR_ROOT}/lib/libintelocl.so"
export PYTHONPATH="${stage}:${vllm_src}"
export LD_LIBRARY_PATH="${stage}/vllm_xpu_kernels:/home/steve/.venvs/vllm-xpu/lib:/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/lib:${CMPLR_ROOT}/lib:${CMPLR_ROOT}/opt/compiler/lib"
export HF_HOME="${cache_dir}/hf"
export HUGGINGFACE_HUB_CACHE="${cache_dir}/hf"
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export VLLM_CACHE_ROOT="${cache_dir}/vllm"
export TORCHINDUCTOR_CACHE_DIR="${compile_cache_dir}/torchinductor"
export TRITON_CACHE_DIR="${compile_cache_dir}/triton"
export XDG_CACHE_HOME="${cache_dir}/xdg"
export TMPDIR="${rpc_dir}"
export VLLM_RPC_BASE_PATH="${rpc_dir}"
export PYTHONNOUSERSITE=1
export PYTHONSAFEPATH=1
export PYTHONDONTWRITEBYTECODE=1

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
export VLLM_XPU_MOE_SYNC_TRACE="${moe_sync_trace}"

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
export Q38_MODEL_PATH="${model}"
export Q38_RUN_DIR="${run_dir}"
export Q38_VALIDATION_ROOT="${validation_root}"
export Q38_MOE_RECEIPT="${moe_receipt}"

"${python}" - <<'PY'
import os
import pathlib
import socket

root = pathlib.Path(os.environ["VLLM_RPC_BASE_PATH"])
probe = root / "socket-probe"
sock = socket.socket(socket.AF_UNIX)
sock.bind(str(probe))
sock.close()
probe.unlink()
PY

timeout 30s xpu-smi discovery -j >"${run_dir}/xpu-discovery.json" || fail "bounded XPU discovery failed"
for device in 0 1 2 3; do
  timeout 30s xpu-smi stats -d "${device}" -j >"${run_dir}/xpu-stats-${device}.json" || fail "bounded XPU stats failed for device ${device}"
done

"${python}" - <<'PY' >"${run_dir}/staged-runtime-preflight.txt"
import importlib
import json
import os
import pathlib
import torch
import vllm_xpu_kernels
import vllm.envs as envs
from vllm.engine.arg_utils import EngineArgs

root = pathlib.Path(os.environ['Q38_KERNEL_STAGE']).resolve()
validation = json.loads((pathlib.Path(os.environ['Q38_VALIDATION_ROOT']) / 'summary.json').read_text())
target = validation['plan']['targets'][0]
assert validation['status'] == 'pass'
assert target['revision'] == 'bcd9f01ddc9cff2316eb84281bebcd5b058bddce'
assert target['tree_sha256'] == '4a3793bd4a795ea6761b3d322200b4a1fd8300cdeb75cc127d330d513f590eb2'
assert target['total_bytes'] == 185563783127
moe_receipt = json.loads(pathlib.Path(os.environ['Q38_MOE_RECEIPT']).read_text())
assert moe_receipt['status'] == 'pass'
assert moe_receipt['backend']['experts_class'].endswith('.TritonExperts')
assert moe_receipt['result']['mismatches'] == 0
modules = [
    vllm_xpu_kernels,
    importlib.import_module('vllm_xpu_kernels._C'),
    importlib.import_module('vllm_xpu_kernels._moe_C'),
]
for module in modules:
    path = pathlib.Path(module.__file__).resolve()
    assert path.is_relative_to(root), (path, root)
    print(f'{module.__name__}={path}')
for namespace, op in [
    ('_C', 'per_token_group_fp8_quant'),
    ('_C', 'xpu_host_register'),
    ('_moe_C', 'topk_softmax'),
]:
    print(torch._C._dispatch_find_schema_or_throw(f'{namespace}::{op}', '').schema())
print(f'xpu_device_count={torch.xpu.device_count()}')
assert torch.xpu.device_count() == 4
assert envs.VLLM_XPU_MOE_SYNC_TRACE == bool(int(os.environ['VLLM_XPU_MOE_SYNC_TRACE']))

discovery_path = pathlib.Path(os.environ['Q38_RUN_DIR']) / 'xpu-discovery.json'
devices = json.loads(discovery_path.read_text())['device_list']
expected = [
    (0, 'Intel(R) Arc(TM) Pro B70 Graphics', '0000:23:00.0', '/dev/dri/card3'),
    (1, 'Intel(R) Arc(TM) Pro B70 Graphics', '0000:27:00.0', '/dev/dri/card4'),
    (2, 'Intel(R) Arc(TM) Pro B70 Graphics', '0000:43:00.0', '/dev/dri/card0'),
    (3, 'Intel(R) Arc(TM) Pro B70 Graphics', '0000:47:00.0', '/dev/dri/card2'),
]
actual = [(d['device_id'], d['device_name'], d['pci_bdf_address'], d['drm_device']) for d in devices]
assert actual == expected, actual
for device in range(4):
    stats = json.loads((pathlib.Path(os.environ['Q38_RUN_DIR']) / f'xpu-stats-{device}.json').read_text())
    memory = next(m['value'] for m in stats['device_level'] if m['metrics_type'] == 'XPUM_STATS_MEMORY_USED')
    assert memory < 256, (device, memory)

model = os.environ['Q38_MODEL_PATH']
args = EngineArgs(
    model=model, tokenizer=model, dtype='bfloat16', tensor_parallel_size=4,
    pipeline_parallel_size=1, data_parallel_size=1,
    distributed_executor_backend='mp', enable_expert_parallel=True,
    all2all_backend='allgather_reducescatter', language_model_only=True,
    moe_backend='triton', enforce_eager=True, max_model_len=512,
    max_num_seqs=1, max_num_batched_tokens=64,
    enable_prefix_caching=False, offload_backend='uva', cpu_offload_gb=12,
    cpu_offload_params={'ple_embedding.ngram_embedding.weight'},
    gpu_memory_utilization=.92, kv_cache_dtype='auto', block_size=64,
    generation_config='vllm', load_format='safetensors', async_scheduling=False,
)
config = args.create_engine_config(usage_context=None)
assert config.parallel_config.tensor_parallel_size == 4
assert config.parallel_config.enable_expert_parallel
assert config.parallel_config.all2all_backend == 'allgather_reducescatter'
assert config.offload_config.offload_backend == 'uva'
assert config.offload_config.uva.cpu_offload_gb == 12
assert config.offload_config.uva.cpu_offload_params == {'ple_embedding.ngram_embedding.weight'}
assert config.kernel_config.moe_backend == 'triton'
assert config.speculative_config is None
assert config.scheduler_config.max_num_batched_tokens == 64
selector = 'ple_embedding.ngram_embedding.weight'
assert f'.{selector}.' in '.model.layers.1.ple.ple_embedding.ngram_embedding.weight.'
assert f'.{selector}.' not in '.model.layers.1.ple.ple_embedding.ngram_embedding.weight_scale.'
ple_bytes_per_rank = 12_800_061_440
assert ple_bytes_per_rank < 12 * 1024**3
assert (12 * 1024**3) - ple_bytes_per_rank < 128 * 1024**2
print('engine_config=tp4_ep4_triton_eager_mtp0_selective_ple_uva')
print(f'ple_bytes_per_rank={ple_bytes_per_rank}')
PY

if ! timeout 180s "${python}" -m torch.distributed.run \
  --standalone --nproc_per_node=4 "${repo_root}/tools/xccl_probe.py" allreduce \
  >"${run_dir}/xccl-tp4-preflight.log" 2>&1; then
  tail -n 120 "${run_dir}/xccl-tp4-preflight.log" >&2 || true
  fail "exact four-rank XCCL preflight failed"
fi
for rank in 0 1 2 3; do
  grep -Fq "rank ${rank} allreduce ok 4.0" "${run_dir}/xccl-tp4-preflight.log" || fail "XCCL rank ${rank} receipt is incomplete"
done

"${python}" - <<'PY' >"${run_dir}/runtime-versions.txt"
import importlib.metadata
import pathlib
import sys
import torch
import triton

print(f'python={sys.executable}')
print(f'torch={torch.__version__}')
print(f'triton={triton.__version__}')
print(f'vllm={importlib.metadata.version("vllm")}')
print(f'vllm_xpu_kernels={importlib.metadata.version("vllm-xpu-kernels")}')
print(f'torch_file={pathlib.Path(torch.__file__).resolve()}')
PY

{
  printf 'campaign=%s\n' "${campaign}"
  printf 'model=%s\n' "${model}"
  printf 'vllm_head=%s\n' "${expected_vllm_head}"
  printf 'kernels_head=%s\n' "${expected_kernels_head}"
  printf 'stage=%s\n' "${stage}"
  printf 'compile_cache=%s\n' "${compile_cache_dir}"
  printf 'offload_backend=uva\n'
  printf 'cpu_offload_gb=12\n'
  printf 'cpu_offload_params=ple_embedding.ngram_embedding.weight\n'
  printf 'ple_cpu_process=absent\n'
  printf 'tp=4 ep=4 all2all=allgather_reducescatter\n'
  printf 'moe_backend=triton eager=1 mtp=0 max_model_len=512 max_num_batched_tokens=64\n'
  printf 'xpu_moe_sync_trace=%s diagnostic_timing=%s\n' "${moe_sync_trace}" "${moe_sync_trace}"
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
  --max-num-batched-tokens 64
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
setsid "${vllm_bin}" serve "${args[@]}" >"${server_log}" 2>&1 &
server_pid=$!
printf '%s\n' "${server_pid}" >"${run_dir}/server.pid"

healthy=0
for _ in $(seq 1 720); do
  if curl -fsS "http://127.0.0.1:${port}/health" >"${run_dir}/health.json" 2>/dev/null; then
    healthy=1
    break
  fi
  if grep -Eq 'EngineCore failed to start|Engine core initialization failed' "${server_log}"; then
    break
  fi
  kill -0 "${server_pid}" 2>/dev/null || break
  sleep 5
done
if (( healthy == 0 )); then
  tail -n 160 "${server_log}" >&2 || true
  fail "server did not become healthy within the bounded startup window"
fi
printf 'HEALTHY: %s pid=%s\n' "${campaign}" "${server_pid}"
set +e
wait "${server_pid}"
server_rc=$?
set -e
server_pid=""
exit "${server_rc}"
