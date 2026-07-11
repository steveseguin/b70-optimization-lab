#!/usr/bin/env bash
set -euo pipefail

# Experimental exact MTP3 linear tree. The target sees the same root plus
# three sequential draft tokens as ordinary MTP3, but TREE_ATTN's graph-static
# state transaction permits one FULL_DECODE_ONLY target graph instead of the
# record lane's 33 PIECEWISE segments.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
ONECCL_INSTALL_DIR="${ONECCL_INSTALL_DIR:-/mnt/usb-models/llm-runtime/oneccl-4ceafd1-b70}"
ONECCL_LIB="$ONECCL_INSTALL_DIR/lib/libccl.so.1.0"
ONECCL_KERNELS="$ONECCL_INSTALL_DIR/lib/ccl/kernels/kernels.spv"
VALIDATED_LIB_SHA256="43d94d43506e30096dd099b9d53b54f932be964751e92ff0cbb8d3a37fad6700"
VALIDATED_KERNELS_SHA256="0d549c35a558f1b216cb7d1efeaa9f86d7596ffc47b383644e075290d314f0c9"

[[ -f "$ONECCL_LIB" && -f "$ONECCL_KERNELS" ]] || {
  echo "validated oneCCL build is missing under $ONECCL_INSTALL_DIR" >&2
  exit 2
}
[[ "$(sha256sum "$ONECCL_LIB" | awk '{print $1}')" == "$VALIDATED_LIB_SHA256" ]] || exit 3
[[ "$(sha256sum "$ONECCL_KERNELS" | awk '{print $1}')" == "$VALIDATED_KERNELS_SHA256" ]] || exit 3

export MODEL_DIR="${MODEL_DIR:-/mnt/fast-ai/llm-cache/hf/hub/models--webhie--Qwen3.6-27B-int4-AutoRound/snapshots/f5750c90b3776db658594df5fe8051098226dd8e}"
export LABEL="${LABEL:-qwen27-tp2-fp16-fixedchain-fullgraph}"
export GPU_INDEX="${GPU_INDEX:-0,1}"
export ZE_AFFINITY_MASK="${ZE_AFFINITY_MASK:-$GPU_INDEX}"
export ONEAPI_DEVICE_SELECTOR="${ONEAPI_DEVICE_SELECTOR:-level_zero:0,1}"
export TENSOR_PARALLEL_SIZE=2
export PORT="${PORT:-19446}"
export MAX_MODEL_LEN="${MAX_MODEL_LEN:-2048}"
export MAX_NUM_BATCHED_TOKENS="${MAX_NUM_BATCHED_TOKENS:-1024}"
export MAX_NUM_SEQS=1
export GPU_MEMORY_UTILIZATION="${GPU_MEMORY_UTILIZATION:-0.95}"

export QWEN36_27B_ENABLE_MTP=0
export QWEN36_27B_ENABLE_XPU_GRAPH=1
# Tree proposal currently supplies an optional hidden-state input as None on
# the first live call; AOT draft capture specializes it as a tensor and fails.
# Keep only the small proposer eager while retaining the full target graph.
export QWEN36_27B_SPECULATIVE_CONFIG='{"method":"qwen3_next_mtp","num_speculative_tokens":3,"speculative_token_tree":"[(0,), (0, 0), (0, 0, 0)]","attention_backend":"TREE_ATTN","enforce_eager":true}'
export COMPILATION_CONFIG='{"cudagraph_mode":"FULL_DECODE_ONLY","cudagraph_capture_sizes":[4],"max_cudagraph_capture_size":4}'
export VLLM_EXTRA_ARGS="--dtype float16 --no-async-scheduling --mamba-cache-mode align --attention-backend TREE_ATTN --generation-config vllm"

export VLLM_XPU_ENABLE_XPU_GRAPH=1
export VLLM_XPU_FORCE_GRAPH_WITH_COMM=1
export VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE=1
export VLLM_XPU_COMPILE_ALLGATHER_CUSTOM_OP=1
export VLLM_XPU_LM_HEAD_INT8=1
export VLLM_XPU_LM_HEAD_INT8_SCALE_DTYPE=bf16
export VLLM_XPU_DRAFT_LM_HEAD_INT4=1
export VLLM_XPU_DRAFT_LM_HEAD_INT4_GROUP_SIZE=128
export VLLM_XPU_DRAFT_LM_HEAD_INT4_SCALE_DTYPE=bf16
export VLLM_XPU_GDN_NATIVE_SPEC_PREFIX_BASE_STATE=1
export VLLM_XPU_GDN_NONSPEC_POSTPROCESS_ACCEPTED_STATE=1
export VLLM_XPU_GDN_PROMOTE_ACCEPTED_SPEC_STATE=0
export VLLM_XPU_DFLASH_DDTREE_BUDGET=3
export VLLM_XPU_DDTREE_NATIVE_KV_COPY=1
export VLLM_XPU_DDTREE_NATIVE_TREE_ATTN=1
export VLLM_XPU_TREE_ATTN_BOOL_SDPA=1
export VLLM_XPU_DDTREE_CAPTURE_GDN_CORE=1
export VLLM_XPU_DDTREE_FULL_GRAPH=1

export ONECCL_CANDIDATE_PATH="$ONECCL_LIB"
export ONECCL_CANDIDATE_SHA256="$VALIDATED_LIB_SHA256"
export ONECCL_KERNELS_SHA256="$VALIDATED_KERNELS_SHA256"
export SERVER_LD_PRELOAD="$ONECCL_LIB"
export SERVER_LD_LIBRARY_PATH="$ONECCL_INSTALL_DIR/lib:/home/steve/.venvs/vllm-xpu/lib:/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/lib"
export SERVER_CCL_KERNEL_PATH="$ONECCL_INSTALL_DIR/lib/ccl/kernels"
export CCL_ATL_TRANSPORT="${CCL_ATL_TRANSPORT:-ofi}"
export CCL_TOPO_P2P_ACCESS="${CCL_TOPO_P2P_ACCESS:-1}"
export CCL_ZE_IPC_EXCHANGE="${CCL_ZE_IPC_EXCHANGE:-pidfd}"

export BENCH_MAX_TOKENS="${BENCH_MAX_TOKENS:-256}"
export BENCH_METRIC_TOKENS=100
export RUN_QUALITY="${RUN_QUALITY:-0}"
export QUALITY_REPEAT_RUNS="${QUALITY_REPEAT_RUNS:-0}"
export CANDIDATE_ENTRYPOINT="$0"

exec "$ROOT/experiments/qwen36-27b-autoround-int4-b70/scripts/run-vllm-candidate.sh"
