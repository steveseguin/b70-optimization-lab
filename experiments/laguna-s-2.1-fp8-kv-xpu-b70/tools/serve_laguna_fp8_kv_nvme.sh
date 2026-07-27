#!/usr/bin/env bash
# Target-only FP8 teacher or width-12/depth-11 FP8 DFlash candidate.
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
repo_root="$(git -C "$script_dir" rev-parse --show-toplevel)"
# shellcheck source=/dev/null
source "$repo_root/experiments/laguna-s-2.1-xpu-b70/tools/laguna_nvme_paths.sh"

mode="${1:?usage: serve_laguna_fp8_kv_nvme.sh teacher|candidate|candidate-eager RUN_DIR}"
run_dir="${2:?usage: serve_laguna_fp8_kv_nvme.sh teacher|candidate|candidate-eager RUN_DIR}"
case "$mode" in teacher|candidate|candidate-eager) ;;
  *) echo "unsupported mode: $mode" >&2; exit 2 ;;
esac

readonly target_revision=4bbfc285f2f8b3b6b526274c133b7b17aae6c8cb
readonly draft_revision=5e07c246915c86dc6920fead03d019989224f2ba
readonly fp8_run_root="$LAGUNA_NVME_RUN_ROOT/fp8-kv"

case "$run_dir" in "$fp8_run_root"/*) ;; *)
  echo "run directory is outside the FP8 KV run root" >&2
  exit 2
esac
[[ "$(realpath -m -- "$run_dir")" == "$run_dir" ]] || {
  echo "run directory must already be canonical" >&2
  exit 2
}
[[ "${VLLM_XPU_LAGUNA_FP8_KV_SCALE_AUDIT:-}" == 1 ]] || {
  echo "VLLM_XPU_LAGUNA_FP8_KV_SCALE_AUDIT must be enabled" >&2
  exit 2
}
[[ "${VLLM_XPU_LAGUNA_M8_PERSISTENT_KV_CACHE_VIEWS:-}" == 0 ]] || {
  echo "persistent BF16 KV views must be explicitly disabled" >&2
  exit 2
}

laguna_nvme_prepare_paths
mkdir -p -- "$fp8_run_root"
laguna_nvme_assert_fixed_path "$fp8_run_root"
laguna_nvme_assert_fixed_path "$run_dir"

common_args=(
  "$LAGUNA_NVME_TARGET_ROOT"
  --host 127.0.0.1
  --port 18080
  --served-model-name laguna-s-2.1-int4-fp8-kv
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
  --max-model-len 8192
  --max-num-batched-tokens 8192
  --max-num-seqs 1
  --block-size 64
  --kv-cache-dtype fp8
  --gpu-memory-utilization "${LAGUNA_GPU_UTIL:-0.90}"
  --no-enable-prefix-caching
  --no-async-scheduling
  --generation-config vllm
  --enable-prompt-tokens-details
)

if [[ "$mode" != teacher ]]; then
  required_environment=(
    VLLM_XPU_LAGUNA_M8_FUSED_W1_ROUTE_W2
    VLLM_XPU_LAGUNA_M8_ROUTE_INTERLEAVE
  )
  for name in "${required_environment[@]}"; do
    [[ "${!name:-}" == 1 ]] || {
      echo "$name must be explicitly enabled for the candidate" >&2
      exit 2
    }
  done
fi

if [[ "$mode" == candidate ]]; then
  for name in \
    VLLM_XPU_LAGUNA_MWIDE_BF16_ROUTER_TOPK \
    VLLM_XPU_LAGUNA_DFLASH_CONTEXT_KV_WORKSPACE \
    VLLM_XPU_LAGUNA_DFLASH_FP8_W8A16 \
    VLLM_XPU_LAGUNA_M8_BREAKABLE_GRAPH \
    VLLM_USE_BREAKABLE_CUDAGRAPH \
    XPU_GRAPH \
    VLLM_XPU_ENABLE_XPU_GRAPH; do
    [[ "${!name:-}" == 1 ]] || {
      echo "$name must be explicitly enabled for the graph candidate" >&2
      exit 2
    }
  done
  common_args+=(
    --compilation-config
    '{"mode":"NONE","cudagraph_mode":"PIECEWISE","cudagraph_capture_sizes":[12],"max_cudagraph_capture_size":12}'
  )
elif [[ "$mode" == candidate-eager ]]; then
  for name in \
    VLLM_XPU_LAGUNA_M8_PREBUILT_EXACT_ATTN_METADATA \
    VLLM_XPU_LAGUNA_MWIDE_BF16_ROUTER_TOPK \
    VLLM_XPU_LAGUNA_DFLASH_CONTEXT_KV_WORKSPACE \
    VLLM_XPU_LAGUNA_DFLASH_FP8_W8A16; do
    [[ "${!name:-}" == 0 ]] || {
      echo "$name must be disabled for the eager isolation" >&2
      exit 2
    }
  done
  common_args+=(--enforce-eager)
else
  common_args+=(--enforce-eager)
fi

if [[ "$mode" != teacher ]]; then
  common_args+=(
    --speculative-config
    "{\"method\":\"dflash\",\"model\":\"$LAGUNA_NVME_DRAFT_ROOT\",\"revision\":\"$draft_revision\",\"num_speculative_tokens\":11,\"draft_sample_method\":\"greedy\",\"rejection_sample_method\":\"standard\",\"use_local_argmax_reduction\":false}"
  )
fi

exec vllm serve "${common_args[@]}"
