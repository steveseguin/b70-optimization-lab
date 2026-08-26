#!/usr/bin/env bash
set -euo pipefail

root="/home/steve/llm-optimizations"
revision="${MODEL_REVISION:-7c360e1cd4a5168099dbc54d16d929bf6df04990}"
vllm_tree="${VLLM_TREE:-/home/steve/src/deepseek-v4-vllm-clean}"
kernel_tree="${KERNEL_TREE:-/home/steve/src/deepseek-v4-xpu-kernels-clean}"
vllm_commit="${VLLM_COMMIT:-61c87db645c256651b5a366f538898485077ad32}"
kernel_commit="${KERNEL_COMMIT:-d553fd2ac0cfc86edbb4fe9c65d567318931fe91}"
model="${MODEL_PATH:-/mnt/fast-ai/llm-models/deepseek-v4-flash-xpu/current-k160}"
python="${DEEPSEEK_PYTHON:-/home/steve/.venvs/deepseek-v4-xpu/bin/python}"
vllm="${VLLM_CLI:-/home/steve/.venvs/deepseek-v4-xpu/bin/vllm}"
verify="${MODEL_VERIFY_SCRIPT:-${root}/experiments/deepseek-v4-flash-reap-xpu-b70/scripts/verify-k160-artifact.sh}"
manifest_file="${MODEL_MANIFEST_FILE:-sha256sums.txt}"
served_model_name="${SERVED_MODEL_NAME:-deepseek-v4-flash-k160}"
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
test -f "${model}/${manifest_file}"
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

venv_root="$(dirname "$(dirname "${python}")")"
oneccl="${ONECCL_INSTALL_DIR:-${venv_root}}"
oneccl_source_tree="${ONECCL_SOURCE_TREE:-/home/steve/src/oneccl-4ceafd1}"
venv_lib="${venv_root}/lib"
oneccl_lib="${ONECCL_LIB_DIR:-${oneccl}/lib}"
# Torch 2.11 XPU and the installed kernel package are a SYCL 8 lane.  Keep
# their matching Unified Runtime loader ahead of any side-by-side oneAPI 2026
# installation when Triton JIT-compiles a new launcher. Put an explicitly
# selected oneCCL directory first so ONECCL_LIB_DIR changes the loaded runtime.
export LD_LIBRARY_PATH="${oneccl_lib}:${venv_lib}:${LD_LIBRARY_PATH:-}"
export CCL_ROOT="${oneccl}"
export CCL_ATL_TRANSPORT="${CCL_ATL_TRANSPORT:-ofi}"
export CCL_TOPO_P2P_ACCESS="${CCL_TOPO_P2P_ACCESS:-1}"
export CCL_SYCL_ALLREDUCE_LL="${CCL_SYCL_ALLREDUCE_LL:-ring}"
export CCL_SYCL_ALLREDUCE_LL_THRESHOLD="${CCL_SYCL_ALLREDUCE_LL_THRESHOLD:-4096}"
export CCL_SYCL_ALLREDUCE_ARC="${CCL_SYCL_ALLREDUCE_ARC:-0}"
export B70_ONECCL_SYCL_MAX_BYTES="${B70_ONECCL_SYCL_MAX_BYTES:-}"
export B70_ONECCL_SYCL_ALLREDUCE_MAX_BYTES="${B70_ONECCL_SYCL_ALLREDUCE_MAX_BYTES:-}"
export B70_ONECCL_SYCL_ALLGATHER_MAX_BYTES="${B70_ONECCL_SYCL_ALLGATHER_MAX_BYTES:-}"
export B70_ONECCL_SYCL_REDUCE_SCATTER_MAX_BYTES="${B70_ONECCL_SYCL_REDUCE_SCATTER_MAX_BYTES:-}"
export ONECCL_FORCE_PRELOAD="${ONECCL_FORCE_PRELOAD:-0}"
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
export VLLM_XPU_FUSED_MOE_USE_REF="${VLLM_XPU_FUSED_MOE_USE_REF:-0}"
export VLLM_XPU_FUSED_MOE_USE_MXFP4_FP8=0
export VLLM_XPU_V4_DIRECT_FP8_ATTN="${VLLM_XPU_V4_DIRECT_FP8_ATTN:-0}"
export VLLM_XPU_V4_SPLIT_FP8_ATTN="${VLLM_XPU_V4_SPLIT_FP8_ATTN:-0}"
export VLLM_XPU_V4_FP8_WO_A="${VLLM_XPU_V4_FP8_WO_A:-0}"
export VLLM_XPU_V4_INPLACE_ALLREDUCE="${VLLM_XPU_V4_INPLACE_ALLREDUCE:-0}"
export VLLM_XPU_V4_INPLACE_ALLREDUCE_M2="${VLLM_XPU_V4_INPLACE_ALLREDUCE_M2:-0}"
export VLLM_XPU_V4_SEGMENTED_ALLREDUCE_MAX_M="${VLLM_XPU_V4_SEGMENTED_ALLREDUCE_MAX_M:-0}"
export VLLM_XPU_DPEP_ALLREDUCE="${VLLM_XPU_DPEP_ALLREDUCE:-0}"
export VLLM_XPU_DPEP_SWITCH_SYNC="${VLLM_XPU_DPEP_SWITCH_SYNC:-0}"
export VLLM_XPU_DPEP_NATIVE="${VLLM_XPU_DPEP_NATIVE:-0}"
export VLLM_XPU_V4_MHC_NORM_FUSION="${VLLM_XPU_V4_MHC_NORM_FUSION:-0}"
export VLLM_XPU_V4_TP4_RING_MHC_POST="${VLLM_XPU_V4_TP4_RING_MHC_POST:-0}"
export VLLM_XPU_V4_TP4_RING_MHC_POST_PRE="${VLLM_XPU_V4_TP4_RING_MHC_POST_PRE:-0}"
export VLLM_XPU_V4_MHC_PRE_M1_SINGLE_KERNEL="${VLLM_XPU_V4_MHC_PRE_M1_SINGLE_KERNEL:-0}"
export VLLM_XPU_V4_MHC_POST_PRE_M1_SINGLE_KERNEL="${VLLM_XPU_V4_MHC_POST_PRE_M1_SINGLE_KERNEL:-0}"
export VLLM_XPU_V4_MHC_POST_PRE_M2_SINGLE_KERNEL="${VLLM_XPU_V4_MHC_POST_PRE_M2_SINGLE_KERNEL:-0}"
export VLLM_XPU_V4_MHC_POST_PRE_M1_RMS="${VLLM_XPU_V4_MHC_POST_PRE_M1_RMS:-0}"
default_fixed_mhc_max_m=0
if [[ "${VLLM_XPU_V4_MHC_POST_PRE_M2_SINGLE_KERNEL}" == "1" ]]; then
  default_fixed_mhc_max_m=2
fi
export VLLM_XPU_V4_MHC_POST_PRE_FIXED_WIDTH_MAX_M="${VLLM_XPU_V4_MHC_POST_PRE_FIXED_WIDTH_MAX_M:-${default_fixed_mhc_max_m}}"
export VLLM_XPU_V4_SHARED_EXPERT_FUSED_ACT_QUANT="${VLLM_XPU_V4_SHARED_EXPERT_FUSED_ACT_QUANT:-0}"
export VLLM_XPU_V4_SHARED_EXPERT_FUSED_ACT_QUANT_MAX_M="${VLLM_XPU_V4_SHARED_EXPERT_FUSED_ACT_QUANT_MAX_M:-1}"
export VLLM_XPU_V4_M2_ROUTED_CLAMP_SILU="${VLLM_XPU_V4_M2_ROUTED_CLAMP_SILU:-0}"
export VLLM_XPU_MOE_OUTPUT_ALIAS="${VLLM_XPU_MOE_OUTPUT_ALIAS:-0}"
export VLLM_XPU_V4_M1_BIASED_TOPK="${VLLM_XPU_V4_M1_BIASED_TOPK:-0}"
export VLLM_XPU_V4_M1_ROUTER_NORM="${VLLM_XPU_V4_M1_ROUTER_NORM:-0}"
export VLLM_XPU_V4_M2_ROUTER_NORM="${VLLM_XPU_V4_M2_ROUTER_NORM:-0}"
export VLLM_XPU_V4_M1_DIRECT_ROUTED_MOE="${VLLM_XPU_V4_M1_DIRECT_ROUTED_MOE:-0}"
export VLLM_XPU_V4_M2_ROUTE_DIRECT_COMPACT="${VLLM_XPU_V4_M2_ROUTE_DIRECT_COMPACT:-0}"
export VLLM_XPU_V4_NATIVE_DUAL_RMSNORM="${VLLM_XPU_V4_NATIVE_DUAL_RMSNORM:-0}"
export VLLM_XPU_V4_FUSED_QNORM_ROPE_KV_INSERT="${VLLM_XPU_V4_FUSED_QNORM_ROPE_KV_INSERT:-0}"
export VLLM_XPU_V4_FUSED_QNORM_ROPE_KV_INSERT_MAX_M="${VLLM_XPU_V4_FUSED_QNORM_ROPE_KV_INSERT_MAX_M:-1}"
export VLLM_XPU_V4_COMPRESSOR_M2_ROW_EXACT="${VLLM_XPU_V4_COMPRESSOR_M2_ROW_EXACT:-0}"
export VLLM_XPU_V4_COMPRESSOR_M2_BATCHED_EXACT="${VLLM_XPU_V4_COMPRESSOR_M2_BATCHED_EXACT:-0}"
default_compressor_batched_exact_max_m=0
if [[ "${VLLM_XPU_V4_COMPRESSOR_M2_BATCHED_EXACT}" == "1" ]]; then
  default_compressor_batched_exact_max_m=2
fi
export VLLM_XPU_V4_COMPRESSOR_BATCHED_EXACT_MAX_M="${VLLM_XPU_V4_COMPRESSOR_BATCHED_EXACT_MAX_M:-${default_compressor_batched_exact_max_m}}"
default_compressor_row_exact_max_m=0
if [[ "${VLLM_XPU_V4_COMPRESSOR_M2_ROW_EXACT}" == "1" ]]; then
  default_compressor_row_exact_max_m=2
fi
export VLLM_XPU_V4_COMPRESSOR_ROW_EXACT_MAX_M="${VLLM_XPU_V4_COMPRESSOR_ROW_EXACT_MAX_M:-${default_compressor_row_exact_max_m}}"
export VLLM_XPU_V4_CAPTURE_CYCLE_WIDTH="${VLLM_XPU_V4_CAPTURE_CYCLE_WIDTH:-2}"
export VLLM_XPU_V4_CAPTURE_CYCLE_DIR="${VLLM_XPU_V4_CAPTURE_CYCLE_DIR:-}"
export VLLM_XPU_V4_CAPTURE_CYCLE_ARM_FILE="${VLLM_XPU_V4_CAPTURE_CYCLE_ARM_FILE:-/tmp/deepseek-v4-cycle-capture.arm}"
export VLLM_XPU_V4_FORWARD_DEVICE_SYNC="${VLLM_XPU_V4_FORWARD_DEVICE_SYNC:-0}"
export VLLM_XPU_V4_DIVERGENCE_CAPTURE_DIR="${VLLM_XPU_V4_DIVERGENCE_CAPTURE_DIR:-}"
export VLLM_XPU_V4_DIVERGENCE_ARM_FILE="${VLLM_XPU_V4_DIVERGENCE_ARM_FILE:-/tmp/deepseek-v4-divergence-capture.arm}"
export VLLM_XPU_V4_DIVERGENCE_STAGES="${VLLM_XPU_V4_DIVERGENCE_STAGES:-layer_out}"
export VLLM_XPU_V4_DIVERGENCE_LAYERS="${VLLM_XPU_V4_DIVERGENCE_LAYERS:-all}"
export VLLM_XPU_V4_DIVERGENCE_MODE="${VLLM_XPU_V4_DIVERGENCE_MODE:-hash}"
export VLLM_XPU_V4_DIVERGENCE_MAX_RECORDS="${VLLM_XPU_V4_DIVERGENCE_MAX_RECORDS:-2048}"
export VLLM_XPU_EXPERT_MAP_ROUND_ROBIN="${VLLM_XPU_EXPERT_MAP_ROUND_ROBIN:-0}"
if [[ "${ONECCL_FORCE_PRELOAD}" == "1" || \
      "${VLLM_XPU_V4_TP4_RING_MHC_POST}" == "1" || \
      "${VLLM_XPU_V4_TP4_RING_MHC_POST_PRE}" == "1" ]]; then
  export LD_PRELOAD="${oneccl_lib}/libccl.so.1.0${LD_PRELOAD:+:${LD_PRELOAD}}"
fi
export VLLM_XPU_LOG_FP8_LINEAR_SHAPES="${VLLM_XPU_LOG_FP8_LINEAR_SHAPES:-0}"
export VLLM_XPU_USE_SAMPLER_KERNEL="${VLLM_XPU_USE_SAMPLER_KERNEL:-1}"
export VLLM_XPU_V4_BLOCK_FP8_W8A16="${VLLM_XPU_V4_BLOCK_FP8_W8A16:-0}"
export VLLM_XPU_V4_BLOCK_FP8_W8A16_MAX_M="${VLLM_XPU_V4_BLOCK_FP8_W8A16_MAX_M:-1}"
export VLLM_XPU_V4_BLOCK_FP8_W8A16_SHAPES="${VLLM_XPU_V4_BLOCK_FP8_W8A16_SHAPES:-}"
export VLLM_XPU_MXFP4_SMALL_M_N="${VLLM_XPU_MXFP4_SMALL_M_N:-64}"
export VLLM_XPU_V4_DIRECT_FP8_BLOCK_H="${VLLM_XPU_V4_DIRECT_FP8_BLOCK_H:-16}"
export VLLM_XPU_V4_DIRECT_FP8_NUM_WARPS="${VLLM_XPU_V4_DIRECT_FP8_NUM_WARPS:-8}"
export VLLM_XPU_V4_SPLIT_FP8_BLOCK_H="${VLLM_XPU_V4_SPLIT_FP8_BLOCK_H:-16}"
export VLLM_XPU_V4_SPLIT_FP8_QK_NUM_WARPS="${VLLM_XPU_V4_SPLIT_FP8_QK_NUM_WARPS:-8}"
export VLLM_XPU_V4_SPLIT_FP8_PV_NUM_WARPS="${VLLM_XPU_V4_SPLIT_FP8_PV_NUM_WARPS:-4}"
export VLLM_CUSTOM_SCOPES_FOR_PROFILING="${VLLM_CUSTOM_SCOPES_FOR_PROFILING:-0}"
export VLLM_MULTI_STREAM_GEMM_TOKEN_THRESHOLD="${VLLM_MULTI_STREAM_GEMM_TOKEN_THRESHOLD:-1024}"
export TRITON_CACHE_AUTOTUNING="${TRITON_CACHE_AUTOTUNING:-1}"
export VLLM_TRITON_FORCE_FIRST_CONFIG="${VLLM_TRITON_FORCE_FIRST_CONFIG:-0}"
export HF_HOME="${HF_HOME:-/mnt/fast-ai/llm-cache/hf}"
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
  --served-model-name "${served_model_name}"
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
  printf 'served_model_name=%s\n' "${served_model_name}"
  printf 'artifact_manifest_file=%s\n' "${manifest_file}"
  printf 'artifact_manifest_sha256=%s\n' "$(sha256sum "${model}/${manifest_file}" | awk '{print $1}')"
  printf 'full_validation_summary=%s\n' "${DEEPSEEK_0731_VALIDATION_SUMMARY:-unset}"
  if [[ -n "${DEEPSEEK_0731_VALIDATION_SUMMARY:-}" ]]; then
    printf 'full_validation_summary_sha256=%s\n' \
      "$(sha256sum "${DEEPSEEK_0731_VALIDATION_SUMMARY}" | awk '{print $1}')"
  fi
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
  printf 'compilation_config=%s\n' "${COMPILATION_CONFIG:-unset}"
  printf 'vllm_xpu_fused_moe_use_ref=%s\n' "${VLLM_XPU_FUSED_MOE_USE_REF}"
  printf 'vllm_xpu_fused_moe_use_mxfp4_fp8=%s\n' "${VLLM_XPU_FUSED_MOE_USE_MXFP4_FP8}"
  printf 'vllm_xpu_v4_direct_fp8_attn=%s\n' "${VLLM_XPU_V4_DIRECT_FP8_ATTN}"
  printf 'vllm_xpu_v4_split_fp8_attn=%s\n' "${VLLM_XPU_V4_SPLIT_FP8_ATTN}"
  printf 'vllm_xpu_v4_fp8_wo_a=%s\n' "${VLLM_XPU_V4_FP8_WO_A}"
  printf 'vllm_xpu_v4_inplace_allreduce=%s\n' "${VLLM_XPU_V4_INPLACE_ALLREDUCE}"
  printf 'vllm_xpu_v4_inplace_allreduce_m2=%s\n' "${VLLM_XPU_V4_INPLACE_ALLREDUCE_M2}"
  printf 'vllm_xpu_v4_segmented_allreduce_max_m=%s\n' "${VLLM_XPU_V4_SEGMENTED_ALLREDUCE_MAX_M}"
  printf 'vllm_xpu_dpep_allreduce=%s\n' "${VLLM_XPU_DPEP_ALLREDUCE}"
  printf 'vllm_xpu_dpep_switch_sync=%s\n' "${VLLM_XPU_DPEP_SWITCH_SYNC}"
  printf 'vllm_xpu_dpep_native=%s\n' "${VLLM_XPU_DPEP_NATIVE}"
  printf 'vllm_xpu_v4_mhc_norm_fusion=%s\n' "${VLLM_XPU_V4_MHC_NORM_FUSION}"
  printf 'vllm_xpu_v4_tp4_ring_mhc_post=%s\n' "${VLLM_XPU_V4_TP4_RING_MHC_POST}"
  printf 'vllm_xpu_v4_tp4_ring_mhc_post_pre=%s\n' "${VLLM_XPU_V4_TP4_RING_MHC_POST_PRE}"
  printf 'vllm_xpu_v4_mhc_pre_m1_single_kernel=%s\n' "${VLLM_XPU_V4_MHC_PRE_M1_SINGLE_KERNEL}"
  printf 'vllm_xpu_v4_mhc_post_pre_m1_single_kernel=%s\n' "${VLLM_XPU_V4_MHC_POST_PRE_M1_SINGLE_KERNEL}"
  printf 'vllm_xpu_v4_mhc_post_pre_m2_single_kernel=%s\n' "${VLLM_XPU_V4_MHC_POST_PRE_M2_SINGLE_KERNEL}"
  printf 'vllm_xpu_v4_mhc_post_pre_m1_rms=%s\n' "${VLLM_XPU_V4_MHC_POST_PRE_M1_RMS}"
  printf 'vllm_xpu_v4_mhc_post_pre_fixed_width_max_m=%s\n' "${VLLM_XPU_V4_MHC_POST_PRE_FIXED_WIDTH_MAX_M}"
  printf 'vllm_xpu_v4_shared_expert_fused_act_quant=%s\n' "${VLLM_XPU_V4_SHARED_EXPERT_FUSED_ACT_QUANT}"
  printf 'vllm_xpu_v4_shared_expert_fused_act_quant_max_m=%s\n' "${VLLM_XPU_V4_SHARED_EXPERT_FUSED_ACT_QUANT_MAX_M}"
  printf 'vllm_xpu_v4_m2_routed_clamp_silu=%s\n' "${VLLM_XPU_V4_M2_ROUTED_CLAMP_SILU}"
  printf 'vllm_xpu_moe_output_alias=%s\n' "${VLLM_XPU_MOE_OUTPUT_ALIAS}"
  printf 'vllm_xpu_v4_m1_biased_topk=%s\n' "${VLLM_XPU_V4_M1_BIASED_TOPK}"
  printf 'vllm_xpu_v4_m1_router_norm=%s\n' "${VLLM_XPU_V4_M1_ROUTER_NORM}"
  printf 'vllm_xpu_v4_m2_router_norm=%s\n' "${VLLM_XPU_V4_M2_ROUTER_NORM}"
  printf 'vllm_xpu_v4_m1_direct_routed_moe=%s\n' "${VLLM_XPU_V4_M1_DIRECT_ROUTED_MOE}"
  printf 'vllm_xpu_v4_m2_route_direct_compact=%s\n' "${VLLM_XPU_V4_M2_ROUTE_DIRECT_COMPACT}"
  printf 'vllm_xpu_v4_native_dual_rmsnorm=%s\n' "${VLLM_XPU_V4_NATIVE_DUAL_RMSNORM}"
  printf 'vllm_xpu_v4_fused_qnorm_rope_kv_insert=%s\n' "${VLLM_XPU_V4_FUSED_QNORM_ROPE_KV_INSERT}"
  printf 'vllm_xpu_v4_fused_qnorm_rope_kv_insert_max_m=%s\n' "${VLLM_XPU_V4_FUSED_QNORM_ROPE_KV_INSERT_MAX_M}"
  printf 'vllm_xpu_v4_compressor_m2_row_exact=%s\n' "${VLLM_XPU_V4_COMPRESSOR_M2_ROW_EXACT}"
  printf 'vllm_xpu_v4_compressor_m2_batched_exact=%s\n' "${VLLM_XPU_V4_COMPRESSOR_M2_BATCHED_EXACT}"
  printf 'vllm_xpu_v4_compressor_batched_exact_max_m=%s\n' "${VLLM_XPU_V4_COMPRESSOR_BATCHED_EXACT_MAX_M}"
  printf 'vllm_xpu_v4_compressor_row_exact_max_m=%s\n' "${VLLM_XPU_V4_COMPRESSOR_ROW_EXACT_MAX_M}"
  printf 'vllm_xpu_v4_capture_cycle_width=%s\n' "${VLLM_XPU_V4_CAPTURE_CYCLE_WIDTH}"
  printf 'vllm_xpu_v4_capture_cycle_dir=%s\n' "${VLLM_XPU_V4_CAPTURE_CYCLE_DIR}"
  printf 'vllm_xpu_v4_capture_cycle_arm_file=%s\n' "${VLLM_XPU_V4_CAPTURE_CYCLE_ARM_FILE}"
  printf 'vllm_xpu_v4_forward_device_sync=%s\n' "${VLLM_XPU_V4_FORWARD_DEVICE_SYNC}"
  printf 'vllm_xpu_v4_divergence_capture_dir=%s\n' "${VLLM_XPU_V4_DIVERGENCE_CAPTURE_DIR}"
  printf 'vllm_xpu_v4_divergence_arm_file=%s\n' "${VLLM_XPU_V4_DIVERGENCE_ARM_FILE}"
  printf 'vllm_xpu_v4_divergence_stages=%s\n' "${VLLM_XPU_V4_DIVERGENCE_STAGES}"
  printf 'vllm_xpu_v4_divergence_layers=%s\n' "${VLLM_XPU_V4_DIVERGENCE_LAYERS}"
  printf 'vllm_xpu_v4_divergence_mode=%s\n' "${VLLM_XPU_V4_DIVERGENCE_MODE}"
  printf 'vllm_xpu_v4_divergence_max_records=%s\n' "${VLLM_XPU_V4_DIVERGENCE_MAX_RECORDS}"
  printf 'vllm_xpu_expert_map_round_robin=%s\n' "${VLLM_XPU_EXPERT_MAP_ROUND_ROBIN}"
  printf 'ld_preload=%s\n' "${LD_PRELOAD:-}"
  printf 'vllm_xpu_log_fp8_linear_shapes=%s\n' "${VLLM_XPU_LOG_FP8_LINEAR_SHAPES}"
  printf 'vllm_xpu_use_sampler_kernel=%s\n' "${VLLM_XPU_USE_SAMPLER_KERNEL}"
  printf 'vllm_xpu_v4_block_fp8_w8a16=%s\n' "${VLLM_XPU_V4_BLOCK_FP8_W8A16}"
  printf 'vllm_xpu_v4_block_fp8_w8a16_max_m=%s\n' "${VLLM_XPU_V4_BLOCK_FP8_W8A16_MAX_M}"
  printf 'vllm_xpu_v4_block_fp8_w8a16_shapes=%s\n' "${VLLM_XPU_V4_BLOCK_FP8_W8A16_SHAPES}"
  printf 'vllm_xpu_mxfp4_small_m_n=%s\n' "${VLLM_XPU_MXFP4_SMALL_M_N}"
  printf 'vllm_xpu_v4_direct_fp8_block_h=%s\n' "${VLLM_XPU_V4_DIRECT_FP8_BLOCK_H}"
  printf 'vllm_xpu_v4_direct_fp8_num_warps=%s\n' "${VLLM_XPU_V4_DIRECT_FP8_NUM_WARPS}"
  printf 'vllm_xpu_v4_split_fp8_block_h=%s\n' "${VLLM_XPU_V4_SPLIT_FP8_BLOCK_H}"
  printf 'vllm_xpu_v4_split_fp8_qk_num_warps=%s\n' "${VLLM_XPU_V4_SPLIT_FP8_QK_NUM_WARPS}"
  printf 'vllm_xpu_v4_split_fp8_pv_num_warps=%s\n' "${VLLM_XPU_V4_SPLIT_FP8_PV_NUM_WARPS}"
  printf 'vllm_xpu_native_mhc=%s\n' "${VLLM_XPU_NATIVE_MHC:-0}"
  printf 'vllm_custom_scopes_for_profiling=%s\n' "${VLLM_CUSTOM_SCOPES_FOR_PROFILING:-0}"
  printf 'vllm_xpu_dspark_disable_draft_graph=%s\n' "${VLLM_XPU_DSPARK_DISABLE_DRAFT_GRAPH:-unset}"
  printf 'vllm_xpu_dspark_piecewise_draft_graph=%s\n' "${VLLM_XPU_DSPARK_PIECEWISE_DRAFT_GRAPH:-unset}"
  printf 'vllm_xpu_dspark_exact_query_capture=%s\n' "${VLLM_XPU_DSPARK_EXACT_QUERY_CAPTURE:-unset}"
  printf 'vllm_xpu_dspark_piecewise_sample_graph=%s\n' "${VLLM_XPU_DSPARK_PIECEWISE_SAMPLE_GRAPH:-unset}"
  printf 'vllm_xpu_dspark_fused_context_wkv=%s\n' "${VLLM_XPU_DSPARK_FUSED_CONTEXT_WKV:-unset}"
  printf 'vllm_xpu_dspark_replicated_markov=%s\n' "${VLLM_XPU_DSPARK_REPLICATED_MARKOV:-unset}"
  printf 'vllm_xpu_greedy_fused_rejection=%s\n' "${VLLM_XPU_GREEDY_FUSED_REJECTION:-unset}"
  printf 'vllm_xpu_greedy_sharded_target_argmax=%s\n' "${VLLM_XPU_GREEDY_SHARDED_TARGET_ARGMAX:-unset}"
  printf 'vllm_xpu_dspark_fixed_m7_target_inputs=%s\n' "${VLLM_XPU_DSPARK_FIXED_M7_TARGET_INPUTS:-unset}"
  printf 'vllm_xpu_dspark_fixed_m8_target_builder=%s\n' "${VLLM_XPU_DSPARK_FIXED_M8_TARGET_BUILDER:-unset}"
  printf 'vllm_xpu_dspark_persistent_markov=%s\n' "${VLLM_XPU_DSPARK_PERSISTENT_MARKOV:-unset}"
  printf 'vllm_xpu_dspark_persistent_markov_width_screen=%s\n' "${VLLM_XPU_DSPARK_PERSISTENT_MARKOV_WIDTH_SCREEN:-unset}"
  printf 'vllm_xpu_dspark_confidence_gate_threshold=%s\n' "${VLLM_XPU_DSPARK_CONFIDENCE_GATE_THRESHOLD:-unset}"
  printf 'vllm_xpu_dspark_draft_prefix_cap=%s\n' "${VLLM_XPU_DSPARK_DRAFT_PREFIX_CAP:-unset}"
  printf 'vllm_xpu_dspark_replicated_markov_w1=%s\n' "${VLLM_XPU_DSPARK_REPLICATED_MARKOV_W1:-unset}"
  printf 'vllm_xpu_dspark_markov_w2_dpas=%s\n' "${VLLM_XPU_DSPARK_MARKOV_W2_DPAS:-unset}"
  printf 'vllm_xpu_v4_mhc_post_pre_m8_dpas=%s\n' "${VLLM_XPU_V4_MHC_POST_PRE_M8_DPAS:-unset}"
  printf 'vllm_xpu_v4_mhc_post_pre_m8_pairtile=%s\n' "${VLLM_XPU_V4_MHC_POST_PRE_M8_PAIRTILE:-unset}"
  printf 'vllm_xpu_dspark_sharded_markov_argmax=%s\n' "${VLLM_XPU_DSPARK_SHARDED_MARKOV_ARGMAX:-unset}"
  printf 'vllm_xpu_dspark_host_markov_argmax=%s\n' "${VLLM_XPU_DSPARK_HOST_MARKOV_ARGMAX:-unset}"
  printf 'vllm_xpu_dspark_ipc_event_markov_argmax=%s\n' "${VLLM_XPU_DSPARK_IPC_EVENT_MARKOV_ARGMAX:-unset}"
  printf 'vllm_xpu_dspark_ipc_event_markov7_bundle=%s\n' "${VLLM_XPU_DSPARK_IPC_EVENT_MARKOV7_BUNDLE:-unset}"
  printf 'vllm_xpu_dspark_ipc_event_count=%s\n' "${VLLM_XPU_DSPARK_IPC_EVENT_COUNT:-unset}"
  printf 'vllm_xpu_dspark_ipc_event_socket=%s\n' "${VLLM_XPU_DSPARK_IPC_EVENT_SOCKET:-unset}"
  printf 'vllm_xpu_dspark_host_markov_shm=%s\n' "${VLLM_XPU_DSPARK_HOST_MARKOV_SHM:-unset}"
  printf 'vllm_xpu_dspark_direct_draft_output=%s\n' "${VLLM_XPU_DSPARK_DIRECT_DRAFT_OUTPUT:-unset}"
  printf 'vllm_xpu_dspark_greedy_copy_elision=%s\n' "${VLLM_XPU_DSPARK_GREEDY_COPY_ELISION:-unset}"
  printf 'dspark_spec_tokens=%s\n' "${DSPARK_SPEC_TOKENS:-unset}"
  printf 'dspark_kv_cache_memory_bytes=%s\n' "${DSPARK_KV_CACHE_MEMORY_BYTES:-unset}"
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
  printf 'oneccl_lib=%s\n' "${oneccl_lib}"
  printf 'oneccl_source_tree=%s\n' "${oneccl_source_tree}"
  if [[ -d "${oneccl_source_tree}/.git" || -f "${oneccl_source_tree}/.git" ]]; then
    printf 'oneccl_source_worktree_head=%s\n' "$(git -C "${oneccl_source_tree}" rev-parse HEAD)"
  fi
  printf 'oneccl_runtime_default_lib=%s\n' "${venv_lib}/libccl.so.1"
  printf 'oneccl_runtime_default_sha256=%s\n' \
    "$(sha256sum "${venv_lib}/libccl.so.1" | awk '{print $1}')"
  printf 'oneccl_runtime_selected_lib=%s\n' "${oneccl_lib}/libccl.so.1"
  printf 'oneccl_runtime_selected_resolved_lib=%s\n' \
    "$(readlink -f "${oneccl_lib}/libccl.so.1")"
  printf 'oneccl_runtime_selected_sha256=%s\n' \
    "$(sha256sum "${oneccl_lib}/libccl.so.1" | awk '{print $1}')"
  printf 'oneccl_force_preload=%s\n' "${ONECCL_FORCE_PRELOAD}"
  printf 'ld_preload=%s\n' "${LD_PRELOAD:-}"
  printf 'ccl_atl_transport=%s\n' "${CCL_ATL_TRANSPORT}"
  printf 'ccl_topo_p2p_access=%s\n' "${CCL_TOPO_P2P_ACCESS}"
  printf 'ccl_enable_sycl_kernels=%s\n' "${CCL_ENABLE_SYCL_KERNELS:-default}"
  printf 'ccl_allreduce=%s\n' "${CCL_ALLREDUCE:-default}"
  printf 'ccl_allgather=%s\n' "${CCL_ALLGATHER:-default}"
  printf 'ccl_allgatherv=%s\n' "${CCL_ALLGATHERV:-default}"
  printf 'ccl_reduce_scatter=%s\n' "${CCL_REDUCE_SCATTER:-default}"
  printf 'ccl_sycl_allreduce_ll=%s\n' "${CCL_SYCL_ALLREDUCE_LL}"
  printf 'ccl_sycl_allreduce_ll_threshold=%s\n' "${CCL_SYCL_ALLREDUCE_LL_THRESHOLD}"
  printf 'ccl_sycl_allreduce_arc=%s\n' "${CCL_SYCL_ALLREDUCE_ARC}"
  printf 'b70_oneccl_sycl_max_bytes=%s\n' "${B70_ONECCL_SYCL_MAX_BYTES:-disabled}"
  printf 'b70_oneccl_sycl_allreduce_max_bytes=%s\n' \
    "${B70_ONECCL_SYCL_ALLREDUCE_MAX_BYTES:-disabled}"
  printf 'b70_oneccl_sycl_allgather_max_bytes=%s\n' \
    "${B70_ONECCL_SYCL_ALLGATHER_MAX_BYTES:-disabled}"
  printf 'b70_oneccl_sycl_reduce_scatter_max_bytes=%s\n' \
    "${B70_ONECCL_SYCL_REDUCE_SCATTER_MAX_BYTES:-disabled}"
  printf 'b70_oneccl_mhc_threads=%s\n' "${B70_ONECCL_MHC_THREADS:-default}"
  printf 'b70_oneccl_mhc_explicit_barrier=%s\n' "${B70_ONECCL_MHC_EXPLICIT_BARRIER:-0}"
  printf 'ccl_kernel_path=%s\n' "${CCL_KERNEL_PATH}"
  printf 'ccl_topo_fabric_vertex_connection_check=%s\n' "${CCL_TOPO_FABRIC_VERTEX_CONNECTION_CHECK:-default}"
  printf 'fi_tcp_iface=%s\n' "${FI_TCP_IFACE}"
  printf 'ccl_kvs_iface=%s\n' "${CCL_KVS_IFACE}"
  printf 'vllm_cache_root=%s\n' "${VLLM_CACHE_ROOT}"
  printf 'torchinductor_cache_dir=%s\n' "${TORCHINDUCTOR_CACHE_DIR}"
  printf 'vllm_multi_stream_gemm_token_threshold=%s\n' "${VLLM_MULTI_STREAM_GEMM_TOKEN_THRESHOLD:-default}"
  printf 'triton_cache_autotuning=%s\n' "${TRITON_CACHE_AUTOTUNING}"
  printf 'vllm_triton_force_first_config=%s\n' "${VLLM_TRITON_FORCE_FIRST_CONFIG}"
  printf 'vllm_extra_args=%s\n' "${VLLM_EXTRA_ARGS:-}"
  printf 'argv='
  printf '%q ' "${argv[@]}"
  printf '\n'
  "${python}" - <<'PY'
import importlib.metadata as metadata
for package in ("torch", "triton-xpu", "vllm", "vllm-xpu-kernels", "oneccl"):
    print(f"package_{package}={metadata.version(package)}")
PY
} >"${run_dir}/identity.txt"

exec "${argv[@]}" \
  >"${run_dir}/server.log" 2>&1
