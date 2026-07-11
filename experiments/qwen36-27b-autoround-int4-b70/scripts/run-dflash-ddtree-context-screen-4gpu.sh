#!/usr/bin/env bash
set -euo pipefail

# Diagnostic-only context-length screen for the Qwen27 DFlash/DDTree oracle.
# Each GPU evaluates the same heldout anchors with a different target-hidden
# context cap. This is acceptance evidence, not endpoint throughput.
if [[ "${QWEN27_DDTREE_CONTEXT_RUNNER_SNAPSHOT:-0}" != "1" ]]; then
  original_repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
  snapshot="$(mktemp /tmp/qwen27-ddtree-context-runner.XXXXXX.sh)"
  cp "${BASH_SOURCE[0]}" "$snapshot"
  exec env \
    QWEN27_DDTREE_CONTEXT_RUNNER_SNAPSHOT=1 \
    QWEN27_DDTREE_REPO_DIR="$original_repo_dir" \
    bash "$snapshot" "$@"
fi
trap 'rm -f "${BASH_SOURCE[0]}"' EXIT

repo_dir="${QWEN27_DDTREE_REPO_DIR:?missing snapshotted repo path}"
cd "$repo_dir"

STAMP="${STAMP:-$(date -u +%Y%m%dT%H%M%SZ)}"
CORPUS_ROOT="${CORPUS_ROOT:-/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-dflash-aux-v8-corrected5-v6b-4gpu-20260710T040000Z}"
OUT_ROOT="${OUT_ROOT:-/mnt/usb-models/llm-optimization-artifacts/qwen27-dflash/ddtree-context-screen-4gpu-$STAMP}"
HELDOUT_STARTS="${HELDOUT_STARTS:-512}"
EVAL_REPEATS="${EVAL_REPEATS:-1}"
DRAFT_TOKENS="${DRAFT_TOKENS:-15}"
NODE_BUDGETS="${NODE_BUDGETS:-15}"
CONTEXTS="${CONTEXTS:-160 512 1024 2048}"
SEED="${SEED:-27}"

read -r -a contexts <<<"$CONTEXTS"
if [[ "${#contexts[@]}" -ne 4 ]]; then
  echo "CONTEXTS must contain exactly four space-separated values" >&2
  exit 2
fi

mkdir -p "$OUT_ROOT"

run_lane() {
  local gpu="$1"
  local max_context="$2"
  local out_dir="$OUT_ROOT/context-$max_context"
  mkdir -p "$out_dir/tmp" "$out_dir/cache"
  (
    export ZE_AFFINITY_MASK="$gpu"
    export ONEAPI_DEVICE_SELECTOR=level_zero:0
    export PYTORCH_ALLOC_CONF=expandable_segments:True
    export TMPDIR="$out_dir/tmp"
    export TORCHINDUCTOR_CACHE_DIR="$out_dir/cache/torchinductor"
    export TRITON_CACHE_DIR="$out_dir/cache/triton"
    /home/steve/.venvs/vllm-xpu/bin/python \
      scripts/evaluate-qwen27-dflash-ddtree-offline.py \
      --corpus-dir "$CORPUS_ROOT/shard-3/dataset" \
      --draft-tokens "$DRAFT_TOKENS" \
      --node-budgets "$NODE_BUDGETS" \
      --max-context "$max_context" \
      --heldout-starts "$HELDOUT_STARTS" \
      --eval-repeats "$EVAL_REPEATS" \
      --seed "$SEED" \
      --device xpu:0 \
      --progress-every 100 \
      --out "$out_dir/report.json" \
      >"$out_dir/stdout.log" \
      2>"$out_dir/stderr.log"
  )
}

pids=()
for gpu in 0 1 2 3; do
  max_context="${contexts[$gpu]}"
  echo "launch gpu=$gpu max_context=$max_context k=$DRAFT_TOKENS budgets=$NODE_BUDGETS"
  run_lane "$gpu" "$max_context" &
  pids+=("$!")
done

rc=0
for pid in "${pids[@]}"; do
  if ! wait "$pid"; then
    rc=1
  fi
done

printf 'DDTree context diagnostic root: %s\n' "$OUT_ROOT"
for report in "$OUT_ROOT"/*/report.json; do
  [[ -f "$report" ]] || continue
  jq -r '[input_filename, .max_context, .heldout_anchor_count, .vanilla.mean_visible_depth, (.budgets | to_entries | map([.key, .value.mean_visible_depth]))] | @json' "$report"
done
exit "$rc"
