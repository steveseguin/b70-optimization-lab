#!/usr/bin/env bash
# Exact production-shaped Laguna M8 eager endpoint for formal A/B crossover legs.
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=laguna_nvme_paths.sh
source "$script_dir/laguna_nvme_paths.sh"

run_dir="${1:?usage: serve_laguna_m8_eager_nvme.sh RUN_DIR}"

readonly model_root="$LAGUNA_NVME_TARGET_ROOT"
readonly draft_root="$LAGUNA_NVME_DRAFT_ROOT"
readonly target_revision=4bbfc285f2f8b3b6b526274c133b7b17aae6c8cb
readonly draft_revision=5e07c246915c86dc6920fead03d019989224f2ba

case "$run_dir" in
  "$LAGUNA_NVME_RUN_ROOT"/*) ;;
  *) echo "run directory is outside the fixed Laguna NVMe run root" >&2; exit 2 ;;
esac
[[ "$(realpath -m -- "$run_dir")" == "$run_dir" ]] || {
  echo "run directory must already be canonical" >&2
  exit 2
}
laguna_nvme_prepare_paths
laguna_nvme_assert_fixed_path "$run_dir"

# This is intentionally the same selector stack as the graph wrapper.  The
# four explicit graph switches below are the only treatment difference.
for name in \
  VLLM_XPU_LAGUNA_M8_FUSED_W1_ROUTE_W2 \
  VLLM_XPU_LAGUNA_M8_ROUTE_INTERLEAVE \
  VLLM_XPU_LAGUNA_M8_SHARED_ELEMENTWISE \
  VLLM_XPU_LAGUNA_M8_QKNORM_ROPE; do
  [[ "${!name:-}" == 1 ]] || { echo "$name must be explicitly enabled" >&2; exit 2; }
done
for name in \
  VLLM_XPU_LAGUNA_M8_BREAKABLE_GRAPH \
  VLLM_USE_BREAKABLE_CUDAGRAPH \
  XPU_GRAPH \
  VLLM_XPU_ENABLE_XPU_GRAPH; do
  [[ "${!name:-}" == 0 ]] || { echo "$name must be explicitly disabled" >&2; exit 2; }
done
[[ "${VLLM_USE_AOT_COMPILE:-}" == 0 ]] || { echo "VLLM_USE_AOT_COMPILE must be 0" >&2; exit 2; }
[[ "${VLLM_XPU_LAGUNA_DETERMINISTIC_GRAPH:-}" == 0 ]] || { echo "VLLM_XPU_LAGUNA_DETERMINISTIC_GRAPH must be 0" >&2; exit 2; }
for forbidden in VLLM_XPU_LAGUNA_M8_EVIDENCE VLLM_XPU_LAGUNA_M8_EVIDENCE_ARM VLLM_XPU_LAGUNA_M8_EVIDENCE_ROOT; do
  [[ ! -v "$forbidden" ]] || { echo "diagnostic evidence variable must be absent: $forbidden" >&2; exit 2; }
done

exec vllm serve "$model_root" \
  --host 127.0.0.1 \
  --port 18080 \
  --served-model-name laguna-s-2.1-int4 \
  --revision "$target_revision" \
  --tokenizer "$model_root" \
  --tokenizer-revision "$target_revision" \
  --trust-remote-code \
  --dtype bfloat16 \
  --tensor-parallel-size 4 \
  --data-parallel-size 1 \
  --pipeline-parallel-size 1 \
  --distributed-executor-backend mp \
  --enable-expert-parallel \
  --all2all-backend allgather_reducescatter \
  --max-model-len 8192 \
  --max-num-batched-tokens 8192 \
  --max-num-seqs 1 \
  --block-size 64 \
  --kv-cache-dtype bfloat16 \
  --gpu-memory-utilization 0.90 \
  --no-enable-prefix-caching \
  --no-async-scheduling \
  --enforce-eager \
  --generation-config vllm \
  --enable-prompt-tokens-details \
  --speculative-config "{\"method\":\"dflash\",\"model\":\"$draft_root\",\"revision\":\"$draft_revision\",\"num_speculative_tokens\":7,\"draft_sample_method\":\"greedy\",\"rejection_sample_method\":\"standard\"}"
