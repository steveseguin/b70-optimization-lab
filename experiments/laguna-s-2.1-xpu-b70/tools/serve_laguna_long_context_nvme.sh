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
readonly max_num_scheduled_tokens="${LAGUNA_MAX_NUM_SCHEDULED_TOKENS:-auto}"
readonly candidate_profile="${LAGUNA_LONG_CANDIDATE_PROFILE:-q12}"

case "$role" in candidate|teacher) ;; *) echo "unsupported role: $role" >&2; exit 2 ;; esac
[[ "$max_model_len" == 32768 ]] || {
  echo "the v1 long-context suite requires LAGUNA_MAX_MODEL_LEN=32768" >&2
  exit 2
}
case "$max_num_batched_tokens" in
  4096|8192|8202|16384|32768) ;;
  8184|8188)
    # Only the depth-sweep profile pins an off-stride budget, and only to keep
    # the derived scheduler budget at 8182 once the draft depth changes. These
    # are 8182+(depth-1) for depths 3 and 7; the profile still decides which of
    # those depths it will actually run.
    [[ "$role" == candidate && "$candidate_profile" == qdepth ]] || {
      echo "batched=$max_num_batched_tokens is reserved for the qdepth depth-sweep candidate" >&2
      exit 2
    }
    ;;
  8182)
    # The depth-1 qdepth pin, and the only budget that gives the speculation-off
    # teacher the candidate's partition. With no speculative config the derived
    # budget is never computed and the scheduler falls back to the batched
    # budget, so a teacher at 8192 silently runs the 8192/8064 partition that
    # was rejected on 2026-08-02 rather than the candidate's 8182/8094.
    [[ "$role" == teacher \
      || ( "$role" == candidate && "$candidate_profile" == qdepth ) ]] || {
      echo "batched=8182 is reserved for the qdepth candidate and the partition-aligned teacher" >&2
      exit 2
    }
    ;;
  *) echo "LAGUNA_MAX_NUM_BATCHED_TOKENS must be 4096, 8182, 8184, 8188, 8192, 8202, 16384, or 32768" >&2; exit 2 ;;
esac
case "$max_num_scheduled_tokens" in
  auto) ;;
  8192)
    [[ "$role" == candidate && "$candidate_profile" == q12 \
      && "${VLLM_XPU_LAGUNA_EXACT_PREFILL_CHUNKS:-}" == 1 \
      && "$max_num_batched_tokens" == 8202 ]] || {
      echo "scheduled-token alignment requires q12 exact-prefill candidate with batched=8202 and scheduled=8192" >&2
      exit 2
    }
    ;;
  *) echo "LAGUNA_MAX_NUM_SCHEDULED_TOKENS must be auto or 8192" >&2; exit 2 ;;
esac
[[ "$max_num_batched_tokens" != 8202 || "$max_num_scheduled_tokens" == 8192 ]] || {
  echo "batched=8202 is reserved for the explicit scheduled=8192 alignment treatment" >&2
  exit 2
}
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
if [[ "$max_num_scheduled_tokens" != auto ]]; then
  common_args+=(--max-num-scheduled-tokens "$max_num_scheduled_tokens")
fi
printf 'Laguna long scheduler budget: batched=%s scheduled=%s\n' \
  "$max_num_batched_tokens" "$max_num_scheduled_tokens" >&2

if [[ "$role" == candidate ]]; then
  required_environment=(
    VLLM_XPU_LAGUNA_M8_BREAKABLE_GRAPH
    VLLM_USE_BREAKABLE_CUDAGRAPH
    XPU_GRAPH
    VLLM_XPU_ENABLE_XPU_GRAPH
    VLLM_XPU_LAGUNA_M8_FUSED_W1_ROUTE_W2
    VLLM_XPU_LAGUNA_M8_ROUTE_INTERLEAVE
    VLLM_XPU_LAGUNA_M8_PREBUILT_EXACT_ATTN_METADATA
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
        VLLM_XPU_LAGUNA_DECODE_GRF128
        VLLM_XPU_LAGUNA_DECODE_TRANSPOSED_SCALES
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
      [[ "${VLLM_XPU_LAGUNA_DFLASH_FP8_Q8:-}" == 0 ]] || {
        echo "VLLM_XPU_LAGUNA_DFLASH_FP8_Q8 must be zero for q12" >&2
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
        VLLM_XPU_LAGUNA_DFLASH_FP8_Q8
        VLLM_XPU_LAGUNA_DFLASH_SEGMENTED_GRAPH
        VLLM_XPU_LAGUNA_DFLASH_INLINE_ATTENTION_GRAPHS
        VLLM_XPU_LAGUNA_M12_SHARED_ELEMENTWISE
        VLLM_XPU_LAGUNA_DECODE_GRF128
        VLLM_XPU_LAGUNA_DECODE_TRANSPOSED_SCALES
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
    q8fp8)
      required_profile_values=(
        VLLM_XPU_LAGUNA_M8_SHARED_ELEMENTWISE
        VLLM_XPU_LAGUNA_DFLASH_CONTEXT_KV_WORKSPACE
        VLLM_XPU_LAGUNA_DFLASH_FP8_W8A16
        VLLM_XPU_LAGUNA_DFLASH_FP8_Q8
      )
      for name in "${required_profile_values[@]}"; do
        [[ "${!name:-}" == 1 ]] || {
          echo "$name must be enabled for the q8fp8 candidate" >&2
          exit 2
        }
      done
      disabled_profile_values=(
        VLLM_XPU_LAGUNA_M8_BF16_ROUTER_TOPK
        VLLM_XPU_LAGUNA_MWIDE_BF16_ROUTER_TOPK
        VLLM_XPU_LAGUNA_DFLASH_SEGMENTED_GRAPH
        VLLM_XPU_LAGUNA_DFLASH_INLINE_ATTENTION_GRAPHS
        VLLM_XPU_LAGUNA_M12_SHARED_ELEMENTWISE
        VLLM_XPU_LAGUNA_DECODE_GRF128
        VLLM_XPU_LAGUNA_DECODE_TRANSPOSED_SCALES
      )
      for name in "${disabled_profile_values[@]}"; do
        [[ "${!name:-}" == 0 ]] || {
          echo "$name must be zero for the q8fp8 candidate" >&2
          exit 2
        }
      done
      [[ "${LAGUNA_M:-}" == 8 && "${LAGUNA_SPEC:-}" == 7 ]] || {
        echo "q8fp8 candidate requires LAGUNA_M=8 and LAGUNA_SPEC=7" >&2
        exit 2
      }
      ;;
    qdepth)
      # Long-context draft-depth sweep. The only interpretable arm-to-arm
      # difference must be the draft depth, so every selector that the vLLM
      # fork pins to one depth or one verifier width is held off at every
      # depth, including at depth 11 where the incumbent enables it:
      #   MWIDE/M8 BF16 router top-k     exact width 12 only
      #     (models/laguna.py `_use_mwide_bf16_router_topk` contract; with the
      #     base router on and MWIDE off a non-eager target raises outright)
      #   DFlash context-KV workspace    depth 11 and width 12
      #     (models/laguna_dflash.py context-KV contract failures)
      #   DFlash FP8 W8A16 / Q8          require the context-KV workspace
      #   DFlash segmented/inline graph  width 12
      #     (worker `_validate_laguna_m8_breakable_graph_config` plus a
      #     capture filter hard-coded to num_tokens == 12)
      #   M12 shared elementwise         depth 11 exactly
      #   M8 shared elementwise          depth 7 exactly, so it cannot be held
      #     constant across arms either and stays off at both depths
      #   M12 mapped gather/scale/add    requires M12 shared elementwise
      #   exact prefill chunks           width 12
      #   wide-prefill QKNorm+RoPE       width 12, depth 11, and batched 8192
      #   decode GRF128 / transposed scales
      #     no width gate anywhere in the vLLM fork, so their width
      #     independence cannot be established here; held off rather than
      #     assumed safe at a width they have never run at
      # The shared candidate selectors above this case stay on. Of those only
      # the fused M8 QKNorm+RoPE is width-sensitive, and it fires at verifier
      # width 8 and 12 alike, which is what limits the measurable depths.
      disabled_profile_values=(
        VLLM_XPU_LAGUNA_M8_BF16_ROUTER_TOPK
        VLLM_XPU_LAGUNA_MWIDE_BF16_ROUTER_TOPK
        VLLM_XPU_LAGUNA_DFLASH_CONTEXT_KV_WORKSPACE
        VLLM_XPU_LAGUNA_DFLASH_FP8_W8A16
        VLLM_XPU_LAGUNA_DFLASH_FP8_Q8
        VLLM_XPU_LAGUNA_DFLASH_SEGMENTED_GRAPH
        VLLM_XPU_LAGUNA_DFLASH_INLINE_ATTENTION_GRAPHS
        VLLM_XPU_LAGUNA_M12_SHARED_ELEMENTWISE
        VLLM_XPU_LAGUNA_M8_SHARED_ELEMENTWISE
        VLLM_XPU_LAGUNA_M12_MAPPED_GATHER_SCALE_ADD
        VLLM_XPU_LAGUNA_EXACT_PREFILL_CHUNKS
        VLLM_XPU_LAGUNA_WIDE_PREFILL_QKNORM_ROPE
        VLLM_XPU_LAGUNA_DECODE_GRF128
        VLLM_XPU_LAGUNA_DECODE_TRANSPOSED_SCALES
      )
      for name in "${disabled_profile_values[@]}"; do
        [[ "${!name:-}" == 0 ]] || {
          echo "$name must be zero for the qdepth candidate" >&2
          exit 2
        }
      done
      case "${LAGUNA_SPEC:-}" in
        11|7) ;;
        0)
          [[ "${LAGUNA_NOSPEC_GRAPH:-0}" == 1 ]] || {
            echo "qdepth depth 0 is the no-drafter arm and requires LAGUNA_NOSPEC_GRAPH=1" >&2
            exit 2
          }
          ;;
        3|1)
          echo "qdepth depth ${LAGUNA_SPEC} is not cleanly measurable: the fused target QKNorm+RoPE only fires at verifier width 8 or 12, and no width-4 or width-2 shared-elementwise op exists, so the target path would silently degrade" >&2
          exit 2
          ;;
        *)
          echo "qdepth candidate requires LAGUNA_SPEC=11 or LAGUNA_SPEC=7" >&2
          exit 2
          ;;
      esac
      [[ "${LAGUNA_M:-}" == "$((LAGUNA_SPEC + 1))" ]] || {
        echo "qdepth candidate requires LAGUNA_M to be LAGUNA_SPEC plus one" >&2
        exit 2
      }
      [[ "${VLLM_XPU_LAGUNA_EXACT_MAX_M:-}" == "$LAGUNA_M" ]] || {
        echo "qdepth candidate requires VLLM_XPU_LAGUNA_EXACT_MAX_M to equal LAGUNA_M" >&2
        exit 2
      }
      [[ "$max_num_scheduled_tokens" == auto ]] || {
        echo "qdepth candidate requires the automatic scheduled-token budget" >&2
        exit 2
      }
      [[ "$max_num_batched_tokens" != 8202 ]] || {
        echo "batched=8202 belongs to the closed alignment treatment, not to qdepth" >&2
        exit 2
      }
      # Parallel drafting reserves LAGUNA_SPEC-1 slots per sequence at
      # max_num_seqs=1, so pinning the batched budget to 8182+(depth-1) keeps
      # the derived per-step budget, and therefore the 32,640-token prefill
      # partition, byte-identical to the incumbent at every depth.
      readonly derived_scheduled_tokens="$((max_num_batched_tokens - (LAGUNA_SPEC - 1)))"
      [[ "$derived_scheduled_tokens" == 8182 ]] || {
        echo "qdepth derives max_num_scheduled_tokens=$derived_scheduled_tokens from batched=$max_num_batched_tokens at depth $LAGUNA_SPEC; set LAGUNA_MAX_NUM_BATCHED_TOKENS=$((8182 + LAGUNA_SPEC - 1)) so it derives 8182" >&2
        exit 2
      }
      printf 'Laguna qdepth arm: depth=%s width=%s batched=%s derived_scheduled=%s\n' \
        "$LAGUNA_SPEC" "$LAGUNA_M" "$max_num_batched_tokens" "$derived_scheduled_tokens" >&2
      ;;
    *)
      echo "LAGUNA_LONG_CANDIDATE_PROFILE must be q12, q8, q8fp8, or qdepth" >&2
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
  )
  # Diagnostic width-1 arm: graphed target execution with no drafter at all.
  # It isolates what graph capture alone is worth, which neither the M=8 nor the
  # M=12 arm can show because both pay for draft passes inside the same step,
  # and which the eager teacher cannot show because it captures nothing.
  if [[ "${LAGUNA_NOSPEC_GRAPH:-0}" == 1 ]]; then
    [[ "$LAGUNA_M" == 1 && "${VLLM_XPU_LAGUNA_EXACT_MAX_M:-}" == 1 ]] || {
      echo "LAGUNA_NOSPEC_GRAPH requires LAGUNA_M=1 and VLLM_XPU_LAGUNA_EXACT_MAX_M=1" >&2
      exit 2
    }
  else
    common_args+=(
      --speculative-config
      "{\"method\":\"dflash\",\"model\":\"$LAGUNA_NVME_DRAFT_ROOT\",\"revision\":\"$draft_revision\",\"num_speculative_tokens\":${LAGUNA_SPEC},\"draft_sample_method\":\"greedy\",\"rejection_sample_method\":\"standard\",\"use_local_argmax_reduction\":false}"
    )
  fi
else
  # The canonical q=1 identity is target-only eager execution with its original
  # asynchronous scheduler. The runner records the source revision separately.
  common_args+=(--enforce-eager)
fi

exec vllm serve "${common_args[@]}"
