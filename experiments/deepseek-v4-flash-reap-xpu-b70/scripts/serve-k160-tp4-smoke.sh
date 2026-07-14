#!/usr/bin/env bash
set -euo pipefail

root="/home/steve/llm-optimizations"
revision="7c360e1cd4a5168099dbc54d16d929bf6df04990"
vllm_tree="${VLLM_TREE:-/home/steve/src/deepseek-v4-vllm-clean}"
kernel_tree="${KERNEL_TREE:-/home/steve/src/deepseek-v4-xpu-kernels-clean}"
vllm_commit="${VLLM_COMMIT:-61c87db645c256651b5a366f538898485077ad32}"
kernel_commit="${KERNEL_COMMIT:-d553fd2ac0cfc86edbb4fe9c65d567318931fe91}"
model="${MODEL_PATH:-/mnt/fast-ai/llm-models/deepseek-v4-flash-xpu/current-k160}"
python="${DEEPSEEK_PYTHON:-/home/steve/.venvs/deepseek-v4-xpu/bin/python}"
vllm="${VLLM_CLI:-/home/steve/.venvs/deepseek-v4-xpu/bin/vllm}"
verify="${root}/experiments/deepseek-v4-flash-reap-xpu-b70/scripts/verify-k160-artifact.sh"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
run_dir="${RUN_DIR:-/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/tp4-smoke-${stamp}}"
port="${PORT:-18080}"
tp_size="${TP_SIZE:-4}"
pp_size="${PP_SIZE:-1}"
dp_size="${DP_SIZE:-1}"
dp_size_local="${DP_SIZE_LOCAL:-${dp_size}}"

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
source /opt/intel/oneapi/compiler/2025.3/env/vars.sh --force >/dev/null 2>&1
source /opt/intel/oneapi/mkl/2025.3/env/vars.sh --force >/dev/null 2>&1
source /opt/intel/oneapi/dnnl/2025.3/env/vars.sh --force >/dev/null 2>&1
set -u

oneccl="${ONECCL_INSTALL_DIR:-/mnt/usb-models/llm-runtime/oneccl-4ceafd1-b70}"
oneccl_source_tree="${ONECCL_SOURCE_TREE:-/home/steve/src/oneccl-4ceafd1}"
venv_lib="$(dirname "$(dirname "${python}")")/lib"
# Torch 2.11 XPU and the installed kernel package are a SYCL 8 lane.  Keep
# their matching Unified Runtime loader ahead of any side-by-side oneAPI 2026
# installation when Triton JIT-compiles a new launcher.
export LD_LIBRARY_PATH="${venv_lib}:${oneccl}/lib:${LD_LIBRARY_PATH:-}"
export CCL_ROOT="${oneccl}"
export CCL_ATL_TRANSPORT="${CCL_ATL_TRANSPORT:-ofi}"
export CCL_TOPO_P2P_ACCESS="${CCL_TOPO_P2P_ACCESS:-1}"
export CCL_SYCL_ALLREDUCE_LL="${CCL_SYCL_ALLREDUCE_LL:-ring}"
export CCL_SYCL_ALLREDUCE_LL_THRESHOLD="${CCL_SYCL_ALLREDUCE_LL_THRESHOLD:-4096}"
export CCL_SYCL_ALLREDUCE_ARC="${CCL_SYCL_ALLREDUCE_ARC:-0}"
export CCL_KERNEL_PATH="${CCL_KERNEL_PATH:-${oneccl}/lib/ccl/kernels}"
export FI_TCP_IFACE="${FI_TCP_IFACE:-eno1}"
export CCL_KVS_IFACE="${CCL_KVS_IFACE:-eno1}"
unset CCL_ZE_IPC_EXCHANGE
unset CCL_WORKER_COUNT

export ONEAPI_DEVICE_SELECTOR="${ONEAPI_DEVICE_SELECTOR:-level_zero:*}"
export ZE_AFFINITY_MASK="${ZE_AFFINITY_MASK:-0,1,2,3}"
export VLLM_TARGET_DEVICE=xpu
export XPU_GRAPH="${XPU_GRAPH:-0}"
export VLLM_XPU_ENABLE_XPU_GRAPH="${VLLM_XPU_ENABLE_XPU_GRAPH:-0}"
export VLLM_XPU_FORCE_GRAPH_WITH_COMM="${VLLM_XPU_FORCE_GRAPH_WITH_COMM:-0}"
export VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE="${VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE:-0}"
# Pin the native BF16-activation MXFP4 path.  Do not allow an inherited
# diagnostic environment to silently select the reference MoE kernel or the
# alternate MXFP4-FP8 activation recipe.
export VLLM_XPU_FUSED_MOE_USE_REF=0
export VLLM_XPU_FUSED_MOE_USE_MXFP4_FP8=0
export VLLM_XPU_V4_DIRECT_FP8_ATTN="${VLLM_XPU_V4_DIRECT_FP8_ATTN:-0}"
export VLLM_XPU_V4_SPLIT_FP8_ATTN="${VLLM_XPU_V4_SPLIT_FP8_ATTN:-0}"
export VLLM_XPU_V4_FP8_WO_A="${VLLM_XPU_V4_FP8_WO_A:-0}"
export VLLM_XPU_V4_INPLACE_ALLREDUCE="${VLLM_XPU_V4_INPLACE_ALLREDUCE:-0}"
export VLLM_XPU_V4_MHC_NORM_FUSION="${VLLM_XPU_V4_MHC_NORM_FUSION:-0}"
export VLLM_XPU_V4_TP4_RING_MHC_POST="${VLLM_XPU_V4_TP4_RING_MHC_POST:-0}"
if [[ "${VLLM_XPU_V4_TP4_RING_MHC_POST}" == "1" ]]; then
  export LD_PRELOAD="${oneccl}/lib/libccl.so.1.0${LD_PRELOAD:+:${LD_PRELOAD}}"
fi
export VLLM_XPU_LOG_FP8_LINEAR_SHAPES="${VLLM_XPU_LOG_FP8_LINEAR_SHAPES:-0}"
export VLLM_XPU_V4_BLOCK_FP8_W8A16="${VLLM_XPU_V4_BLOCK_FP8_W8A16:-0}"
export VLLM_XPU_MXFP4_SMALL_M_N="${VLLM_XPU_MXFP4_SMALL_M_N:-64}"
export VLLM_XPU_V4_DIRECT_FP8_BLOCK_H="${VLLM_XPU_V4_DIRECT_FP8_BLOCK_H:-16}"
export VLLM_XPU_V4_DIRECT_FP8_NUM_WARPS="${VLLM_XPU_V4_DIRECT_FP8_NUM_WARPS:-8}"
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
  --tensor-parallel-size "${tp_size}"
  --data-parallel-size "${dp_size}"
  --data-parallel-size-local "${dp_size_local}"
  --pipeline-parallel-size "${pp_size}"
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
  printf 'vllm_xpu_v4_direct_fp8_attn=%s\n' "${VLLM_XPU_V4_DIRECT_FP8_ATTN}"
  printf 'vllm_xpu_v4_split_fp8_attn=%s\n' "${VLLM_XPU_V4_SPLIT_FP8_ATTN}"
  printf 'vllm_xpu_v4_fp8_wo_a=%s\n' "${VLLM_XPU_V4_FP8_WO_A}"
  printf 'vllm_xpu_v4_inplace_allreduce=%s\n' "${VLLM_XPU_V4_INPLACE_ALLREDUCE}"
  printf 'vllm_xpu_v4_mhc_norm_fusion=%s\n' "${VLLM_XPU_V4_MHC_NORM_FUSION}"
  printf 'vllm_xpu_v4_tp4_ring_mhc_post=%s\n' "${VLLM_XPU_V4_TP4_RING_MHC_POST}"
  printf 'ld_preload=%s\n' "${LD_PRELOAD:-}"
  printf 'vllm_xpu_log_fp8_linear_shapes=%s\n' "${VLLM_XPU_LOG_FP8_LINEAR_SHAPES}"
  printf 'vllm_xpu_v4_block_fp8_w8a16=%s\n' "${VLLM_XPU_V4_BLOCK_FP8_W8A16}"
  printf 'vllm_xpu_mxfp4_small_m_n=%s\n' "${VLLM_XPU_MXFP4_SMALL_M_N}"
  printf 'vllm_xpu_v4_direct_fp8_block_h=%s\n' "${VLLM_XPU_V4_DIRECT_FP8_BLOCK_H}"
  printf 'vllm_xpu_v4_direct_fp8_num_warps=%s\n' "${VLLM_XPU_V4_DIRECT_FP8_NUM_WARPS}"
  printf 'vllm_xpu_native_mhc=%s\n' "${VLLM_XPU_NATIVE_MHC:-0}"
  printf 'enforce_eager=%s\n' "${ENFORCE_EAGER:-1}"
  printf 'expert_parallel=1\n'
  printf 'tensor_parallel_size=%s\n' "${tp_size}"
  printf 'pipeline_parallel_size=%s\n' "${pp_size}"
  printf 'data_parallel_size=%s\n' "${dp_size}"
  printf 'data_parallel_size_local=%s\n' "${dp_size_local}"
  printf 'gpu_memory_utilization=%s\n' "${GPU_MEMORY_UTILIZATION:-0.95}"
  printf 'max_model_len=%s\n' "${MAX_MODEL_LEN:-2048}"
  printf 'max_num_batched_tokens=%s\n' "${MAX_NUM_BATCHED_TOKENS:-2048}"
  printf 'kv_cache_dtype=fp8\nblock_size=256\nprefix_caching=0\n'
  printf 'oneccl=%s\n' "${oneccl}"
  printf 'oneccl_source_tree=%s\n' "${oneccl_source_tree}"
  if [[ -d "${oneccl_source_tree}/.git" || -f "${oneccl_source_tree}/.git" ]]; then
    printf 'oneccl_commit=%s\n' "$(git -C "${oneccl_source_tree}" rev-parse HEAD)"
  fi
  printf 'ccl_atl_transport=%s\n' "${CCL_ATL_TRANSPORT}"
  printf 'ccl_topo_p2p_access=%s\n' "${CCL_TOPO_P2P_ACCESS}"
  printf 'ccl_sycl_allreduce_ll=%s\n' "${CCL_SYCL_ALLREDUCE_LL}"
  printf 'ccl_sycl_allreduce_ll_threshold=%s\n' "${CCL_SYCL_ALLREDUCE_LL_THRESHOLD}"
  printf 'ccl_sycl_allreduce_arc=%s\n' "${CCL_SYCL_ALLREDUCE_ARC}"
  printf 'ccl_kernel_path=%s\n' "${CCL_KERNEL_PATH}"
  printf 'ccl_topo_fabric_vertex_connection_check=%s\n' "${CCL_TOPO_FABRIC_VERTEX_CONNECTION_CHECK:-default}"
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
