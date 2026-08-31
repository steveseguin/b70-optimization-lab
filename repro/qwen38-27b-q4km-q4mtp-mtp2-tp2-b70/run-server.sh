#!/usr/bin/env bash
set -euo pipefail
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
target_dir=${TARGET_DIR:?set TARGET_DIR}
draft_dir=${DRAFT_DIR:?set DRAFT_DIR}
build_dir=${BUILD_DIR:?set BUILD_DIR}
mtp_depth=${MTP_DEPTH:-2}
host=${HOST_ADDR:-127.0.0.1}
port=${PORT:-18142}
ctx_size=${CTX_SIZE:-8192}
parallel_slots=${PARALLEL_SLOTS:-1}
batch_size=${BATCH_SIZE:-1024}
ubatch_size=${UBATCH_SIZE:-256}
threads=${THREADS:-8}
wdc_q4k=${WDC_Q4K:-0}
wdc_q4k_name_filter=${WDC_Q4K_NAME_FILTER:-}
q4k_f16_cache_filter=${Q4K_F16_CACHE_FILTER:-}
q4k_dual_gemm=${Q4K_DUAL_GEMM:-0}
f16_act_dedup=${F16_ACT_DEDUP:-0}
q4k_reorder=${Q4K_REORDER:-0}
queue_settle_ms=${QUEUE_SETTLE_MS:-0}
queue_settle_target=${QUEUE_SETTLE_TARGET:-0}
tp_size=${TP_SIZE:-2}
feature_profile=${FEATURE_PROFILE:-tuned}
q8_dedup_override=${Q8_DEDUP_OVERRIDE:-}
fuse_ext=${FUSE_EXT_OVERRIDE:-15}
[[ "${mtp_depth}" == 0 || "${mtp_depth}" == 2 ]] || { printf 'MTP_DEPTH must be 0 or 2\n' >&2; exit 2; }
[[ "${wdc_q4k}" == 0 || "${wdc_q4k}" == 1 ]] || { printf 'WDC_Q4K must be 0 or 1\n' >&2; exit 2; }
[[ "${wdc_q4k_name_filter}" =~ ^[A-Za-z0-9_.,-]*$ ]] || { printf 'WDC_Q4K_NAME_FILTER contains unsupported characters\n' >&2; exit 2; }
[[ -z "${wdc_q4k_name_filter}" || "${wdc_q4k}" == 1 ]] || { printf 'WDC_Q4K_NAME_FILTER requires WDC_Q4K=1\n' >&2; exit 2; }
[[ "${q4k_f16_cache_filter}" =~ ^[A-Za-z0-9_.,-]*$ ]] || { printf 'Q4K_F16_CACHE_FILTER contains unsupported characters\n' >&2; exit 2; }
[[ -z "${q4k_f16_cache_filter}" || "${wdc_q4k}" == 0 ]] || { printf 'Q4K_F16_CACHE_FILTER cannot be combined with WDC_Q4K=1\n' >&2; exit 2; }
[[ "${q4k_dual_gemm}" == 0 || "${q4k_dual_gemm}" == 1 ]] || { printf 'Q4K_DUAL_GEMM must be 0 or 1\n' >&2; exit 2; }
[[ "${q4k_dual_gemm}" == 0 || ( "${q4k_f16_cache_filter}" == *ffn_gate* && "${q4k_f16_cache_filter}" == *ffn_up* ) ]] || { printf 'Q4K_DUAL_GEMM=1 requires ffn_gate and ffn_up in Q4K_F16_CACHE_FILTER\n' >&2; exit 2; }
[[ "${f16_act_dedup}" == 0 || "${f16_act_dedup}" == 1 ]] || { printf 'F16_ACT_DEDUP must be 0 or 1\n' >&2; exit 2; }
[[ "${f16_act_dedup}" == 0 || "${q4k_f16_cache_filter}" == *ffn_gate* ]] || { printf 'F16_ACT_DEDUP=1 requires ffn_gate in Q4K_F16_CACHE_FILTER\n' >&2; exit 2; }
[[ "${q4k_reorder}" == 0 || "${q4k_reorder}" == 1 ]] || { printf 'Q4K_REORDER must be 0 or 1\n' >&2; exit 2; }
[[ "${wdc_q4k}" == 0 || "${q4k_reorder}" == 1 ]] || { printf 'WDC_Q4K=1 requires Q4K_REORDER=1\n' >&2; exit 2; }
[[ "${queue_settle_ms}" =~ ^[0-9]+$ ]] && (( queue_settle_ms <= 5000 )) || { printf 'QUEUE_SETTLE_MS must be an integer from 0 through 5000\n' >&2; exit 2; }
[[ "${queue_settle_target}" =~ ^[0-9]+$ ]] && (( queue_settle_target <= 1024 )) || { printf 'QUEUE_SETTLE_TARGET must be an integer from 0 through 1024\n' >&2; exit 2; }
(( queue_settle_target == 0 || queue_settle_ms > 0 )) || { printf 'QUEUE_SETTLE_TARGET requires QUEUE_SETTLE_MS > 0\n' >&2; exit 2; }
[[ "${tp_size}" == 1 || "${tp_size}" == 2 ]] || { printf 'TP_SIZE must be 1 or 2\n' >&2; exit 2; }
[[ "${feature_profile}" == tuned || "${feature_profile}" == reference || "${feature_profile}" == base ]] || { printf 'FEATURE_PROFILE must be tuned, reference, or base\n' >&2; exit 2; }
[[ -z "${q8_dedup_override}" || "${q8_dedup_override}" == 0 || "${q8_dedup_override}" == 1 || "${q8_dedup_override}" == 2 ]] || { printf 'Q8_DEDUP_OVERRIDE must be empty, 0, 1, or 2\n' >&2; exit 2; }
[[ "${fuse_ext}" =~ ^[0-9]+$ ]] && (( fuse_ext <= 31 )) || { printf 'FUSE_EXT_OVERRIDE must be 0..31\n' >&2; exit 2; }
for value in "${ctx_size}" "${parallel_slots}" "${batch_size}" "${ubatch_size}" "${threads}"; do
  [[ "${value}" =~ ^[1-9][0-9]*$ ]] || { printf 'numeric settings must be positive integers\n' >&2; exit 2; }
done
pgrep -x llama-server >/dev/null && { printf 'Another llama-server is running\n' >&2; exit 1; }
exec 9>/tmp/b70-model-host.lock
flock -n 9 || { printf 'Another model campaign owns the host lock\n' >&2; exit 1; }
exec 8>/tmp/b70-gpu0.lock
flock -n 8 || { printf 'GPU 0 is locked\n' >&2; exit 1; }
exec 10>/tmp/b70-gpu1.lock
flock -n 10 || { printf 'GPU 1 is locked\n' >&2; exit 1; }
"${script_dir}/preflight.sh"
set +u
# shellcheck disable=SC1091
source /opt/intel/oneapi/setvars.sh --force >/dev/null 2>&1
set -u
export ONEAPI_DEVICE_SELECTOR=level_zero:1,0
export LD_LIBRARY_PATH="${build_dir}/bin${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"
export GGML_SYCL_ENABLE_GRAPH=0 UR_L0_USE_IMMEDIATE_COMMANDLISTS=1 UR_L0_V2_FORCE_DISABLE_COPY_OFFLOAD=1
export GGML_SYCL_COMM_SINGLE_KERNEL=1 GGML_META_FUSE_ALLREDUCE_ADD=1 GGML_META_FUSE_ALLREDUCE_ADD_RMS_MUL=1
export GGML_SYCL_COMM_FUSED_Q8=1 GGML_SYCL_FUSED_SWIGLU_Q8=1 GGML_SYCL_FUSED_ATTN_Q8=1 GGML_SYCL_FUSED_GDN_Q8=1
export GGML_SYCL_FUSED_MMVQ_PAIR=1 GGML_SYCL_FUSED_MMVQ_SWIGLU_Q4K=1 GGML_SYCL_FUSED_MMVQ_PAIR_GDN=1
export GGML_SYCL_FUSED_MMVQ_TRIPLE_ATTN=1 GGML_SYCL_FUSED_MMVQ_TRIPLE_GDN=1 GGML_SYCL_FUSED_MMVQ_QUAD_GDN=1
export GGML_SYCL_FUSED_GDN_BETA_SIGMOID=1 GGML_SYCL_FUSED_CONCAT_STATE=1 GGML_SYCL_FUSED_GDN_STATE_IO=1 GGML_SYCL_FUSED_CONV_STATE_IO=1
export GGML_SYCL_COMM_DIRECT_Q8=2 GGML_SYCL_FUSED_ROPE_SET_ROWS=1 GGML_SYCL_COMM_REDUCE_VEC4=1 GGML_SYCL_FUSED_QK_NORM_ROPE=1
# Bits 0..3 are qualified. Bit 4 is an experimental recurrent-tail fusion and
# must remain default-off until it independently passes the output oracle.
export GGML_SYCL_FUSED_CONV_SILU_L2=1 GGML_SYCL_FUSE_EXT="${fuse_ext}" GGML_SYCL_QDEDUP_STATS=1 GGML_SYCL_MMQ_Q4K_REORDER=1
export GGML_SYCL_WDC=off
export LLAMA_SERVER_QUEUE_SETTLE_MS="${queue_settle_ms}"
export LLAMA_SERVER_QUEUE_SETTLE_TARGET="${queue_settle_target}"
if [[ "${feature_profile}" == reference || "${feature_profile}" == base ]]; then
  # Diagnostic control: disable every lab fusion/reorder/collective door so a
  # strict replay can distinguish shared optimized kernels from the base path.
  export GGML_META_FUSE_ALLREDUCE_ADD=0 GGML_META_FUSE_ALLREDUCE_ADD_RMS_MUL=0
  export GGML_SYCL_COMM_DIRECT_Q8=0 GGML_SYCL_COMM_FUSED_Q8=0 GGML_SYCL_COMM_REDUCE_VEC4=0 GGML_SYCL_COMM_SINGLE_KERNEL=0
  export GGML_SYCL_FUSED_ATTN_Q8=0 GGML_SYCL_FUSED_CONCAT_STATE=0 GGML_SYCL_FUSED_CONV_SILU_L2=0 GGML_SYCL_FUSED_CONV_STATE_IO=0
  export GGML_SYCL_FUSED_GDN_BETA_SIGMOID=0 GGML_SYCL_FUSED_GDN_Q8=0 GGML_SYCL_FUSED_GDN_STATE_IO=0
  export GGML_SYCL_FUSED_MMVQ_PAIR=0 GGML_SYCL_FUSED_MMVQ_PAIR_GDN=0 GGML_SYCL_FUSED_MMVQ_QUAD_GDN=0
  export GGML_SYCL_FUSED_MMVQ_SWIGLU_Q4K=0 GGML_SYCL_FUSED_MMVQ_TRIPLE_ATTN=0 GGML_SYCL_FUSED_MMVQ_TRIPLE_GDN=0
  export GGML_SYCL_FUSED_QK_NORM_ROPE=0 GGML_SYCL_FUSED_ROPE_SET_ROWS=0 GGML_SYCL_FUSED_SWIGLU_Q8=0
  export GGML_SYCL_FUSE_EXT=0 GGML_SYCL_MMQ_Q4K_REORDER=0 GGML_SYCL_QDEDUP_STATS=0
  unset GGML_SYCL_REORDER_IN_GEMM GGML_SYCL_FORCE_REORDER_Q4K GGML_SYCL_DISABLE_REORDER_Q6K
fi
if [[ "${feature_profile}" == base ]]; then
  export GGML_SYCL_ENABLE_OPT=0 GGML_SYCL_ENABLE_DNN=0 GGML_SYCL_ENABLE_FUSION=0 GGML_SYCL_ENABLE_MMQ=0
  export GGML_SYCL_Q8_QUANT_DEDUP=0 GGML_SYCL_MMVQ_PAD=0 GGML_SYCL_MMVQ_SPLIT=0 GGML_SYCL_MKL_DIRECT=0
  export UR_L0_USE_IMMEDIATE_COMMANDLISTS=0
fi
if [[ -n "${q8_dedup_override}" ]]; then
  export GGML_SYCL_Q8_QUANT_DEDUP="${q8_dedup_override}"
fi
unset GGML_SYCL_FORCE_REORDER
if [[ "${feature_profile}" == tuned && "${q4k_reorder}" == 1 ]]; then
  # WDC comparisons set this in both arms, keeping WDC as the only variable.
  export GGML_SYCL_REORDER_IN_GEMM=1 GGML_SYCL_FORCE_REORDER_Q4K=1
  export GGML_SYCL_DISABLE_REORDER_Q6K=1
else
  unset GGML_SYCL_REORDER_IN_GEMM GGML_SYCL_FORCE_REORDER_Q4K
  unset GGML_SYCL_DISABLE_REORDER_Q6K
fi
if [[ "${feature_profile}" != tuned && "${wdc_q4k}" == 1 ]]; then
  printf 'WDC_Q4K=1 is incompatible with a non-tuned FEATURE_PROFILE\n' >&2
  exit 2
elif [[ "${wdc_q4k}" == 1 ]]; then
  # Default-off candidate: oneDNN consumes the scoped Q4_K reordered layout.
  # GGML_SYCL_WDC remains off because this screen enables only the Q4_K door.
  export GGML_SYCL_WDC_Q4K=1
  if [[ -n "${wdc_q4k_name_filter}" ]]; then
    export GGML_SYCL_WDC_Q4K_NAME_FILTER="${wdc_q4k_name_filter}"
  else
    unset GGML_SYCL_WDC_Q4K_NAME_FILTER
  fi
else
  unset GGML_SYCL_WDC_Q4K GGML_SYCL_WDC_Q4K_NAME_FILTER
fi
if [[ -n "${q4k_f16_cache_filter}" ]]; then
  # Default-off exact-arithmetic candidate: preserve the incumbent Q4_K
  # dequantized F16 bytes on device and feed them to the unchanged GEMM.
  export GGML_SYCL_Q4K_F16_CACHE_FILTER="${q4k_f16_cache_filter}"
else
  unset GGML_SYCL_Q4K_F16_CACHE_FILTER
fi
if [[ "${q4k_dual_gemm}" == 1 ]]; then
  export GGML_SYCL_Q4K_DUAL_GEMM=1
else
  unset GGML_SYCL_Q4K_DUAL_GEMM
fi
if [[ "${f16_act_dedup}" == 1 ]]; then
  export GGML_SYCL_F16_ACT_DEDUP=1
else
  unset GGML_SYCL_F16_ACT_DEDUP
fi
args=(--model "${target_dir}/Qwen3.8-27B-Q4_K_M.gguf")
if [[ "${tp_size}" == 2 ]]; then
  args+=(--device SYCL0,SYCL1 --split-mode tensor --tensor-split 1,1 --gpu-layers 99 --fit off)
else
  args+=(--device SYCL0 --gpu-layers 99 --fit off)
fi
if [[ "${mtp_depth}" == 2 ]]; then
  args+=(
    --model-draft "${draft_dir}/mtp-Qwen3.8-27B-Q4_0.gguf" --device-draft SYCL0 --gpu-layers-draft 99
    --spec-type draft-mtp --spec-draft-n-max 2 --spec-draft-n-min 0 --spec-draft-p-min 0
    --cache-type-k-draft f16 --cache-type-v-draft f16
  )
fi
exec systemd-run --user --scope --quiet --property=MemoryHigh=11G --property=MemoryMax=13G --property=MemorySwapMax=12G \
  "${build_dir}/bin/llama-server" "${args[@]}" \
  --cache-type-k f16 --cache-type-v f16 --flash-attn on \
  --batch-size "${batch_size}" --ubatch-size "${ubatch_size}" --cache-ram 0 --ctx-checkpoints 0 \
  --reasoning off --threads "${threads}" --poll 50 --ctx-size "${ctx_size}" --parallel "${parallel_slots}" \
  --cont-batching --no-cache-prompt --slot-prompt-similarity 0 --metrics --host "${host}" --port "${port}"
