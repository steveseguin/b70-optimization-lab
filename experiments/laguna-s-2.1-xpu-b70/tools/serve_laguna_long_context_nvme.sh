#!/usr/bin/env bash
# Separate 32K Laguna service identity for prompt-processing experiments.
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=laguna_nvme_paths.sh
source "$script_dir/laguna_nvme_paths.sh"

role="${1:?usage: serve_laguna_long_context_nvme.sh candidate|teacher RUN_DIR}"
run_dir="${2:?usage: serve_laguna_long_context_nvme.sh candidate|teacher RUN_DIR}"
readonly target_revision=4bbfc285f2f8b3b6b526274c133b7b17aae6c8cb
readonly draft_revision=5e07c246915c86dc6920fead03d019989224f2ba
readonly max_model_len="${LAGUNA_MAX_MODEL_LEN:-32768}"
readonly max_num_batched_tokens="${LAGUNA_MAX_NUM_BATCHED_TOKENS:-8192}"
readonly candidate_profile="${LAGUNA_LONG_CANDIDATE_PROFILE:-q12}"

case "$role" in candidate|teacher) ;; *) echo "unsupported role: $role" >&2; exit 2 ;; esac
[[ "$max_model_len" == 32768 ]] || {
  echo "the v1 long-context suite requires LAGUNA_MAX_MODEL_LEN=32768" >&2
  exit 2
}
case "$max_num_batched_tokens" in
  8192|16384|32768) ;;
  *) echo "LAGUNA_MAX_NUM_BATCHED_TOKENS must be 8192, 16384, or 32768" >&2; exit 2 ;;
esac
case "$run_dir" in "$LAGUNA_NVME_RUN_ROOT"/*) ;; *)
  echo "run directory is outside the fixed Laguna NVMe run root" >&2
  exit 2
esac
[[ "$(realpath -m -- "$run_dir")" == "$run_dir" ]] || {
  echo "run directory must already be canonical" >&2
  exit 2
}
laguna_nvme_prepare_paths
laguna_nvme_assert_fixed_path "$run_dir"

common_args=(
  "$LAGUNA_NVME_TARGET_ROOT"
  --host 127.0.0.1
  --port 18080
  --served-model-name laguna-s-2.1-int4
  --revision "$target_revision"
  --tokenizer "$LAGUNA_NVME_TARGET_ROOT"
  --tokenizer-revision "$target_revision"
  --trust-remote-code
  --dtype bfloat16
  --tensor-parallel-size 4
  --data-parallel-size 1
  --pipeline-parallel-size 1
  --distributed-executor-backend mp
  --enable-expert-parallel
  --all2all-backend allgather_reducescatter
  --max-model-len "$max_model_len"
  --max-num-batched-tokens "$max_num_batched_tokens"
  --max-num-seqs 1
  --block-size 64
  --kv-cache-dtype bfloat16
  --gpu-memory-utilization "${LAGUNA_GPU_UTIL:-0.90}"
  --enable-chunked-prefill
  --no-enable-prefix-caching
  --generation-config vllm
  --enable-prompt-tokens-details
  --enable-per-request-metrics
)

if [[ "$role" == candidate ]]; then
  required_environment=(
    VLLM_XPU_LAGUNA_M8_BREAKABLE_GRAPH
    VLLM_USE_BREAKABLE_CUDAGRAPH
    XPU_GRAPH
    VLLM_XPU_ENABLE_XPU_GRAPH
    VLLM_XPU_LAGUNA_M8_FUSED_W1_ROUTE_W2
    VLLM_XPU_LAGUNA_M8_ROUTE_INTERLEAVE
    VLLM_XPU_LAGUNA_M8_PREBUILT_EXACT_ATTN_METADATA
    VLLM_XPU_LAGUNA_DECODE_GRF128
    VLLM_XPU_LAGUNA_DECODE_TRANSPOSED_SCALES
    VLLM_XPU_LAGUNA_M8_QKNORM_ROPE
  )
  for name in "${required_environment[@]}"; do
    [[ "${!name:-}" == 1 ]] || {
      echo "$name must be explicitly enabled for the candidate" >&2
      exit 2
    }
  done
  case "$candidate_profile" in
    q12)
      required_profile_values=(
        VLLM_XPU_LAGUNA_M8_BF16_ROUTER_TOPK
        VLLM_XPU_LAGUNA_MWIDE_BF16_ROUTER_TOPK
        VLLM_XPU_LAGUNA_DFLASH_CONTEXT_KV_WORKSPACE
        VLLM_XPU_LAGUNA_DFLASH_FP8_W8A16
        VLLM_XPU_LAGUNA_DFLASH_SEGMENTED_GRAPH
        VLLM_XPU_LAGUNA_DFLASH_INLINE_ATTENTION_GRAPHS
        VLLM_XPU_LAGUNA_M12_SHARED_ELEMENTWISE
      )
      for name in "${required_profile_values[@]}"; do
        [[ "${!name:-}" == 1 ]] || {
          echo "$name must be enabled for the q12 candidate" >&2
          exit 2
        }
      done
      [[ "${VLLM_XPU_LAGUNA_M8_SHARED_ELEMENTWISE:-}" == 0 ]] || {
        echo "VLLM_XPU_LAGUNA_M8_SHARED_ELEMENTWISE must be zero for q12" >&2
        exit 2
      }
      [[ "${LAGUNA_M:-}" == 12 && "${LAGUNA_SPEC:-}" == 11 ]] || {
        echo "q12 candidate requires LAGUNA_M=12 and LAGUNA_SPEC=11" >&2
        exit 2
      }
      ;;
    q8)
      required_profile_values=(
        VLLM_XPU_LAGUNA_M8_SHARED_ELEMENTWISE
      )
      for name in "${required_profile_values[@]}"; do
        [[ "${!name:-}" == 1 ]] || {
          echo "$name must be enabled for the q8 candidate" >&2
          exit 2
        }
      done
      disabled_profile_values=(
        VLLM_XPU_LAGUNA_M8_BF16_ROUTER_TOPK
        VLLM_XPU_LAGUNA_MWIDE_BF16_ROUTER_TOPK
        VLLM_XPU_LAGUNA_DFLASH_CONTEXT_KV_WORKSPACE
        VLLM_XPU_LAGUNA_DFLASH_FP8_W8A16
        VLLM_XPU_LAGUNA_DFLASH_SEGMENTED_GRAPH
        VLLM_XPU_LAGUNA_DFLASH_INLINE_ATTENTION_GRAPHS
        VLLM_XPU_LAGUNA_M12_SHARED_ELEMENTWISE
      )
      for name in "${disabled_profile_values[@]}"; do
        [[ "${!name:-}" == 0 ]] || {
          echo "$name must be zero for the q8 candidate" >&2
          exit 2
        }
      done
      [[ "${LAGUNA_M:-}" == 8 && "${LAGUNA_SPEC:-}" == 7 ]] || {
        echo "q8 candidate requires LAGUNA_M=8 and LAGUNA_SPEC=7" >&2
        exit 2
      }
      ;;
    *)
      echo "LAGUNA_LONG_CANDIDATE_PROFILE must be q12 or q8" >&2
      exit 2
      ;;
  esac
  [[ "${VLLM_USE_AOT_COMPILE:-}" == 0 ]] || {
    echo "candidate requires VLLM_USE_AOT_COMPILE=0" >&2
    exit 2
  }
  common_args+=(
    --no-async-scheduling
    --compilation-config
    "{\"mode\":\"NONE\",\"cudagraph_mode\":\"PIECEWISE\",\"cudagraph_capture_sizes\":[${LAGUNA_M}],\"max_cudagraph_capture_size\":${LAGUNA_M}}"
    --speculative-config
    "{\"method\":\"dflash\",\"model\":\"$LAGUNA_NVME_DRAFT_ROOT\",\"revision\":\"$draft_revision\",\"num_speculative_tokens\":${LAGUNA_SPEC},\"draft_sample_method\":\"greedy\",\"rejection_sample_method\":\"standard\",\"use_local_argmax_reduction\":false}"
  )
else
  # The canonical q=1 identity is target-only eager execution with its original
  # asynchronous scheduler. The runner records the source revision separately.
  common_args+=(--enforce-eager)
fi

exec vllm serve "${common_args[@]}"
