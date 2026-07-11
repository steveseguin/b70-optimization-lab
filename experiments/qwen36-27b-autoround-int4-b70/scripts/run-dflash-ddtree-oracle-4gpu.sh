#!/usr/bin/env bash
set -euo pipefail

# Diagnostic-only four-GPU DDTree acceptance sweep. This does not measure
# endpoint throughput and must never be submitted to LocalMaxxing.
if [[ "${QWEN27_DDTREE_RUNNER_SNAPSHOT:-0}" != "1" ]]; then
  original_repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
  snapshot="$(mktemp /tmp/qwen27-ddtree-runner.XXXXXX.sh)"
  cp "${BASH_SOURCE[0]}" "$snapshot"
  exec env \
    QWEN27_DDTREE_RUNNER_SNAPSHOT=1 \
    QWEN27_DDTREE_REPO_DIR="$original_repo_dir" \
    bash "$snapshot" "$@"
fi
trap 'rm -f "${BASH_SOURCE[0]}"' EXIT

repo_dir="${QWEN27_DDTREE_REPO_DIR:?missing snapshotted repo path}"
cd "$repo_dir"

STAMP="${STAMP:-$(date -u +%Y%m%dT%H%M%SZ)}"
CORPUS_ROOT="${CORPUS_ROOT:-/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-dflash-aux-v8-corrected5-v6b-4gpu-20260710T040000Z}"
OUT_ROOT="${OUT_ROOT:-/mnt/usb-models/llm-optimization-artifacts/qwen27-dflash/ddtree-oracle-4gpu-$STAMP}"
HELDOUT_STARTS="${HELDOUT_STARTS:-1024}"
SEED="${SEED:-27}"
MODE="${MODE:-sweep}"
EVAL_REPEATS="${EVAL_REPEATS:-3}"
MAX_CONTEXT="${MAX_CONTEXT:-160}"

mkdir -p "$OUT_ROOT"

run_lane() {
  local gpu="$1"
  local label="$2"
  local draft_tokens="$3"
  local budgets="$4"
  local out_dir="$OUT_ROOT/$label"
  mkdir -p "$out_dir/tmp" "$out_dir/cache"
  (
    repeat_args=(--deterministic-one-pass)
    if [[ "$MODE" == "confirm" ]]; then
      repeat_args=(--eval-repeats "$EVAL_REPEATS")
    fi
    export ZE_AFFINITY_MASK="$gpu"
    export ONEAPI_DEVICE_SELECTOR=level_zero:0
    export PYTORCH_ALLOC_CONF=expandable_segments:True
    export TMPDIR="$out_dir/tmp"
    export TORCHINDUCTOR_CACHE_DIR="$out_dir/cache/torchinductor"
    export TRITON_CACHE_DIR="$out_dir/cache/triton"
    /home/steve/.venvs/vllm-xpu/bin/python \
      scripts/evaluate-qwen27-dflash-ddtree-offline.py \
      --corpus-dir "$CORPUS_ROOT/shard-3/dataset" \
      --draft-tokens "$draft_tokens" \
      --heldout-starts "$HELDOUT_STARTS" \
      --max-context "$MAX_CONTEXT" \
      "${repeat_args[@]}" \
      --node-budgets "$budgets" \
      --seed "$SEED" \
      --device xpu:0 \
      --progress-every 100 \
      --out "$out_dir/report.json" \
      >"$out_dir/stdout.log" \
      2>"$out_dir/stderr.log"
  )
}

if [[ "$MODE" == "confirm" ]]; then
  lanes=(
    "0|k4|4|4,16,32"
    "1|k8|8|8,16,32"
    "2|k12|12|12,24,48"
    "3|k15|15|15,30"
  )
elif [[ "$MODE" == "sweep" ]]; then
  lanes=(
    "0|k4|4|4,8,16,32,64"
    "1|k8|8|8,16,32,64,128"
    "2|k12|12|12,24,48,96,192"
    "3|k15|15|15,30,60,120,240"
  )
else
  echo "unknown MODE=$MODE (expected sweep or confirm)" >&2
  exit 1
fi

pids=()
for lane in "${lanes[@]}"; do
  IFS='|' read -r gpu label draft_tokens budgets <<<"$lane"
  echo "launch gpu=$gpu label=$label k=$draft_tokens budgets=$budgets"
  run_lane "$gpu" "$label" "$draft_tokens" "$budgets" &
  pids+=("$!")
done

rc=0
for pid in "${pids[@]}"; do
  if ! wait "$pid"; then
    rc=1
  fi
done

printf 'DDTree diagnostic root: %s\n' "$OUT_ROOT"
for report in "$OUT_ROOT"/*/report.json; do
  [[ -f "$report" ]] || continue
  jq -r '[input_filename, .draft_tokens, .vanilla.mean_visible_depth, (.budgets | to_entries | map([.key, .value.mean_visible_depth]))] | @json' "$report"
done
exit "$rc"
