#!/usr/bin/env bash
set -euo pipefail

# Diagnostic only: four shards of the fixed realistic corpus, no endpoint
# throughput and never LocalMaxxing eligible.
if [[ "${QWEN27_DFLASH_MTP_LEAF_SNAPSHOT:-0}" != "1" ]]; then
  repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
  snapshot="$(mktemp /tmp/qwen27-dflash-mtp-leaf.XXXXXX.sh)"
  cp "${BASH_SOURCE[0]}" "$snapshot"
  exec env QWEN27_DFLASH_MTP_LEAF_SNAPSHOT=1 \
    QWEN27_DFLASH_MTP_LEAF_REPO="$repo_dir" bash "$snapshot" "$@"
fi
trap 'rm -f "${BASH_SOURCE[0]}"' EXIT

repo_dir="${QWEN27_DFLASH_MTP_LEAF_REPO:?missing repo path}"
cd "$repo_dir"
STAMP="${STAMP:-$(date -u +%Y%m%dT%H%M%SZ)}"
OUT_ROOT="${OUT_ROOT:-/mnt/usb-models/llm-optimization-artifacts/qwen27-dflash/mtp-leaf-oracle-$STAMP}"
TRACKED_OUT="${TRACKED_OUT:-$repo_dir/experiments/qwen36-27b-autoround-int4-b70/diagnostics/qwen27-dflash-mtp-leaf-oracle-$STAMP.json}"
mkdir -p "$OUT_ROOT"

pids=()
for gpu in 0 1 2 3; do
  shard="$OUT_ROOT/shard-$gpu"
  mkdir -p "$shard/tmp" "$shard/cache"
  (
    export ZE_AFFINITY_MASK="$gpu"
    export ONEAPI_DEVICE_SELECTOR=level_zero:0
    export PYTORCH_ALLOC_CONF=expandable_segments:True
    export TMPDIR="$shard/tmp"
    export TORCHINDUCTOR_CACHE_DIR="$shard/cache/torchinductor"
    export TRITON_CACHE_DIR="$shard/cache/triton"
    /home/steve/.venvs/vllm-xpu/bin/python \
      scripts/evaluate-qwen27-dflash-mtp-leaf-oracle.py \
      --shard-index "$gpu" --num-shards 4 \
      --out "$shard/report.json" \
      >"$shard/stdout.log" 2>"$shard/stderr.log"
  ) &
  pids+=("$!")
done

rc=0
for pid in "${pids[@]}"; do
  if ! wait "$pid"; then
    rc=1
  fi
done
if [[ "$rc" != "0" ]]; then
  echo "one or more DFlash+MTP oracle shards failed: $OUT_ROOT" >&2
  exit "$rc"
fi

merge_args=()
for gpu in 0 1 2 3; do
  merge_args+=(--merge-report "$OUT_ROOT/shard-$gpu/report.json")
done
/home/steve/.venvs/vllm-xpu/bin/python \
  scripts/evaluate-qwen27-dflash-mtp-leaf-oracle.py \
  "${merge_args[@]}" --out "$TRACKED_OUT"

echo "DFlash+MTP leaf oracle: $TRACKED_OUT"
jq '{classification, summary}' "$TRACKED_OUT"
