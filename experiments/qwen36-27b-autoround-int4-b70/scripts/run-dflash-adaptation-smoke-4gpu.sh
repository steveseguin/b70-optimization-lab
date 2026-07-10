#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$repo_dir"

STAMP="${STAMP:-$(date -u +%Y%m%dT%H%M%SZ)}"
CORPUS_ROOT="${CORPUS_ROOT:-/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-dflash-aux-v8-corrected5-v6b-4gpu-20260710T040000Z}"
OUT_ROOT="${OUT_ROOT:-/mnt/usb-models/llm-optimization-artifacts/qwen27-dflash/adaptation-smoke-4gpu-$STAMP}"
MATRIX="${MATRIX:-smoke}"
if [[ "$MATRIX" == "long" ]]; then
  STEPS="${STEPS:-2000}"
  HELDOUT_STARTS="${HELDOUT_STARTS:-1024}"
  EVAL_EVERY="${EVAL_EVERY:-500}"
else
  STEPS="${STEPS:-200}"
  HELDOUT_STARTS="${HELDOUT_STARTS:-512}"
  EVAL_EVERY="${EVAL_EVERY:-100}"
fi
TRAIN_STARTS="${TRAIN_STARTS:-8192}"
EVAL_REPEATS="${EVAL_REPEATS:-3}"

for shard in 0 1 2 3; do
  if [[ ! -d "$CORPUS_ROOT/shard-$shard/dataset" ]]; then
    echo "missing corrected DFlash corpus shard: $CORPUS_ROOT/shard-$shard/dataset" >&2
    exit 1
  fi
done

mkdir -p "$OUT_ROOT"

run_variant() {
  local gpu="$1"
  local label="$2"
  local scope="$3"
  local loss_mode="$4"
  local lr="$5"
  local decay="$6"
  local out_dir="$OUT_ROOT/$label"
  mkdir -p "$out_dir/tmp" "$out_dir/cache"
  (
    export ZE_AFFINITY_MASK="$gpu"
    export ONEAPI_DEVICE_SELECTOR=level_zero:0
    export PYTORCH_ALLOC_CONF=expandable_segments:True
    export TMPDIR="$out_dir/tmp"
    export TORCHINDUCTOR_CACHE_DIR="$out_dir/cache/torchinductor"
    export TRITON_CACHE_DIR="$out_dir/cache/triton"
    /home/steve/.venvs/vllm-xpu/bin/python \
      scripts/train-qwen27-dflash-offline.py \
      --dataset-dir "$CORPUS_ROOT/shard-0/dataset" \
      --dataset-dir "$CORPUS_ROOT/shard-1/dataset" \
      --dataset-dir "$CORPUS_ROOT/shard-2/dataset" \
      --heldout-dir "$CORPUS_ROOT/shard-3/dataset" \
      --out-dir "$out_dir" \
      --device xpu:0 \
      --draft-tokens 8 \
      --min-context 16 \
      --max-context 160 \
      --train-starts "$TRAIN_STARTS" \
      --heldout-starts "$HELDOUT_STARTS" \
      --eval-repeats "$EVAL_REPEATS" \
      --steps "$STEPS" \
      --lr "$lr" \
      --lr-schedule cosine \
      --loss-mode "$loss_mode" \
      --position-decay "$decay" \
      --train-scope "$scope" \
      --eval-every "$EVAL_EVERY" \
      --log-every 20 \
      > "$out_dir/train.stdout.log" \
      2> "$out_dir/train.stderr.log"
  )
}

# The public DFlash weights are already trained. These are conservative
# adaptation rates, not the paper's from-scratch 6e-4 rate.
if [[ "$MATRIX" == "long" ]]; then
  variants=(
    "0|layers-paperdecay-lr3e-6|layers|position-decay|3e-6|0.7788007830714049"
    "1|layers-paperdecay-lr1e-5|layers|position-decay|1e-5|0.7788007830714049"
    "2|layers-auf-lr1e-5|layers|accept-until-fail|1e-5|0.7788007830714049"
    "3|all-auf-lr1e-5|all-draft|accept-until-fail|1e-5|0.7788007830714049"
  )
elif [[ "$MATRIX" == "smoke" ]]; then
  variants=(
    "0|fc-paperdecay-lr3e-6|fc|position-decay|3e-6|0.7788007830714049"
    "1|layers-paperdecay-lr1e-6|layers|position-decay|1e-6|0.7788007830714049"
    "2|all-paperdecay-lr1e-6|all-draft|position-decay|1e-6|0.7788007830714049"
    "3|all-auf-lr1e-6|all-draft|accept-until-fail|1e-6|0.7788007830714049"
  )
else
  echo "unknown MATRIX=$MATRIX (expected smoke or long)" >&2
  exit 1
fi

pids=()
for item in "${variants[@]}"; do
  IFS='|' read -r gpu label scope loss_mode lr decay <<< "$item"
  echo "launch gpu=$gpu label=$label scope=$scope loss=$loss_mode lr=$lr"
  run_variant "$gpu" "$label" "$scope" "$loss_mode" "$lr" "$decay" &
  pids+=("$!")
done

rc=0
for pid in "${pids[@]}"; do
  if ! wait "$pid"; then
    rc=1
  fi
done

printf 'DFlash adaptation root: %s\n' "$OUT_ROOT"
for summary in "$OUT_ROOT"/*/summary.json; do
  [[ -f "$summary" ]] || continue
  jq -r '[input_filename, .baseline.visible_tokens_per_step, .final.visible_tokens_per_step, (.final.visible_tokens_per_step - .baseline.visible_tokens_per_step)] | @tsv' "$summary"
done
exit "$rc"
