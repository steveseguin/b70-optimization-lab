#!/usr/bin/env bash
set -euo pipefail

# Strict fresh-response candidate wrapper for Qwen3.6 27B vLLM/XPU lanes.
#
# This is intended for source/config/checkpoint screens that might become
# headline candidates. It starts one isolated server at the requested tensor
# parallel size, runs the fixed Qwen
# realistic suite once per prompt with cached_tokens=0 required, optionally runs
# the deterministic Qwen text quality suite, then writes a compact summary.
#
# Diagnostic/synthetic runs should use separate scripts. LocalMaxxing
# submissions require this strict gate plus quality review.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"

# Portable repro packets may restore the two runtime repositories outside the
# original /home/steve/src paths. Keep the historical defaults, but snapshot
# the exact trees selected by the caller.
VLLM_SOURCE_TREE="${VLLM_SOURCE_TREE:-/home/steve/src/vllm}"
VLLM_XPU_KERNELS_SOURCE_TREE="${VLLM_XPU_KERNELS_SOURCE_TREE:-/home/steve/src/vllm-xpu-kernels}"

STAMP="${STAMP:-$(date -u +%Y%m%dT%H%M%SZ)}"
LABEL="${LABEL:-qwen27-candidate}"
GPU_INDEX="${GPU_INDEX:-0}"
TENSOR_PARALLEL_SIZE="${TENSOR_PARALLEL_SIZE:-1}"
PORT="${PORT:-19420}"
HOST="${HOST:-127.0.0.1}"
SERVED_MODEL_NAME="${SERVED_MODEL_NAME:-qwen36-27b-candidate}"
QUALITY_REPEAT_RUNS="${QUALITY_REPEAT_RUNS:-32}"
QUALITY_LONG_CONTEXT_TOKENS="${QUALITY_LONG_CONTEXT_TOKENS:-1024}"
BENCH_MAX_TOKENS="${BENCH_MAX_TOKENS:-512}"
BENCH_METRIC_TOKENS="${BENCH_METRIC_TOKENS:-100}"
SMOKE_MAX_TOKENS="${SMOKE_MAX_TOKENS:-64}"

RUN_ROOT="${RUN_ROOT:-/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/candidates}"
RUN_DIR="${RUN_DIR:-$RUN_ROOT/${LABEL}-${STAMP}}"
OUT_DIR="${OUT_DIR:-$ROOT/data/qwen36-27b-autoround-int4-b70-baselines}"
BENCH_OUT="${BENCH_OUT:-$OUT_DIR/${LABEL}-realistic128-chat-tokenids-qwensuite-${STAMP}.json}"
QUALITY_OUT="${QUALITY_OUT:-$OUT_DIR/quality-${LABEL}-repeat${QUALITY_REPEAT_RUNS}-ctx${QUALITY_LONG_CONTEXT_TOKENS}-${STAMP}.json}"
SMOKE_OUT="${SMOKE_OUT:-$OUT_DIR/smoke-${LABEL}-${STAMP}.json}"
SUMMARY_OUT="${SUMMARY_OUT:-$OUT_DIR/${LABEL}-candidate-summary-${STAMP}.json}"
SUITE="${SUITE:-$ROOT/repro/qwen36-27b-autoround-int4-b70/realistic-suite-v1.json}"
if [[ -z "${REQUEST_EXTRA_JSON:-}" ]]; then
  REQUEST_EXTRA_JSON='{"chat_template_kwargs":{"enable_thinking":false}}'
fi

MODEL_DIR="${MODEL_DIR:-/mnt/fast-ai/llm-cache/hf/hub/models--webhie--Qwen3.6-27B-int4-AutoRound/snapshots/f5750c90b3776db658594df5fe8051098226dd8e}"
if [[ ! -e "$MODEL_DIR" ]]; then
  echo "MODEL_DIR does not exist: $MODEL_DIR" >&2
  exit 2
fi

export MODEL_DIR GPU_INDEX TENSOR_PARALLEL_SIZE PORT HOST SERVED_MODEL_NAME
export QWEN36_27B_AR_VENV="${QWEN36_27B_AR_VENV:-/home/steve/.venvs/vllm-xpu}"
export HF_HOME="${HF_HOME:-/mnt/fast-ai/llm-cache/hf}"
export TRANSFORMERS_CACHE="${TRANSFORMERS_CACHE:-$HF_HOME/transformers}"
export MAX_MODEL_LEN="${MAX_MODEL_LEN:-2048}"
export MAX_NUM_BATCHED_TOKENS="${MAX_NUM_BATCHED_TOKENS:-1024}"
export MAX_NUM_SEQS="${MAX_NUM_SEQS:-1}"
export GPU_MEMORY_UTILIZATION="${GPU_MEMORY_UTILIZATION:-0.95}"
export QWEN36_27B_ENABLE_MTP="${QWEN36_27B_ENABLE_MTP:-1}"
export NUM_SPECULATIVE_TOKENS="${NUM_SPECULATIVE_TOKENS:-3}"
export QWEN36_27B_ENABLE_XPU_GRAPH="${QWEN36_27B_ENABLE_XPU_GRAPH:-1}"
if [[ -z "${COMPILATION_CONFIG:-}" ]]; then
  export COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE","max_cudagraph_capture_size":8}'
else
  export COMPILATION_CONFIG
fi
export VLLM_XPU_GDN_PROMOTE_ACCEPTED_SPEC_STATE="${VLLM_XPU_GDN_PROMOTE_ACCEPTED_SPEC_STATE:-1}"
export VLLM_XPU_GDN_NONSPEC_POSTPROCESS_ACCEPTED_STATE="${VLLM_XPU_GDN_NONSPEC_POSTPROCESS_ACCEPTED_STATE:-0}"
export VLLM_XPU_LM_HEAD_INT8="${VLLM_XPU_LM_HEAD_INT8:-1}"
export VLLM_XPU_LM_HEAD_INT8_SCALE_DTYPE="${VLLM_XPU_LM_HEAD_INT8_SCALE_DTYPE:-bf16}"
export QWEN36_27B_DEFAULT_ENABLE_THINKING="${QWEN36_27B_DEFAULT_ENABLE_THINKING:-0}"
export QWEN36_27B_ENABLE_PROMPT_TOKEN_DETAILS="${QWEN36_27B_ENABLE_PROMPT_TOKEN_DETAILS:-1}"

PYTHON="${PYTHON:-$QWEN36_27B_AR_VENV/bin/python}"
READINESS_TIMEOUT_S="${READINESS_TIMEOUT_S:-900}"
RUN_SMOKE="${RUN_SMOKE:-1}"
RUN_BENCH="${RUN_BENCH:-1}"
RUN_QUALITY="${RUN_QUALITY:-1}"
QUALITY_SKIP_LONG_CONTEXT="${QUALITY_SKIP_LONG_CONTEXT:-0}"
QUALITY_BASELINE_JSON="${QUALITY_BASELINE_JSON:-}"
QUALITY_REQUEST_ID_PREFIX="${QUALITY_REQUEST_ID_PREFIX:-${LABEL}-${STAMP}}"

mkdir -p "$RUN_DIR" "$OUT_DIR"

# Preserve the exact dirty runtime source state for every endpoint candidate.
# The active vLLM/XPU trees intentionally carry a composite experiment stack,
# so a base commit alone is not enough to reproduce a result.
snapshot_git_tree() {
  local tree="$1"
  local name="$2"
  git -C "$tree" rev-parse HEAD > "$RUN_DIR/${name}.git-head"
  git -C "$tree" status --short --branch > "$RUN_DIR/${name}.git-status"
  git -C "$tree" diff --binary > "$RUN_DIR/${name}.working.patch"
}

snapshot_git_tree "$ROOT" "llm-optimizations"
snapshot_git_tree "$VLLM_SOURCE_TREE" "vllm"
snapshot_git_tree "$VLLM_XPU_KERNELS_SOURCE_TREE" "vllm-xpu-kernels"
find "$VLLM_XPU_KERNELS_SOURCE_TREE/vllm_xpu_kernels" \
  -maxdepth 1 -type f -name '*.so' -print0 \
  | sort -z \
  | xargs -0 -r sha256sum > "$RUN_DIR/xpu-runtime-binaries.sha256"
if [[ -n "${VLLM_XPU_KERNELS_SRC:-}" \
  && "$VLLM_XPU_KERNELS_SRC" != "$VLLM_XPU_KERNELS_SOURCE_TREE" ]]; then
  find "$VLLM_XPU_KERNELS_SRC" -maxdepth 2 \
    \( -type f -o -type l \) \( -name '*.so' -o -name '*.so.*' \) -print0 \
    | sort -z \
    | xargs -0 -r sha256sum > "$RUN_DIR/xpu-staged-runtime-binaries.sha256"
fi
if [[ -n "${SERVER_LD_PRELOAD:-}" ]]; then
  : > "$RUN_DIR/server-ld-preload.sha256"
  IFS=: read -r -a server_preloads <<< "$SERVER_LD_PRELOAD"
  for preload in "${server_preloads[@]}"; do
    if [[ ! -f "$preload" ]]; then
      echo "SERVER_LD_PRELOAD entry is not a regular file: $preload" >&2
      exit 2
    fi
    sha256sum "$preload" >> "$RUN_DIR/server-ld-preload.sha256"
  done
fi
cp "$0" "$RUN_DIR/$(basename "$0").snapshot"
if [[ -n "${CANDIDATE_ENTRYPOINT:-}" && -f "$CANDIDATE_ENTRYPOINT" ]]; then
  cp "$CANDIDATE_ENTRYPOINT" \
    "$RUN_DIR/$(basename "$CANDIDATE_ENTRYPOINT").snapshot"
fi
cp experiments/qwen36-27b-autoround-int4-b70/scripts/serve-vllm.sh \
  "$RUN_DIR/serve-vllm.sh.snapshot"

server_pid=""
cleanup() {
  if [[ -n "${server_pid:-}" ]] && kill -0 "$server_pid" 2>/dev/null; then
    kill "$server_pid" 2>/dev/null || true
    wait "$server_pid" 2>/dev/null || true
  fi
}
trap cleanup EXIT

{
  echo "date_utc=$STAMP"
  echo "label=$LABEL"
  echo "candidate_entrypoint=${CANDIDATE_ENTRYPOINT:-$0}"
  echo "run_dir=$RUN_DIR"
  echo "model_dir=$MODEL_DIR"
  echo "served_model_name=$SERVED_MODEL_NAME"
  echo "gpu_index=$GPU_INDEX"
  echo "tensor_parallel_size=$TENSOR_PARALLEL_SIZE"
  echo "port=$PORT"
  echo "hf_home=$HF_HOME"
  echo "vllm_cache_root=${VLLM_CACHE_ROOT:-}"
  echo "torchinductor_cache_dir=${TORCHINDUCTOR_CACHE_DIR:-}"
  echo "max_model_len=$MAX_MODEL_LEN"
  echo "max_num_batched_tokens=$MAX_NUM_BATCHED_TOKENS"
  echo "max_num_seqs=$MAX_NUM_SEQS"
  echo "gpu_memory_utilization=$GPU_MEMORY_UTILIZATION"
  echo "vllm_target_device=${VLLM_TARGET_DEVICE:-xpu}"
  echo "xpu_kernels_src=${VLLM_XPU_KERNELS_SRC:-/home/steve/src/vllm-xpu-kernels}"
  echo "enable_mtp=$QWEN36_27B_ENABLE_MTP"
  echo "num_speculative_tokens=$NUM_SPECULATIVE_TOKENS"
  echo "enable_xpu_graph=$QWEN36_27B_ENABLE_XPU_GRAPH"
  echo "compilation_config=$COMPILATION_CONFIG"
  echo "batch_invariant=${VLLM_BATCH_INVARIANT:-0}"
  echo "promote_accepted_spec_state=$VLLM_XPU_GDN_PROMOTE_ACCEPTED_SPEC_STATE"
  echo "nonspec_postprocess_accepted_state=$VLLM_XPU_GDN_NONSPEC_POSTPROCESS_ACCEPTED_STATE"
  echo "gdn_packed_decode_with_source=${VLLM_XPU_GDN_PACKED_DECODE_WITH_SOURCE:-}"
  echo "draft_lm_head_int4=${VLLM_XPU_DRAFT_LM_HEAD_INT4:-}"
  echo "draft_lm_head_int4_group_size=${VLLM_XPU_DRAFT_LM_HEAD_INT4_GROUP_SIZE:-}"
  echo "draft_lm_head_int4_scale_dtype=${VLLM_XPU_DRAFT_LM_HEAD_INT4_SCALE_DTYPE:-}"
  echo "gdn_serial_spec_decode=${VLLM_XPU_GDN_SERIAL_SPEC_DECODE:-}"
  echo "gdn_serial_spec_conv=${VLLM_XPU_GDN_SERIAL_SPEC_CONV:-}"
  echo "gdn_serial_spec_packed_decode=${VLLM_XPU_GDN_SERIAL_SPEC_PACKED_DECODE:-}"
  echo "gdn_serial_spec_skip_draft_state=${VLLM_XPU_GDN_SERIAL_SPEC_SKIP_DRAFT_STATE:-}"
  echo "gdn_serial_spec_single_state_slot=${VLLM_XPU_GDN_SERIAL_SPEC_SINGLE_STATE_SLOT:-}"
  echo "gdn_serial_spec_source_offset_zero=${VLLM_XPU_GDN_SERIAL_SPEC_SOURCE_OFFSET_ZERO:-}"
  echo "gdn_spec_promote_running_after_spec=${VLLM_XPU_GDN_SPEC_PROMOTE_RUNNING_AFTER_SPEC:-}"
  echo "gdn_spec_promote_running_offset_plus_one=${VLLM_XPU_GDN_SPEC_PROMOTE_RUNNING_OFFSET_PLUS_ONE:-}"
  echo "gdn_native_spec_decode=${VLLM_XPU_GDN_NATIVE_SPEC_DECODE:-}"
  echo "gdn_native_spec_prefix_base_state=${VLLM_XPU_GDN_NATIVE_SPEC_PREFIX_BASE_STATE:-}"
  echo "gdn_native_spec_replacement_prefix_state_counts=${VLLM_XPU_GDN_NATIVE_SPEC_REPLACEMENT_PREFIX_STATE_COUNTS:-}"
  echo "gdn_native_spec_decode_serial=${VLLM_XPU_GDN_NATIVE_SPEC_DECODE_SERIAL:-}"
  echo "gdn_native_spec_recurrent_serial_exact=${VLLM_XPU_GDN_NATIVE_SPEC_RECURRENT_SERIAL_EXACT:-}"
  echo "gdn_disable_spec_static_graph_metadata=${VLLM_XPU_GDN_DISABLE_SPEC_STATIC_GRAPH_METADATA:-}"
  echo "gdn_native_spec_prefill_sequence=${VLLM_XPU_GDN_NATIVE_SPEC_PREFILL_SEQUENCE:-}"
  echo "gdn_native_spec_prefill_output_decode_state=${VLLM_XPU_GDN_NATIVE_SPEC_PREFILL_OUTPUT_DECODE_STATE:-}"
  echo "gdn_native_spec_prefill_output_replay_columns=${VLLM_XPU_GDN_NATIVE_SPEC_PREFILL_OUTPUT_REPLAY_COLUMNS:-}"
  echo "gdn_native_spec_prefill_output_replay_prefixes=${VLLM_XPU_GDN_NATIVE_SPEC_PREFILL_OUTPUT_REPLAY_PREFIXES:-}"
  echo "gdn_native_spec_prefill_replay_partial_prefix=${VLLM_XPU_GDN_NATIVE_SPEC_PREFILL_REPLAY_PARTIAL_PREFIX:-}"
  echo "gdn_native_spec_prefill_replay_exact_serial_state=${VLLM_XPU_GDN_NATIVE_SPEC_PREFILL_REPLAY_EXACT_SERIAL_STATE:-}"
  echo "gdn_native_spec_prefill_exact_state_offset_plus_one=${VLLM_XPU_GDN_NATIVE_SPEC_PREFILL_EXACT_STATE_OFFSET_PLUS_ONE:-}"
  echo "gdn_native_spec_prefill_backup_state_column=${VLLM_XPU_GDN_NATIVE_SPEC_PREFILL_BACKUP_STATE_COLUMN:-}"
  echo "gdn_native_spec_prefill_prepromote=${VLLM_XPU_GDN_NATIVE_SPEC_PREFILL_PREPROMOTE:-}"
  echo "gdn_native_spec_skip_final_promote=${VLLM_XPU_GDN_NATIVE_SPEC_SKIP_FINAL_PROMOTE:-}"
  echo "gdn_native_spec_prefill_exact_replay_native_decode=${VLLM_XPU_GDN_NATIVE_SPEC_PREFILL_EXACT_REPLAY_NATIVE_DECODE:-}"
  echo "gdn_native_spec_prefill_exact_replay_write_outputs=${VLLM_XPU_GDN_NATIVE_SPEC_PREFILL_EXACT_REPLAY_WRITE_OUTPUTS:-}"
  echo "gdn_native_fallback=${VLLM_XPU_GDN_NATIVE_FALLBACK:-}"
  echo "gdn_replayssm_spec=${VLLM_XPU_GDN_REPLAYSSM_SPEC:-}"
  echo "gdn_replayssm_spec_cache_len=${VLLM_XPU_GDN_REPLAYSSM_SPEC_CACHE_LEN:-}"
  echo "gdn_replayssm_torch_fallback=${VLLM_XPU_GDN_REPLAYSSM_TORCH_FALLBACK:-}"
  echo "gdn_replayssm_stage_conv_torch_fallback=${VLLM_XPU_GDN_REPLAYSSM_STAGE_CONV_TORCH_FALLBACK:-}"
  echo "gdn_replayssm_commit_in_forward=${VLLM_XPU_GDN_REPLAYSSM_COMMIT_IN_FORWARD:-}"
  echo "gdn_replayssm_fuse_commit_stage=${VLLM_XPU_GDN_REPLAYSSM_FUSE_COMMIT_STAGE:-}"
  echo "gdn_replayssm_slot_mgmt_torch_fallback=${VLLM_XPU_GDN_REPLAYSSM_SLOT_MGMT_TORCH_FALLBACK:-}"
  echo "draft_disable_cudagraphs=${VLLM_XPU_DRAFT_DISABLE_CUDAGRAPHS:-}"
  echo "disable_spec_decode_cudagraph_replay=${VLLM_XPU_DISABLE_SPEC_DECODE_CUDAGRAPH_REPLAY:-}"
  echo "skip_compiled_spec_decode=${VLLM_XPU_SKIP_COMPILED_SPEC_DECODE:-}"
  echo "spec_decode_verify_trace_file=${VLLM_XPU_SPEC_DECODE_VERIFY_TRACE_FILE:-}"
  echo "spec_decode_verify_trace_max_lines=${VLLM_XPU_SPEC_DECODE_VERIFY_TRACE_MAX_LINES:-}"
  echo "spec_decode_verify_trace_topk=${VLLM_XPU_SPEC_DECODE_VERIFY_TRACE_TOPK:-}"
  echo "spec_decode_bonus_logit_trace_file=${VLLM_XPU_SPEC_DECODE_BONUS_LOGIT_TRACE_FILE:-}"
  echo "spec_decode_bonus_logit_trace_max_lines=${VLLM_XPU_SPEC_DECODE_BONUS_LOGIT_TRACE_MAX_LINES:-}"
  echo "gdn_metadata_trace_file=${VLLM_XPU_GDN_METADATA_TRACE_FILE:-}"
  echo "gdn_metadata_trace_max_lines=${VLLM_XPU_GDN_METADATA_TRACE_MAX_LINES:-}"
  echo "gdn_metadata_trace_rank=${VLLM_XPU_GDN_METADATA_TRACE_RANK:-}"
  echo "model_input_trace_file=${VLLM_XPU_MODEL_INPUT_TRACE_FILE:-}"
  echo "model_input_trace_max_lines=${VLLM_XPU_MODEL_INPUT_TRACE_MAX_LINES:-}"
  echo "model_input_trace_rank=${VLLM_XPU_MODEL_INPUT_TRACE_RANK:-}"
  echo "fa_serial_spec_mode=${VLLM_XPU_FA_SERIAL_SPEC_MODE:-}"
  echo "fa_batch_invariant=${VLLM_XPU_FA_BATCH_INVARIANT:-0}"
  echo "fa_sync_after_packed=${VLLM_XPU_FA_SYNC_AFTER_PACKED:-0}"
  echo "qwen_sync_after_full_attn_o_proj=${VLLM_XPU_QWEN_SYNC_AFTER_FULL_ATTN_O_PROJ:-0}"
  echo "qwen_sync_after_full_attn_o_proj_layers=${VLLM_XPU_QWEN_SYNC_AFTER_FULL_ATTN_O_PROJ_LAYERS:-}"
  echo "sync_row_parallel_after_gemm_prefix=${VLLM_XPU_SYNC_ROW_PARALLEL_AFTER_GEMM_PREFIX:-}"
  echo "onednn_int4_completion_barrier=${VLLM_XPU_ONEDNN_INT4_COMPLETION_BARRIER:-0}"
  echo "onednn_int4_input_dependency=${VLLM_XPU_ONEDNN_INT4_INPUT_DEPENDENCY:-0}"
  echo "onednn_int4_input_dependency_scope=${VLLM_XPU_ONEDNN_INT4_INPUT_DEPENDENCY_SCOPE:-}"
  echo "m4_m1_oracle_file=${VLLM_XPU_M4_M1_ORACLE_FILE:-}"
  echo "m4_m1_oracle_forward=${VLLM_XPU_M4_M1_ORACLE_FORWARD:-}"
  echo "m4_m1_oracle_components=${VLLM_XPU_M4_M1_ORACLE_COMPONENTS:-}"
  echo "int4_gemm_fixed_m4=${VLLM_XPU_INT4_GEMM_FIXED_M4:-0}"
  echo "int8_lm_head_fixed_m4=${VLLM_XPU_INT8_LM_HEAD_FIXED_M4:-0}"
  echo "onednn_int8_completion_barrier=${VLLM_XPU_ONEDNN_INT8_COMPLETION_BARRIER:-0}"
  echo "sync_after_cudagraph_warmup=${VLLM_XPU_SYNC_AFTER_CUDAGRAPH_WARMUP:-0}"
  echo "sync_after_model_forward=${VLLM_XPU_SYNC_AFTER_MODEL_FORWARD:-0}"
  echo "qwen_gemma_rmsnorm_batch_invariant=${VLLM_XPU_QWEN_GEMMA_RMSNORM_BATCH_INVARIANT:-}"
  echo "qwen_gemma_rmsnorm_serial_m4=${VLLM_XPU_QWEN_GEMMA_RMSNORM_SERIAL_M4:-0}"
  echo "qwen_gemma_rmsnorm_sycl=${VLLM_XPU_QWEN_GEMMA_RMSNORM_SYCL:-0}"
  echo "qwen_device_barrier_after_input_norm=${VLLM_XPU_QWEN_DEVICE_BARRIER_AFTER_INPUT_NORM:-0}"
  echo "qwen_device_barrier_after_input_norm_layers=${VLLM_XPU_QWEN_DEVICE_BARRIER_AFTER_INPUT_NORM_LAYERS:-}"
  echo "split_qwen_gemma_rmsnorm_sycl=${VLLM_XPU_SPLIT_QWEN_GEMMA_RMSNORM_SYCL:-0}"
  echo "gdn_native_spec_metadata_snapshot=${VLLM_XPU_GDN_NATIVE_SPEC_METADATA_SNAPSHOT:-}"
  echo "gdn_native_spec_completion_barrier=${VLLM_XPU_GDN_NATIVE_SPEC_COMPLETION_BARRIER:-0}"
  echo "gdn_capture_native_spec=${VLLM_XPU_GDN_CAPTURE_NATIVE_SPEC:-0}"
  echo "gdn_trace_conv_publish_once=${VLLM_XPU_GDN_TRACE_CONV_PUBLISH_ONCE:-}"
  echo "qwen_layer_trace_file=${VLLM_XPU_QWEN_LAYER_TRACE_FILE:-}"
  echo "qwen_layer_trace_layers=${VLLM_XPU_QWEN_LAYER_TRACE_LAYERS:-}"
  echo "qwen_layer_trace_stages=${VLLM_XPU_QWEN_LAYER_TRACE_STAGES:-}"
  echo "qwen_layer_trace_row_indices=${VLLM_XPU_QWEN_LAYER_TRACE_ROW_INDICES:-}"
  echo "qwen_layer_trace_pos_min=${VLLM_XPU_QWEN_LAYER_TRACE_POS_MIN:-}"
  echo "qwen_layer_trace_pos_max=${VLLM_XPU_QWEN_LAYER_TRACE_POS_MAX:-}"
  echo "gdn_row_trace_file=${VLLM_XPU_GDN_ROW_TRACE_FILE:-}"
  echo "gdn_row_trace_layers=${VLLM_XPU_GDN_ROW_TRACE_LAYERS:-}"
  echo "gdn_row_trace_stages=${VLLM_XPU_GDN_ROW_TRACE_STAGES:-}"
  echo "gdn_trace_file=${VLLM_XPU_GDN_TRACE_FILE:-}"
  echo "gdn_trace_layer_regex=${VLLM_XPU_GDN_TRACE_LAYER_REGEX:-}"
  echo "xpu_compile_allreduce_custom_op=${VLLM_XPU_COMPILE_ALLREDUCE_CUSTOM_OP:-}"
  echo "xpu_compile_allgather_custom_op=${VLLM_XPU_COMPILE_ALLGATHER_CUSTOM_OP:-}"
  echo "xpu_compile_allreduce_static_inplace=${VLLM_XPU_COMPILE_ALLREDUCE_STATIC_INPLACE:-}"
  echo "xpu_custom_allreduce_clone_input=${VLLM_XPU_CUSTOM_ALLREDUCE_CLONE_INPUT:-}"
  echo "xpu_custom_allreduce_graph_clone_input=${VLLM_XPU_CUSTOM_ALLREDUCE_GRAPH_CLONE_INPUT:-}"
  echo "xpu_custom_allreduce_inplace_max_numel=${VLLM_XPU_CUSTOM_ALLREDUCE_INPLACE_MAX_NUMEL:-}"
  echo "xpu_custom_allreduce_tiny_fp32_inplace_max_numel=${VLLM_XPU_CUSTOM_ALLREDUCE_TINY_FP32_INPLACE_MAX_NUMEL:-}"
  echo "xpu_compile_allreduce_no_clone=${VLLM_XPU_COMPILE_ALLREDUCE_NO_CLONE:-}"
  echo "ccl_enable_sycl_kernels=${CCL_ENABLE_SYCL_KERNELS:-}"
  echo "ccl_sycl_esimd=${CCL_SYCL_ESIMD:-}"
  echo "ccl_sycl_allreduce_tmp_buf=${CCL_SYCL_ALLREDUCE_TMP_BUF:-}"
  echo "ccl_sycl_allreduce_small_threshold=${CCL_SYCL_ALLREDUCE_SMALL_THRESHOLD:-}"
  echo "ccl_atl_transport=${CCL_ATL_TRANSPORT:-}"
  echo "ccl_topo_p2p_access=${CCL_TOPO_P2P_ACCESS:-}"
  echo "ccl_ze_ipc_exchange=${CCL_ZE_IPC_EXCHANGE:-}"
  echo "ccl_kernel_path=${CCL_KERNEL_PATH:-}"
  echo "oneccl_candidate_path=${ONECCL_CANDIDATE_PATH:-}"
  echo "oneccl_candidate_sha256=${ONECCL_CANDIDATE_SHA256:-}"
  echo "oneccl_kernels_sha256=${ONECCL_KERNELS_SHA256:-}"
  echo "oneccl_source_top_commit=${ONECCL_SOURCE_TOP_COMMIT:-}"
  echo "oneccl_libccl_commit=${ONECCL_LIBCCL_COMMIT:-}"
  echo "server_ld_preload=${SERVER_LD_PRELOAD:-}"
  echo "server_ld_library_path=${SERVER_LD_LIBRARY_PATH:-}"
  echo "server_ccl_kernel_path=${SERVER_CCL_KERNEL_PATH:-}"
  echo "ld_preload=${LD_PRELOAD:-}"
  echo "ld_library_path=${LD_LIBRARY_PATH:-}"
  echo "gdn_replayssm_fuse_pending_metadata=${VLLM_XPU_GDN_REPLAYSSM_FUSE_PENDING_METADATA:-}"
  echo "gdn_replayssm_direct_core_out=${VLLM_XPU_GDN_REPLAYSSM_DIRECT_CORE_OUT:-}"
  echo "gdn_accepted_prefix_counts=${VLLM_XPU_GDN_ACCEPTED_PREFIX_COUNTS:-}"
  echo "enable_fla_packed_recurrent_decode=${VLLM_ENABLE_FLA_PACKED_RECURRENT_DECODE:-}"
  echo "gdn_spec_state_offset_plus_one=${VLLM_XPU_GDN_SPEC_STATE_OFFSET_PLUS_ONE:-}"
  echo "gdn_spec_promote_conv_state=${VLLM_XPU_GDN_SPEC_PROMOTE_CONV_STATE:-}"
  echo "gdn_native_promote_conv_state=${VLLM_XPU_GDN_NATIVE_PROMOTE_CONV_STATE:-}"
  echo "spec_restore_partial_reject_gdn_state=${VLLM_XPU_SPEC_DECODE_RESTORE_DRAFT_PARTIAL_REJECT_GDN_STATE:-}"
  echo "spec_restore_full_accept_gdn_state=${VLLM_XPU_SPEC_DECODE_RESTORE_DRAFT_FULL_ACCEPT_GDN_STATE:-}"
  echo "spec_suppress_replacement=${VLLM_XPU_SPEC_DECODE_SUPPRESS_REPLACEMENT:-}"
  echo "spec_recover_suppressed_replacement=${VLLM_XPU_SPEC_DECODE_RECOVER_SUPPRESSED_REPLACEMENT:-}"
  echo "spec_no_preempt_suppressed_replacement=${VLLM_XPU_SPEC_DECODE_NO_PREEMPT_SUPPRESSED_REPLACEMENT:-}"
  echo "spec_replay_suppressed_replacement_accepted=${VLLM_XPU_SPEC_DECODE_REPLAY_SUPPRESSED_REPLACEMENT_ACCEPTED:-}"
  echo "spec_replay_suppressed_replacement_preempt=${VLLM_XPU_SPEC_DECODE_REPLAY_SUPPRESSED_REPLACEMENT_PREEMPT:-}"
  echo "spec_replay_suppressed_replacement_extra_steps=${VLLM_XPU_SPEC_DECODE_REPLAY_SUPPRESSED_REPLACEMENT_EXTRA_STEPS:-}"
  echo "spec_eager_replacement_recovery=${VLLM_XPU_SPEC_DECODE_EAGER_REPLACEMENT_RECOVERY:-}"
  echo "spec_restore_replayed_gdn_state=${VLLM_XPU_SPEC_DECODE_RESTORE_REPLAYED_GDN_STATE:-}"
  echo "spec_eager_all_recovery_steps=${VLLM_XPU_SPEC_DECODE_EAGER_ALL_RECOVERY_STEPS:-}"
  echo "spec_filter_suppressed_bonus_next_input=${VLLM_XPU_SPEC_DECODE_FILTER_SUPPRESSED_BONUS_NEXT_INPUT:-}"
  echo "spec_skip_replayed_mamba_postprocess=${VLLM_XPU_SPEC_DECODE_SKIP_REPLAYED_MAMBA_POSTPROCESS:-}"
  echo "spec_keep_placeholder_replacement_suppression=${VLLM_XPU_SPEC_DECODE_KEEP_PLACEHOLDER_REPLACEMENT_SUPPRESSION:-}"
  echo "spec_force_eager=${VLLM_XPU_SPEC_DECODE_FORCE_EAGER:-}"
  echo "xpu_spec_decode_draft_only=${VLLM_XPU_SPEC_DECODE_DRAFT_ONLY:-}"
  echo "xpu_spec_decode_draft_only_accept_min_margin=${VLLM_XPU_SPEC_DECODE_DRAFT_ONLY_ACCEPT_MIN_MARGIN:-}"
  echo "xpu_spec_decode_accept_min_margin=${VLLM_XPU_SPEC_DECODE_ACCEPT_MIN_MARGIN:-}"
  echo "xpu_spec_decode_replacement_min_margin=${VLLM_XPU_SPEC_DECODE_REPLACEMENT_MIN_MARGIN:-}"
  echo "xpu_spec_decode_bonus_min_margin=${VLLM_XPU_SPEC_DECODE_BONUS_MIN_MARGIN:-}"
  echo "xpu_spec_decode_recover_suppressed_replacement=${VLLM_XPU_SPEC_DECODE_RECOVER_SUPPRESSED_REPLACEMENT:-}"
  echo "lm_head_int8=$VLLM_XPU_LM_HEAD_INT8"
  echo "lm_head_int8_scale_dtype=$VLLM_XPU_LM_HEAD_INT8_SCALE_DTYPE"
  echo "lm_head_int8_serial_m1=${VLLM_XPU_LM_HEAD_INT8_SERIAL_M1:-0}"
  echo "gdn_ba_serial_m1=${VLLM_XPU_GDN_BA_SERIAL_M1:-0}"
  echo "mtp_text_input_ids_next=${VLLM_XPU_MTP_TEXT_INPUT_IDS_NEXT:-}"
  echo "mtp_next_dispatch_trace_file=${VLLM_XPU_MTP_NEXT_DISPATCH_TRACE_FILE:-}"
  echo "disable_compile_cache=${VLLM_DISABLE_COMPILE_CACHE:-}"
  echo "request_extra_json=$REQUEST_EXTRA_JSON"
  echo "qwen36_27b_speculative_config=${QWEN36_27B_SPECULATIVE_CONFIG:-}"
  echo "dflash_ddtree_budget=${VLLM_XPU_DFLASH_DDTREE_BUDGET:-}"
  echo "ddtree_native_kv_copy=${VLLM_XPU_DDTREE_NATIVE_KV_COPY:-}"
  echo "ddtree_native_tree_attn=${VLLM_XPU_DDTREE_NATIVE_TREE_ATTN:-}"
  echo "tree_attn_bool_sdpa=${VLLM_XPU_TREE_ATTN_BOOL_SDPA:-}"
  echo "ddtree_capture_gdn_core=${VLLM_XPU_DDTREE_CAPTURE_GDN_CORE:-}"
  echo "ddtree_full_graph=${VLLM_XPU_DDTREE_FULL_GRAPH:-}"
  echo "qwen3_dflash_layer_types=${VLLM_XPU_QWEN3_DFLASH_LAYER_TYPES:-}"
  echo "dflash_runtime_int8=${VLLM_XPU_DFLASH_RUNTIME_INT8:-}"
  echo "decode_timing=${VLLM_XPU_DECODE_TIMING:-}"
  echo "decode_timing_sync=${VLLM_XPU_DECODE_TIMING_SYNC:-}"
  echo "decode_timing_label_regex=${VLLM_XPU_DECODE_TIMING_LABEL_REGEX:-}"
  echo "decode_timing_sync_label_regex=${VLLM_XPU_DECODE_TIMING_SYNC_LABEL_REGEX:-}"
  echo "quality_repeat_runs=$QUALITY_REPEAT_RUNS"
  echo "run_smoke=$RUN_SMOKE"
  echo "run_bench=$RUN_BENCH"
  echo "run_quality=$RUN_QUALITY"
  echo "quality_request_id_prefix=$QUALITY_REQUEST_ID_PREFIX"
  echo "quality_long_context_tokens=$QUALITY_LONG_CONTEXT_TOKENS"
  echo "bench_max_tokens=$BENCH_MAX_TOKENS"
  echo "bench_metric_tokens=$BENCH_METRIC_TOKENS"
  echo "smoke_max_tokens=$SMOKE_MAX_TOKENS"
  echo "quality_baseline_json=$QUALITY_BASELINE_JSON"
  echo "vllm_extra_args=${VLLM_EXTRA_ARGS:-}"
} > "$RUN_DIR/identity.env"

(
  if [[ -n "${SERVER_LD_PRELOAD:-}" ]]; then
    export LD_PRELOAD="$SERVER_LD_PRELOAD"
  fi
  if [[ -n "${SERVER_LD_LIBRARY_PATH:-}" ]]; then
    export LD_LIBRARY_PATH="$SERVER_LD_LIBRARY_PATH"
  fi
  if [[ -n "${SERVER_CCL_KERNEL_PATH:-}" ]]; then
    export CCL_KERNEL_PATH="$SERVER_CCL_KERNEL_PATH"
  fi
  exec experiments/qwen36-27b-autoround-int4-b70/scripts/serve-vllm.sh
) > "$RUN_DIR/server.stdout.log" 2>&1 &
server_pid=$!
echo "$server_pid" > "$RUN_DIR/server.pid"

deadline=$((SECONDS + READINESS_TIMEOUT_S))
until curl -fsS "http://127.0.0.1:${PORT}/v1/models" \
  > "$RUN_DIR/models.json" 2> "$RUN_DIR/models.err"; do
  if ! kill -0 "$server_pid" 2>/dev/null; then
    echo "server exited before readiness; see $RUN_DIR/server.stdout.log" >&2
    break
  fi
  if (( SECONDS >= deadline )); then
    echo "timed out waiting for http://127.0.0.1:${PORT}/v1/models" >&2
    break
  fi
  sleep 2
done

smoke_rc=0
bench_rc=0
quality_rc=0

if kill -0 "$server_pid" 2>/dev/null && [[ -s "$RUN_DIR/models.json" ]]; then
  set +e
  if [[ "$RUN_SMOKE" != "0" ]]; then
    BASE_URL="http://127.0.0.1:${PORT}/v1" \
      MODEL="$SERVED_MODEL_NAME" \
      ENABLE_THINKING=0 \
      MAX_TOKENS="$SMOKE_MAX_TOKENS" \
      OUT="$SMOKE_OUT" \
      experiments/qwen36-27b-autoround-int4-b70/scripts/smoke-openai.sh \
      > "$RUN_DIR/smoke.stdout.log" 2>&1
    smoke_rc=$?
  fi

  if [[ "$RUN_BENCH" != "0" ]]; then
    "$PYTHON" scripts/bench-openai-realistic-suite.py \
      --base-url "http://127.0.0.1:${PORT}" \
      --model "$SERVED_MODEL_NAME" \
      --api-mode chat \
      --suite "$SUITE" \
      --max-tokens "$BENCH_MAX_TOKENS" \
      --metric-tokens "$BENCH_METRIC_TOKENS" \
      --seed 1 \
      --request-extra-json "$REQUEST_EXTRA_JSON" \
      --return-token-ids \
      --out "$BENCH_OUT" \
      > "$RUN_DIR/bench.stdout.log" 2>&1
    bench_rc=$?
  fi

  if [[ "$RUN_QUALITY" != "0" ]]; then
    quality_args=(
      "$PYTHON" scripts/qwen36-text-quality-suite.py
      --base-url "http://127.0.0.1:${PORT}"
      --model "$SERVED_MODEL_NAME"
      --tokenizer "$MODEL_DIR"
      --repeat-runs "$QUALITY_REPEAT_RUNS"
      --long-context-tokens "$QUALITY_LONG_CONTEXT_TOKENS"
      --chat-template-kwargs-json '{"enable_thinking": false}'
      --request-id-prefix "$QUALITY_REQUEST_ID_PREFIX"
      --output-json "$QUALITY_OUT"
    )
    if [[ "$QUALITY_SKIP_LONG_CONTEXT" != "0" ]]; then
      quality_args+=(--skip-long-context)
    fi
    if [[ -n "$QUALITY_BASELINE_JSON" ]]; then
      quality_args+=(--baseline-json "$QUALITY_BASELINE_JSON")
    fi
    "${quality_args[@]}" > "$RUN_DIR/quality.stdout.log" 2>&1
    quality_rc=$?
  fi
  set -e
fi

"$PYTHON" - "$SUMMARY_OUT" "$LABEL" "$RUN_DIR" "$MODEL_DIR" "$SMOKE_OUT" \
  "$BENCH_OUT" "$QUALITY_OUT" "$smoke_rc" "$bench_rc" "$quality_rc" \
  "$RUN_SMOKE" "$RUN_BENCH" "$RUN_QUALITY" <<'PY'
import json
import sys
from pathlib import Path

summary_out = Path(sys.argv[1])
label = sys.argv[2]
run_dir = Path(sys.argv[3])
model_dir = sys.argv[4]
smoke_path = Path(sys.argv[5])
bench_path = Path(sys.argv[6])
quality_path = Path(sys.argv[7])
smoke_rc = int(sys.argv[8])
bench_rc = int(sys.argv[9])
quality_rc = int(sys.argv[10])
run_smoke = sys.argv[11] != "0"
run_bench = sys.argv[12] != "0"
run_quality = sys.argv[13] != "0"

def read_json(path: Path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception as exc:
        return {"error": repr(exc), "path": str(path)}

smoke = read_json(smoke_path)
bench = read_json(bench_path)
quality = read_json(quality_path)
gate = (bench or {}).get("realistic_final_gate") or {}
fresh = (bench or {}).get("fresh_response_validity") or {}
bench_summary = (bench or {}).get("summary") or {}
speed = (bench_summary.get("tok_s_1_100_after_ttft") or {})
quality_pass = None
quality_baseline_match = None
if quality is not None:
    quality_pass = quality.get("pass_all")
    quality_baseline_match = quality.get("baseline_match_all")

status = {
    "smoke_skipped": not run_smoke,
    "bench_skipped": not run_bench,
    "quality_skipped": not run_quality,
    "smoke_rc": smoke_rc,
    "bench_rc": bench_rc,
    "quality_rc": quality_rc,
    "smoke_pass": (smoke or {}).get("pass"),
    "realistic_gate_passed": gate.get("passed"),
    "fresh_response_valid": fresh.get("valid"),
    "cached_tokens_all_zero": gate.get("cached_tokens_all_zero"),
    "quality_pass_all": quality_pass,
    "quality_baseline_match_all": quality_baseline_match,
}
out = {
    "classification": (
        "strict_fresh_qwen27_candidate_summary"
        if run_bench
        else "diagnostic_qwen27_quality_only_summary"
    ),
    "label": label,
    "model_dir": model_dir,
    "run_dir": str(run_dir),
    "artifacts": {
        "identity": str(run_dir / "identity.env"),
        "server_log": str(run_dir / "server.stdout.log"),
        "models_json": str(run_dir / "models.json"),
        "smoke": str(smoke_path) if smoke_path.exists() else None,
        "bench": str(bench_path) if bench_path.exists() else None,
        "quality": str(quality_path) if quality_path.exists() else None,
    },
    "status": status,
    "primary_metric": {
        "median_tok_s_1_100_after_ttft": speed.get("median"),
        "p10": speed.get("p10"),
        "mean": speed.get("mean"),
        "count": speed.get("count"),
    },
    "ttft_ms": (bench_summary.get("ttft_ms") or {}),
    "fresh_response_validity": fresh,
    "realistic_final_gate": gate,
    "quality_summary": (
        None if quality is None else {
            "pass_all": quality.get("pass_all"),
            "baseline_match_all": quality.get("baseline_match_all"),
            "exact": {item.get("name"): item.get("pass")
                      for item in quality.get("exact_cases", [])},
            "repeat_pass": (quality.get("repeat_case") or {}).get("pass"),
            "long_context_pass": (
                None if quality.get("long_context_case") is None
                else (quality.get("long_context_case") or {}).get("pass")
            ),
        }
    ),
}
summary_out.parent.mkdir(parents=True, exist_ok=True)
summary_out.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
print(json.dumps(out, indent=2, sort_keys=True))
PY

cp "$SUMMARY_OUT" "$RUN_DIR/summary.json" 2>/dev/null || true

echo "$SUMMARY_OUT"
if [[ "$smoke_rc" -ne 0 || "$bench_rc" -ne 0 || "$quality_rc" -ne 0 ]]; then
  exit 1
fi
