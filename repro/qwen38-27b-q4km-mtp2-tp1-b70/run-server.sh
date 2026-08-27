#!/usr/bin/env bash
set -euo pipefail
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
target_dir=${TARGET_DIR:?set TARGET_DIR}
draft_dir=${DRAFT_DIR:?set DRAFT_DIR}
build_dir=${BUILD_DIR:?set BUILD_DIR}
gpu=${GPU_INDEX:-0}
host=${HOST_ADDR:-127.0.0.1}
port=${PORT:-18139}
ctx_size=${CTX_SIZE:-8192}
parallel_slots=${PARALLEL_SLOTS:-1}
ubatch_size=${UBATCH_SIZE:-512}
threads=${THREADS:-16}
[[ "${gpu}" =~ ^[0-9]+$ ]] || { printf 'GPU_INDEX must be numeric\n' >&2; exit 2; }
[[ "${ctx_size}" =~ ^[1-9][0-9]*$ ]] || { printf 'CTX_SIZE must be positive\n' >&2; exit 2; }
[[ "${parallel_slots}" =~ ^[1-9][0-9]*$ ]] || { printf 'PARALLEL_SLOTS must be positive\n' >&2; exit 2; }
[[ "${ubatch_size}" =~ ^[1-9][0-9]*$ ]] || { printf 'UBATCH_SIZE must be positive\n' >&2; exit 2; }
[[ "${threads}" =~ ^[1-9][0-9]*$ ]] || { printf 'THREADS must be positive\n' >&2; exit 2; }
pgrep -x llama-server >/dev/null && { printf 'Another llama-server is running\n' >&2; exit 1; }
"${script_dir}/preflight.sh"
set +u
# shellcheck disable=SC1091
source /opt/intel/oneapi/setvars.sh --force >/dev/null 2>&1
set -u
export ONEAPI_DEVICE_SELECTOR="level_zero:${gpu}"
export GGML_SYCL_ENABLE_GRAPH=0 UR_L0_USE_IMMEDIATE_COMMANDLISTS=1 UR_L0_V2_FORCE_DISABLE_COPY_OFFLOAD=1
export GGML_SYCL_COMM_SINGLE_KERNEL=1 GGML_META_FUSE_ALLREDUCE_ADD=1 GGML_META_FUSE_ALLREDUCE_ADD_RMS_MUL=1
export GGML_SYCL_COMM_FUSED_Q8=1 GGML_SYCL_FUSED_SWIGLU_Q8=1 GGML_SYCL_FUSED_ATTN_Q8=1 GGML_SYCL_FUSED_GDN_Q8=1
export GGML_SYCL_FUSED_MMVQ_PAIR=1 GGML_SYCL_FUSED_MMVQ_SWIGLU_Q4K=1 GGML_SYCL_FUSED_MMVQ_PAIR_GDN=1
export GGML_SYCL_FUSED_MMVQ_TRIPLE_ATTN=1 GGML_SYCL_FUSED_MMVQ_TRIPLE_GDN=1 GGML_SYCL_FUSED_MMVQ_QUAD_GDN=1
export GGML_SYCL_FUSED_GDN_BETA_SIGMOID=1 GGML_SYCL_FUSED_CONCAT_STATE=1 GGML_SYCL_FUSED_GDN_STATE_IO=1 GGML_SYCL_FUSED_CONV_STATE_IO=1
export GGML_SYCL_COMM_DIRECT_Q8=2 GGML_SYCL_FUSED_ROPE_SET_ROWS=1 GGML_SYCL_COMM_REDUCE_VEC4=1 GGML_SYCL_FUSED_QK_NORM_ROPE=1
export GGML_SYCL_FUSED_CONV_SILU_L2=1 GGML_SYCL_FUSE_EXT=31 GGML_SYCL_QDEDUP_STATS=1 GGML_SYCL_MMQ_Q4K_REORDER=1
unset GGML_SYCL_WDC GGML_SYCL_WDC_Q4K GGML_SYCL_REORDER_IN_GEMM GGML_SYCL_FORCE_REORDER GGML_SYCL_FORCE_REORDER_Q4K GGML_SYCL_DISABLE_REORDER_Q6K
exec systemd-run --user --scope --quiet --property=MemoryHigh=11G --property=MemoryMax=13G --property=MemorySwapMax=12G \
  "${build_dir}/bin/llama-server" \
  --model "${target_dir}/Qwen3.8-27B-Q4_K_M.gguf" --device SYCL0 --gpu-layers 99 --split-mode none --fit off \
  --model-draft "${draft_dir}/mtp-Qwen3.8-27B-Q4_0.gguf" --device-draft SYCL0 --gpu-layers-draft 99 \
  --spec-type draft-mtp --spec-draft-n-max 2 --spec-draft-n-min 0 --spec-draft-p-min 0 \
  --cache-type-k f16 --cache-type-v f16 --cache-type-k-draft f16 --cache-type-v-draft f16 \
  --flash-attn on --batch-size 2048 --ubatch-size "${ubatch_size}" --cache-ram 0 --ctx-checkpoints 0 \
  --reasoning off --threads "${threads}" --poll 50 --ctx-size "${ctx_size}" --parallel "${parallel_slots}" --cont-batching \
  --no-cache-prompt --slot-prompt-similarity 0 --metrics --host "${host}" --port "${port}"
