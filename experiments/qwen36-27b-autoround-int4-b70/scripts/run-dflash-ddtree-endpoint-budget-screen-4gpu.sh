#!/usr/bin/env bash
set -euo pipefail

# Four-GPU diagnostic endpoint screen for repaired Qwen27 DFlash/DDTree.
# Each GPU runs one tree budget against the fixed cold realistic suite. Quality
# is deliberately deferred until a budget beats the current endpoint screen.
if [[ "${QWEN27_DDTREE_ENDPOINT_RUNNER_SNAPSHOT:-0}" != "1" ]]; then
  repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
  snapshot="$(mktemp /tmp/qwen27-ddtree-endpoint-runner.XXXXXX.sh)"
  cp "${BASH_SOURCE[0]}" "$snapshot"
  exec env \
    QWEN27_DDTREE_ENDPOINT_RUNNER_SNAPSHOT=1 \
    QWEN27_DDTREE_REPO_DIR="$repo_dir" \
    bash "$snapshot" "$@"
fi
trap 'rm -f "${BASH_SOURCE[0]}"' EXIT

repo_dir="${QWEN27_DDTREE_REPO_DIR:?missing snapshotted repo path}"
cd "$repo_dir"

STAMP="${STAMP:-$(date -u +%Y%m%dT%H%M%SZ)}"
PORT_BASE="${PORT_BASE:-19436}"
BENCH_MAX_TOKENS="${BENCH_MAX_TOKENS:-128}"
BENCH_METRIC_TOKENS="${BENCH_METRIC_TOKENS:-100}"
SCREEN_TAG="${SCREEN_TAG:-depthrope}"
read -r -a budgets <<< "${BUDGETS:-4 8 12 15}"
if [[ "${#budgets[@]}" -ne 4 ]]; then
  echo "BUDGETS must contain exactly four integers, one per GPU" >&2
  exit 2
fi
RUN_ROOT="${RUN_ROOT:-/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/diagnostics/qwen27-ddtree-$SCREEN_TAG-budget-screen-$STAMP}"
OUT_DIR="${OUT_DIR:-$repo_dir/data/qwen36-27b-autoround-int4-b70-diagnostics}"
mkdir -p "$RUN_ROOT" "$OUT_DIR"

run_lane() {
  local gpu="$1"
  local budget="$2"
  local port=$((PORT_BASE + gpu))
  local capture_size=$((budget + 1))
  local label="qwen27-ddtree-${SCREEN_TAG}-k${budget}"
  local run_dir="$RUN_ROOT/k${budget}"
  local tmp_dir="/tmp/q27dt-${STAMP}-${gpu}"
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
    # ZMQ IPC paths are limited to 107 bytes on Linux; keep TMPDIR short.
    export TMPDIR="$tmp_dir"
    export TORCHINDUCTOR_CACHE_DIR="$run_dir/cache/torchinductor"
    export TRITON_CACHE_DIR="$run_dir/cache/triton"

    export QWEN36_27B_ENABLE_MTP=0
    export QWEN36_27B_ENABLE_XPU_GRAPH=1
    export QWEN36_27B_SPECULATIVE_CONFIG="{\"method\":\"dflash\",\"model\":\"/mnt/fast-ai/llm-cache/hf/manual/z-lab--Qwen3.6-27B-DFlash\",\"num_speculative_tokens\":$budget}"
    export COMPILATION_CONFIG="{\"cudagraph_mode\":\"FULL_DECODE_ONLY\",\"cudagraph_capture_sizes\":[$capture_size],\"max_cudagraph_capture_size\":$capture_size}"
    export VLLM_EXTRA_ARGS="--no-async-scheduling --mamba-cache-mode align --attention-backend TREE_ATTN --generation-config vllm"
    export VLLM_XPU_LM_HEAD_INT8=1
    export VLLM_XPU_LM_HEAD_INT8_SCALE_DTYPE=bf16
    export VLLM_XPU_GDN_NATIVE_SPEC_PREFIX_BASE_STATE=1
    export VLLM_XPU_GDN_NONSPEC_POSTPROCESS_ACCEPTED_STATE=1
    export VLLM_XPU_GDN_PROMOTE_ACCEPTED_SPEC_STATE=0
    export VLLM_XPU_QWEN3_DFLASH_LAYER_TYPES=mixed
    export VLLM_XPU_DFLASH_DDTREE_BUDGET="$budget"
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
  budget="${budgets[$gpu]}"
  echo "launch gpu=$gpu port=$((PORT_BASE + gpu)) budget=$budget"
  run_lane "$gpu" "$budget" &
  pids+=("$!")
done

rc=0
for pid in "${pids[@]}"; do
  if ! wait "$pid"; then
    rc=1
  fi
done

echo "DDTree endpoint budget screen: $RUN_ROOT"
for budget in "${budgets[@]}"; do
  summary="$OUT_DIR/qwen27-ddtree-${SCREEN_TAG}-k${budget}-summary-$STAMP.json"
  if [[ -f "$summary" ]]; then
    jq -c '{label, primary_metric, status}' "$summary"
  else
    echo "missing summary for k=$budget" >&2
  fi
done
exit "$rc"
