#!/usr/bin/env bash
set -euo pipefail

# Corrected diagnostic four-GPU screen for intrinsic-MTP fixed trees. Two GPUs
# repeat the smallest branching tree to expose run/device variance; the other
# two test deeper/wider regular trees. The old flat-chain control is omitted
# because it does not export topology and is not comparable to this tree path.
if [[ "${QWEN27_MTP_TREE_RUNNER_SNAPSHOT:-0}" != "1" ]]; then
  repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
  snapshot="$(mktemp /tmp/qwen27-mtp-tree-screen.XXXXXX.sh)"
  cp "${BASH_SOURCE[0]}" "$snapshot"
  exec env \
    QWEN27_MTP_TREE_RUNNER_SNAPSHOT=1 \
    QWEN27_MTP_TREE_REPO_DIR="$repo_dir" \
    bash "$snapshot" "$@"
fi
trap 'rm -f "${BASH_SOURCE[0]}"' EXIT

repo_dir="${QWEN27_MTP_TREE_REPO_DIR:?missing snapshotted repo path}"
cd "$repo_dir"

STAMP="${STAMP:-$(date -u +%Y%m%dT%H%M%SZ)}"
PORT_BASE="${PORT_BASE:-19452}"
BENCH_MAX_TOKENS="${BENCH_MAX_TOKENS:-128}"
BENCH_METRIC_TOKENS="${BENCH_METRIC_TOKENS:-100}"
TREE_DRAFT_ENFORCE_EAGER="${TREE_DRAFT_ENFORCE_EAGER:-1}"
RUN_ROOT="${RUN_ROOT:-/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/diagnostics/qwen27-mtp-fixed-tree-corrected-$STAMP}"
OUT_DIR="${OUT_DIR:-$repo_dir/data/qwen36-27b-autoround-int4-b70-diagnostics}"
mkdir -p "$RUN_ROOT" "$OUT_DIR"

labels=(binary2-gpu0 binary2-gpu1 binary3 ternary2)
nodes=(6 6 14 12)
trees=(
  '[(0,), (1,), (0, 0), (0, 1), (1, 0), (1, 1)]'
  '[(0,), (1,), (0, 0), (0, 1), (1, 0), (1, 1)]'
  '[(0,), (1,), (0, 0), (0, 1), (1, 0), (1, 1), (0, 0, 0), (0, 0, 1), (0, 1, 0), (0, 1, 1), (1, 0, 0), (1, 0, 1), (1, 1, 0), (1, 1, 1)]'
  '[(0,), (1,), (2,), (0, 0), (0, 1), (0, 2), (1, 0), (1, 1), (1, 2), (2, 0), (2, 1), (2, 2)]'
)

run_lane() {
  local gpu="$1"
  local lane="${labels[$gpu]}"
  local node_count="${nodes[$gpu]}"
  local tree="${trees[$gpu]}"
  local port=$((PORT_BASE + gpu))
  local capture_size=$((node_count + 1))
  local label="qwen27-mtp-fixedtree-${lane}-n${node_count}"
  local run_dir="$RUN_ROOT/$lane"
  local tmp_dir="/tmp/q27mt-${STAMP}-${gpu}"
  local spec_config
  spec_config="$(jq -cn \
    --arg tree "$tree" \
    --argjson n "$node_count" \
    --argjson eager "$TREE_DRAFT_ENFORCE_EAGER" \
    '{method:"qwen3_next_mtp",num_speculative_tokens:$n,speculative_token_tree:$tree,attention_backend:"TREE_ATTN",enforce_eager:($eager == 1)}')"
  mkdir -p "$tmp_dir" "$run_dir/cache"

  (
    export GPU_INDEX="$gpu"
    export PORT="$port"
    export LABEL="$label"
    export RUN_DIR="$run_dir"
    export OUT_DIR
    export BENCH_MAX_TOKENS BENCH_METRIC_TOKENS
    export BENCH_OUT="$OUT_DIR/${label}-strict128-$STAMP.json"
    export SMOKE_OUT="$OUT_DIR/${label}-smoke-$STAMP.json"
    export SUMMARY_OUT="$OUT_DIR/${label}-summary-$STAMP.json"
    export RUN_QUALITY=0
    export QUALITY_REPEAT_RUNS=0
    export SMOKE_MAX_TOKENS=8
    export TMPDIR="$tmp_dir"
    export TORCHINDUCTOR_CACHE_DIR="$run_dir/cache/torchinductor"
    export TRITON_CACHE_DIR="$run_dir/cache/triton"

    export QWEN36_27B_ENABLE_MTP=0
    export QWEN36_27B_ENABLE_XPU_GRAPH=1
    export QWEN36_27B_SPECULATIVE_CONFIG="$spec_config"
    export COMPILATION_CONFIG="{\"cudagraph_mode\":\"FULL_DECODE_ONLY\",\"cudagraph_capture_sizes\":[$capture_size],\"max_cudagraph_capture_size\":$capture_size}"
    export VLLM_EXTRA_ARGS="--no-async-scheduling --mamba-cache-mode align --attention-backend TREE_ATTN --generation-config vllm"
    export VLLM_XPU_LM_HEAD_INT8=1
    export VLLM_XPU_LM_HEAD_INT8_SCALE_DTYPE=bf16
    export VLLM_XPU_DRAFT_LM_HEAD_INT4=1
    export VLLM_XPU_DRAFT_LM_HEAD_INT4_GROUP_SIZE=128
    export VLLM_XPU_DRAFT_LM_HEAD_INT4_SCALE_DTYPE=bf16
    export VLLM_XPU_GDN_NATIVE_SPEC_PREFIX_BASE_STATE=1
    export VLLM_XPU_GDN_NONSPEC_POSTPROCESS_ACCEPTED_STATE=1
    export VLLM_XPU_GDN_PROMOTE_ACCEPTED_SPEC_STATE=0
    export VLLM_XPU_DFLASH_DDTREE_BUDGET="$node_count"
    export VLLM_XPU_DDTREE_NATIVE_KV_COPY=1
    export VLLM_XPU_DDTREE_NATIVE_TREE_ATTN=1
    export VLLM_XPU_TREE_ATTN_BOOL_SDPA=1
    export VLLM_XPU_DDTREE_CAPTURE_GDN_CORE=1
    export VLLM_XPU_DDTREE_FULL_GRAPH=1

    experiments/qwen36-27b-autoround-int4-b70/scripts/run-vllm-candidate.sh \
      >"$run_dir/runner.log" 2>&1
  )
}

pids=()
for gpu in 0 1 2 3; do
  echo "launch gpu=$gpu port=$((PORT_BASE + gpu)) lane=${labels[$gpu]} nodes=${nodes[$gpu]}"
  run_lane "$gpu" &
  pids+=("$!")
done

rc=0
for pid in "${pids[@]}"; do
  if ! wait "$pid"; then
    rc=1
  fi
done

echo "MTP fixed-tree screen: $RUN_ROOT"
for gpu in 0 1 2 3; do
  label="qwen27-mtp-fixedtree-${labels[$gpu]}-n${nodes[$gpu]}"
  summary="$OUT_DIR/${label}-summary-$STAMP.json"
  if [[ -f "$summary" ]]; then
    jq -c '{label, primary_metric, status}' "$summary"
  else
    echo "missing summary for $label" >&2
  fi
done
exit "$rc"
