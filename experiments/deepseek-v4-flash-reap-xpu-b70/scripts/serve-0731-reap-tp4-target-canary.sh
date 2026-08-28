#!/usr/bin/env bash
set -euo pipefail

root="/home/steve/llm-optimizations"
base="${root}/experiments/deepseek-v4-flash-reap-xpu-b70/scripts/serve-k160-tp4-smoke.sh"
model="${MODEL_PATH:-/mnt/usb-models/llm-models/DeepSeek-V4-Flash-0731-REAP}"
revision="ddc04540efda3d2a0788b129f1fad828ddc19b60"
verify="${root}/experiments/deepseek-v4-flash-reap-xpu-b70/scripts/verify-0731-reap-artifact.py"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
profile="${DEEPSEEK_0731_TARGET_PROFILE:-smoke}"
case "${profile}" in
  smoke)
    run_label=canary
    context_tokens=256
    ;;
  full)
    run_label=full
    context_tokens=2048
    ;;
  *)
    printf 'DEEPSEEK_0731_TARGET_PROFILE must be smoke or full\n' >&2
    exit 2
    ;;
esac
export DEEPSEEK_0731_TARGET_PROFILE="${profile}"
vllm_tree="/home/steve/src/deepseek-v4-vllm-record-baseline-264c7f2f7"
kernel_tree="/home/steve/src/deepseek-v4-xpu-kernels-record-313156737"
oneccl_tree="/home/steve/src/oneccl-2021.17.2-b70-sizegate"
oneccl_lib="/mnt/fast-ai/runtime/oneccl-2021.17.2-b70-wideepoch-48fda4f/lib"
python="/home/steve/.venvs/deepseek-v4-xpu/bin/python"
vllm="/home/steve/.venvs/deepseek-v4-xpu/bin/vllm"

test -n "${DEEPSEEK_0731_VALIDATION_SUMMARY:-}"
test -f "${DEEPSEEK_0731_VALIDATION_SUMMARY}"
test ! -L "${DEEPSEEK_0731_VALIDATION_SUMMARY}"
export DEEPSEEK_0731_VALIDATION_SUMMARY="$(realpath -e -- "${DEEPSEEK_0731_VALIDATION_SUMMARY}")"
"${verify}" "${model}" --full-validation-summary "${DEEPSEEK_0731_VALIDATION_SUMMARY}"
test "$(git -C "${vllm_tree}" rev-parse HEAD)" = 264c7f2f7df21ddeeab32ecca0353133344f1ac9
test -z "$(git -C "${vllm_tree}" status --porcelain)"
test "$(git -C "${kernel_tree}" rev-parse HEAD)" = 31315673737d95da0f79179c8f755260ef02c1d6
test -z "$(git -C "${kernel_tree}" status --porcelain)"
test "$(git -C "${oneccl_tree}" rev-parse HEAD)" = 48fda4f0e074db005596d6899d5227d3f0316c12
git -C "${oneccl_tree}" diff --quiet
git -C "${oneccl_tree}" diff --cached --quiet
test "$(sha256sum "${kernel_tree}/vllm_xpu_kernels/_xpu_C.abi3.so" | awk '{print $1}')" = \
  c0597c1db9d1e684462adce681101957e7a969baab3c0c71fb748ca7fd8c24e9
test "$(sha256sum "${oneccl_lib}/libccl.so.1" | awk '{print $1}')" = \
  53de2b6d65265803d64773546c1166ceed4ae43737f0fded776f5847b4b461c9
PYTHONPATH="${vllm_tree}:${kernel_tree}" "${python}" - <<'PY'
from importlib.metadata import version

expected = {
    "torch": "2.12.0+xpu",
    "triton-xpu": "3.7.1",
    "vllm": "0.1.dev1172+g4a6fd8747.xpu",
    "vllm-xpu-kernels": "0.1.11.dev53+g744a8b4",
    "oneccl": "2021.17.2",
}
actual = {name: version(name) for name in expected}
if actual != expected:
    raise SystemExit(f"record venv package identity mismatch: {actual!r}")
PY

export MODEL_PATH="${model}"
export MODEL_REVISION="${revision}"
export MODEL_VERIFY_SCRIPT="${verify}"
export MODEL_MANIFEST_FILE=SHA256SUMS
export SERVED_MODEL_NAME=deepseek-v4-flash-0731-reap-k160
export VLLM_TREE="${vllm_tree}"
export VLLM_COMMIT=264c7f2f7df21ddeeab32ecca0353133344f1ac9
export KERNEL_TREE="${kernel_tree}"
export KERNEL_COMMIT=31315673737d95da0f79179c8f755260ef02c1d6
export PYTHONPATH="${VLLM_TREE}:${KERNEL_TREE}"
export DEEPSEEK_PYTHON="${python}"
export VLLM_CLI="${vllm}"

export ONECCL_INSTALL_DIR=/home/steve/.venvs/deepseek-v4-xpu
export ONECCL_LIB_DIR="${oneccl_lib}"
export ONECCL_SOURCE_TREE="${oneccl_tree}"
export ONECCL_FORCE_PRELOAD=1
export B70_ONECCL_SYCL_ALLREDUCE_MAX_BYTES=131072
export B70_ONECCL_SYCL_MAX_BYTES=
export B70_ONECCL_SYCL_ALLGATHER_MAX_BYTES=
export B70_ONECCL_SYCL_REDUCE_SCATTER_MAX_BYTES=
export CCL_ATL_TRANSPORT=ofi
export CCL_TOPO_P2P_ACCESS=1
export CCL_SYCL_ALLREDUCE_LL=ring
export CCL_SYCL_ALLREDUCE_LL_THRESHOLD=4096
export CCL_SYCL_ALLREDUCE_ARC=0
export FI_TCP_IFACE=eno1
export CCL_KVS_IFACE=eno1
unset LD_PRELOAD LD_LIBRARY_PATH CCL_ALLREDUCE CCL_ALLGATHER CCL_ALLGATHERV
unset CCL_REDUCE_SCATTER CCL_ENABLE_SYCL_KERNELS CCL_WORKER_COUNT CCL_ZE_IPC_EXCHANGE
unset B70_ONECCL_MHC_THREADS B70_ONECCL_MHC_EXPLICIT_BARRIER
unset CCL_TOPO_FABRIC_VERTEX_CONNECTION_CHECK

export RUN_DIR="/mnt/fast-ai/bench-results/deepseek-v4-flash-0731-reap/target-eager-${run_label}-${stamp}"
export VLLM_CACHE_ROOT="/mnt/fast-ai/vllm-cache-exp/deepseek-v4-flash-0731-reap-${revision}/target-eager-${stamp}/vllm"
export TORCHINDUCTOR_CACHE_DIR="/mnt/fast-ai/vllm-cache-exp/deepseek-v4-flash-0731-reap-${revision}/target-eager-${stamp}/torchinductor"
test ! -e "${RUN_DIR}"
test ! -e "${VLLM_CACHE_ROOT}"
test ! -e "${TORCHINDUCTOR_CACHE_DIR}"
export MAX_MODEL_LEN="${context_tokens}"
export MAX_NUM_BATCHED_TOKENS="${context_tokens}"
export GPU_MEMORY_UTILIZATION=0.95
export TP_SIZE=4
export PP_SIZE=1
export DP_SIZE=1
export DP_SIZE_LOCAL=1
export ONEAPI_DEVICE_SELECTOR='level_zero:*'
export ZE_AFFINITY_MASK=0,1,2,3
export RUN_PREFLIGHT=1
export PORT=18080
export XPU_GRAPH=0
export VLLM_XPU_ENABLE_XPU_GRAPH=0
export VLLM_XPU_FORCE_GRAPH_WITH_COMM=0
export VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE=0
export COMPILATION_CONFIG='{"cudagraph_mode":"NONE"}'
export ENFORCE_EAGER=1
export VERIFY_MANIFEST=0

# Checkpoint-isolation arm: no draft and no record performance overlay.  Clear
# every historical optional selector explicitly so a caller's environment
# cannot contaminate the frozen arm.
zero_selectors=(
  VLLM_XPU_V4_DIRECT_FP8_ATTN VLLM_XPU_V4_SPLIT_FP8_ATTN
  VLLM_XPU_V4_FP8_WO_A VLLM_XPU_V4_INPLACE_ALLREDUCE
  VLLM_XPU_V4_INPLACE_ALLREDUCE_M2 VLLM_XPU_V4_SEGMENTED_ALLREDUCE_MAX_M
  VLLM_XPU_DPEP_ALLREDUCE VLLM_XPU_DPEP_SWITCH_SYNC VLLM_XPU_DPEP_NATIVE
  VLLM_XPU_V4_MHC_NORM_FUSION VLLM_XPU_V4_TP4_RING_MHC_POST
  VLLM_XPU_V4_TP4_RING_MHC_POST_PRE VLLM_XPU_V4_MHC_PRE_M1_SINGLE_KERNEL
  VLLM_XPU_V4_MHC_POST_PRE_M1_SINGLE_KERNEL VLLM_XPU_V4_MHC_POST_PRE_M2_SINGLE_KERNEL
  VLLM_XPU_V4_MHC_POST_PRE_M1_RMS
  VLLM_XPU_V4_MHC_POST_PRE_FIXED_WIDTH_MAX_M VLLM_XPU_V4_SHARED_EXPERT_FUSED_ACT_QUANT
  VLLM_XPU_V4_SHARED_EXPERT_FUSED_ACT_QUANT_MAX_M VLLM_XPU_V4_M2_ROUTED_CLAMP_SILU
  VLLM_XPU_MOE_OUTPUT_ALIAS VLLM_XPU_V4_M1_BIASED_TOPK VLLM_XPU_V4_M1_ROUTER_NORM
  VLLM_XPU_V4_M2_ROUTER_NORM VLLM_XPU_V4_M1_DIRECT_ROUTED_MOE
  VLLM_XPU_V4_M2_ROUTE_DIRECT_COMPACT VLLM_XPU_V4_DIRECT_ROUTED_MOE_ALLOW_256_EXPERT_FALLBACK
  VLLM_XPU_V4_NATIVE_DUAL_RMSNORM VLLM_XPU_V4_FUSED_QNORM_ROPE_KV_INSERT
  VLLM_XPU_V4_FUSED_QNORM_ROPE_KV_INSERT_MAX_M VLLM_XPU_V4_COMPRESSOR_M2_ROW_EXACT
  VLLM_XPU_V4_COMPRESSOR_M2_BATCHED_EXACT VLLM_XPU_V4_COMPRESSOR_ROW_EXACT_MAX_M
  VLLM_XPU_V4_COMPRESSOR_BATCHED_EXACT_MAX_M VLLM_XPU_V4_FORWARD_DEVICE_SYNC
  VLLM_XPU_EXPERT_MAP_ROUND_ROBIN VLLM_XPU_V4_BLOCK_FP8_W8A16
  VLLM_XPU_V4_BLOCK_FP8_W8A16_MAX_M VLLM_XPU_NATIVE_MHC
  VLLM_XPU_DSPARK_DISABLE_DRAFT_GRAPH VLLM_XPU_DSPARK_PIECEWISE_DRAFT_GRAPH
  VLLM_XPU_DSPARK_EXACT_QUERY_CAPTURE VLLM_XPU_DSPARK_PIECEWISE_SAMPLE_GRAPH
  VLLM_XPU_DSPARK_FUSED_CONTEXT_WKV VLLM_XPU_DSPARK_REPLICATED_MARKOV
  VLLM_XPU_GREEDY_FUSED_REJECTION VLLM_XPU_GREEDY_SHARDED_TARGET_ARGMAX
  VLLM_XPU_DSPARK_FIXED_M7_TARGET_INPUTS VLLM_XPU_DSPARK_FIXED_M8_TARGET_BUILDER
  VLLM_XPU_DSPARK_PERSISTENT_MARKOV VLLM_XPU_DSPARK_PERSISTENT_MARKOV_WIDTH_SCREEN
  VLLM_XPU_DSPARK_REPLICATED_MARKOV_W1 VLLM_XPU_DSPARK_MARKOV_W2_DPAS
  VLLM_XPU_V4_MHC_POST_PRE_M8_DPAS VLLM_XPU_V4_MHC_POST_PRE_M8_PAIRTILE
  VLLM_XPU_DSPARK_SHARDED_MARKOV_ARGMAX VLLM_XPU_DSPARK_HOST_MARKOV_ARGMAX
  VLLM_XPU_DSPARK_IPC_EVENT_MARKOV_ARGMAX VLLM_XPU_DSPARK_IPC_EVENT_MARKOV7_BUNDLE
  VLLM_XPU_DSPARK_DIRECT_DRAFT_OUTPUT VLLM_XPU_DSPARK_GREEDY_COPY_ELISION
)
for selector in "${zero_selectors[@]}"; do
  export "${selector}=0"
done
export VLLM_XPU_FUSED_MOE_USE_REF=0
export VLLM_XPU_FUSED_MOE_USE_MXFP4_FP8=0
export VLLM_XPU_MXFP4_SMALL_M_N=64
export VLLM_XPU_V4_ROUTER_NORM_MAX_M=0
export VLLM_XPU_V4_BLOCK_FP8_W8A16_SHAPES=
export VLLM_XPU_LOG_FP8_LINEAR_SHAPES=0
# Stock XPU runtime default. This is the ordinary sampler, not the optional
# sharded target-argmax or DSpark sampler selectors frozen to zero above.
export VLLM_XPU_USE_SAMPLER_KERNEL=1
export VLLM_CUSTOM_SCOPES_FOR_PROFILING=0
export VLLM_MULTI_STREAM_GEMM_TOKEN_THRESHOLD=1024
export TRITON_CACHE_AUTOTUNING=1
export VLLM_TRITON_FORCE_FIRST_CONFIG=0
export VLLM_XPU_V4_CAPTURE_CYCLE_WIDTH=2
export VLLM_XPU_V4_CAPTURE_CYCLE_DIR=
export VLLM_XPU_V4_CAPTURE_CYCLE_ARM_FILE="${RUN_DIR}/disabled-cycle-capture.arm"
export VLLM_XPU_V4_DIRECT_FP8_BLOCK_H=16
export VLLM_XPU_V4_DIRECT_FP8_NUM_WARPS=8
export VLLM_XPU_V4_SPLIT_FP8_BLOCK_H=16
export VLLM_XPU_V4_SPLIT_FP8_QK_NUM_WARPS=8
export VLLM_XPU_V4_SPLIT_FP8_PV_NUM_WARPS=4
export VLLM_XPU_V4_DIVERGENCE_CAPTURE_DIR=
export VLLM_XPU_V4_DIVERGENCE_ARM_FILE="${RUN_DIR}/disabled-divergence.arm"
export VLLM_XPU_V4_DIVERGENCE_STAGES=layer_out
export VLLM_XPU_V4_DIVERGENCE_LAYERS=all
export VLLM_XPU_V4_DIVERGENCE_MODE=hash
export VLLM_XPU_V4_DIVERGENCE_MAX_RECORDS=2048
export VLLM_XPU_DSPARK_CONFIDENCE_GATE_THRESHOLD=
export VLLM_XPU_DSPARK_DRAFT_PREFIX_CAP=0
unset VLLM_XPU_DSPARK_HOST_MARKOV_SHM VLLM_XPU_DSPARK_IPC_EVENT_COUNT
unset VLLM_XPU_DSPARK_IPC_EVENT_SOCKET DSPARK_SPEC_TOKENS
export DSPARK_KV_CACHE_MEMORY_BYTES=125829120
export VLLM_EXTRA_ARGS="--enable-prompt-tokens-details --kv-cache-memory 125829120"

printf 'DeepSeek V4 Flash 0731 REAP K160 target-only eager %s arm\n' "${profile}"
printf 'model_revision=%s\n' "${revision}"
printf 'run_dir=%s\n' "${RUN_DIR}"
printf 'crypto_receipt=%s\n' "${DEEPSEEK_0731_VALIDATION_SUMMARY}"
exec "${base}"
