#!/usr/bin/env bash
set -euo pipefail

root="/home/steve/llm-optimizations"
revision="7c360e1cd4a5168099dbc54d16d929bf6df04990"
vllm_tree="${VLLM_TREE:-/home/steve/src/deepseek-v4-vllm-clean}"
kernel_tree="${KERNEL_TREE:-/home/steve/src/deepseek-v4-xpu-kernels-clean}"
vllm_commit="382bbd51448b2f58c73b3e51d051bc352166ba91"
kernel_commit="840482d03ee12f6398967757efee9a493225644d"
model="${MODEL_PATH:-/mnt/fast-ai/llm-models/deepseek-v4-flash-xpu/current-k160}"
python="${DEEPSEEK_PYTHON:-/home/steve/.venvs/deepseek-v4-xpu/bin/python}"
vllm="${VLLM_CLI:-/home/steve/.venvs/deepseek-v4-xpu/bin/vllm}"
verify="${root}/experiments/deepseek-v4-flash-reap-xpu-b70/scripts/verify-k160-artifact.sh"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
run_dir="${RUN_DIR:-/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/tp4-smoke-${stamp}}"
port="${PORT:-18080}"

test -x "${python}"
test -x "${vllm}"
test -d "${model}"
test "$(git -C "${vllm_tree}" rev-parse HEAD)" = "${vllm_commit}"
test "$(git -C "${kernel_tree}" rev-parse HEAD)" = "${kernel_commit}"
test -z "$(git -C "${vllm_tree}" status --porcelain)"
test -z "$(git -C "${kernel_tree}" status --porcelain)"
# Promotion already performs two full SHA-256 passes (archive and hot copy).
# Repeated smoke launches keep structural and byte-count verification but skip
# rereading 96 GiB unless VERIFY_MANIFEST=1 is requested.
DEEPSEEK_HF_VERIFY=0 DEEPSEEK_CHECK_MANIFEST="${VERIFY_MANIFEST:-0}" \
  "${verify}" "${model}"
mkdir -p "${run_dir}"

set +u
source /opt/intel/oneapi/setvars.sh --force >/dev/null 2>&1
source /opt/intel/oneapi/compiler/2025.3/env/vars.sh --force >/dev/null 2>&1
source /opt/intel/oneapi/mkl/2025.3/env/vars.sh --force >/dev/null 2>&1
source /opt/intel/oneapi/dnnl/2025.3/env/vars.sh --force >/dev/null 2>&1
set -u

oneccl="${ONECCL_INSTALL_DIR:-/mnt/usb-models/llm-runtime/oneccl-4ceafd1-b70}"
export LD_LIBRARY_PATH="${oneccl}/lib:${LD_LIBRARY_PATH:-}"
export CCL_ROOT="${oneccl}"
export CCL_ATL_TRANSPORT="${CCL_ATL_TRANSPORT:-ofi}"
export CCL_TOPO_P2P_ACCESS="${CCL_TOPO_P2P_ACCESS:-1}"
export FI_TCP_IFACE="${FI_TCP_IFACE:-eno1}"
export CCL_KVS_IFACE="${CCL_KVS_IFACE:-eno1}"
unset CCL_ZE_IPC_EXCHANGE
unset CCL_WORKER_COUNT

export ONEAPI_DEVICE_SELECTOR="${ONEAPI_DEVICE_SELECTOR:-level_zero:*}"
export ZE_AFFINITY_MASK="${ZE_AFFINITY_MASK:-0,1,2,3}"
export VLLM_TARGET_DEVICE=xpu
export XPU_GRAPH="${XPU_GRAPH:-0}"
export VLLM_XPU_ENABLE_XPU_GRAPH="${VLLM_XPU_ENABLE_XPU_GRAPH:-0}"
export VLLM_XPU_FORCE_GRAPH_WITH_COMM=0
export VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE=0
# Pin the native BF16-activation MXFP4 path.  Do not allow an inherited
# diagnostic environment to silently select the reference MoE kernel or the
# alternate MXFP4-FP8 activation recipe.
export VLLM_XPU_FUSED_MOE_USE_REF=0
export VLLM_XPU_FUSED_MOE_USE_MXFP4_FP8=0
export HF_HOME="${HF_HOME:-/mnt/usb-models/llm-cache/hf}"
export VLLM_CACHE_ROOT="${VLLM_CACHE_ROOT:-/mnt/fast-ai/vllm-cache-exp/deepseek-v4-k160-${revision}/vllm}"
export TORCHINDUCTOR_CACHE_DIR="${TORCHINDUCTOR_CACHE_DIR:-/mnt/fast-ai/vllm-cache-exp/deepseek-v4-k160-${revision}/torchinductor}"
mkdir -p "${VLLM_CACHE_ROOT}" "${TORCHINDUCTOR_CACHE_DIR}"

if [[ "${RUN_PREFLIGHT:-1}" == "1" ]]; then
  PYTHON="${python}" PHYSICAL_DEVICES=0,1,2,3 XCCL_DEVICES=0,1,2,3 \
    XCCL_NPROC=4 FI_TCP_IFACE="${FI_TCP_IFACE}" CCL_KVS_IFACE="${CCL_KVS_IFACE}" \
    "${root}/scripts/check-qwen36-xpu-xccl-health.sh" \
    | tee "${run_dir}/preflight.log"
fi

extra_args=(--enforce-eager)
if [[ "${ENFORCE_EAGER:-1}" == "0" ]]; then
  extra_args=()
fi
user_extra_args=()
if [[ -n "${VLLM_EXTRA_ARGS:-}" ]]; then
  read -r -a user_extra_args <<<"${VLLM_EXTRA_ARGS}"
fi

argv=(
  "${vllm}" serve "${model}"
  --host "${HOST:-127.0.0.1}"
  --port "${port}"
  --served-model-name deepseek-v4-flash-k160
  --dtype auto
  --tensor-parallel-size 4
  --pipeline-parallel-size 1
  --distributed-executor-backend mp
  --enable-expert-parallel
  --all2all-backend allgather_reducescatter
  --max-model-len "${MAX_MODEL_LEN:-2048}"
  --max-num-batched-tokens "${MAX_NUM_BATCHED_TOKENS:-2048}"
  --max-num-seqs 1
  --gpu-memory-utilization "${GPU_MEMORY_UTILIZATION:-0.95}"
  --kv-cache-dtype fp8
  --block-size 256
  --tokenizer-mode deepseek_v4
  --reasoning-parser deepseek_v4
  --tool-call-parser deepseek_v4
  --enable-auto-tool-choice
  --no-enable-prefix-caching
  --generation-config vllm
  "${extra_args[@]}"
  "${user_extra_args[@]}"
)

{
  printf 'model=%s\n' "$(readlink -f "${model}")"
  printf 'model_revision=%s\n' "${revision}"
  printf 'artifact_manifest_sha256=%s\n' "$(sha256sum "${model}/sha256sums.txt" | awk '{print $1}')"
  printf 'verify_manifest=%s\n' "${VERIFY_MANIFEST:-0}"
  printf 'vllm_tree=%s\n' "${vllm_tree}"
  printf 'vllm_commit=%s\n' "${vllm_commit}"
  printf 'kernel_tree=%s\n' "${kernel_tree}"
  printf 'kernel_commit=%s\n' "${kernel_commit}"
  printf 'oneapi_device_selector=%s\n' "${ONEAPI_DEVICE_SELECTOR}"
  printf 'ze_affinity_mask=%s\n' "${ZE_AFFINITY_MASK}"
  printf 'xpu_graph=%s\n' "${XPU_GRAPH}"
  printf 'vllm_xpu_enable_xpu_graph=%s\n' "${VLLM_XPU_ENABLE_XPU_GRAPH}"
  printf 'vllm_xpu_force_graph_with_comm=%s\n' "${VLLM_XPU_FORCE_GRAPH_WITH_COMM}"
  printf 'vllm_xpu_graph_noop_comm_capture=%s\n' "${VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE}"
  printf 'vllm_xpu_fused_moe_use_ref=%s\n' "${VLLM_XPU_FUSED_MOE_USE_REF}"
  printf 'vllm_xpu_fused_moe_use_mxfp4_fp8=%s\n' "${VLLM_XPU_FUSED_MOE_USE_MXFP4_FP8}"
  printf 'enforce_eager=%s\n' "${ENFORCE_EAGER:-1}"
  printf 'expert_parallel=1\n'
  printf 'gpu_memory_utilization=%s\n' "${GPU_MEMORY_UTILIZATION:-0.95}"
  printf 'max_model_len=%s\n' "${MAX_MODEL_LEN:-2048}"
  printf 'max_num_batched_tokens=%s\n' "${MAX_NUM_BATCHED_TOKENS:-2048}"
  printf 'kv_cache_dtype=fp8\nblock_size=256\nprefix_caching=0\n'
  printf 'oneccl=%s\n' "${oneccl}"
  printf 'ccl_atl_transport=%s\n' "${CCL_ATL_TRANSPORT}"
  printf 'ccl_topo_p2p_access=%s\n' "${CCL_TOPO_P2P_ACCESS}"
  printf 'fi_tcp_iface=%s\n' "${FI_TCP_IFACE}"
  printf 'ccl_kvs_iface=%s\n' "${CCL_KVS_IFACE}"
  printf 'vllm_cache_root=%s\n' "${VLLM_CACHE_ROOT}"
  printf 'torchinductor_cache_dir=%s\n' "${TORCHINDUCTOR_CACHE_DIR}"
  printf 'vllm_extra_args=%s\n' "${VLLM_EXTRA_ARGS:-}"
  printf 'argv='
  printf '%q ' "${argv[@]}"
  printf '\n'
  "${python}" - <<'PY'
import importlib.metadata as metadata
for package in ("torch", "triton-xpu", "vllm", "vllm-xpu-kernels"):
    print(f"package_{package}={metadata.version(package)}")
PY
} >"${run_dir}/identity.txt"

exec "${argv[@]}" \
  >"${run_dir}/server.log" 2>&1
