#!/usr/bin/env bash
set -euo pipefail

MULTIWINDOW_DIR="${1:-data/qwen36-onednn-moe-island-layer9-r1-multiwindow-20260612bc}"
MANIFEST="${MANIFEST:-$MULTIWINDOW_DIR/resident_multiwindow_manifest.csv}"
OUT_JSON="${OUT_JSON:-$MULTIWINDOW_DIR/resident_multiwindow_pair_result.json}"
WARMUP="${WARMUP:-40}"
ITERATIONS="${ITERATIONS:-400}"

if [[ ! -d "$MULTIWINDOW_DIR" ]]; then
  echo "missing multi-window directory: $MULTIWINDOW_DIR" >&2
  exit 2
fi

tmp_manifest="${MANIFEST}.tmp"
: > "$tmp_manifest"
while IFS= read -r -d '' window_dir; do
  if [[ ! -f "$window_dir/gemm1.meta" || ! -f "$window_dir/gemm2.meta" ]]; then
    echo "missing gemm metadata under $window_dir" >&2
    exit 2
  fi
  printf '%s,%s\n' \
    "$(realpath --relative-to "$(dirname "$MANIFEST")" "$window_dir/gemm1.meta")" \
    "$(realpath --relative-to "$(dirname "$MANIFEST")" "$window_dir/gemm2.meta")" \
    >> "$tmp_manifest"
done < <(find "$MULTIWINDOW_DIR" -maxdepth 1 -type d -name 'window_*' -print0 | sort -z)
mv "$tmp_manifest" "$MANIFEST"

ONEDNN_WINDOW_MANIFEST="$MANIFEST" \
ONEDNN_PAIR_JSON="$OUT_JSON" \
ONEDNN_PAIR_WARMUP="$WARMUP" \
ONEDNN_PAIR_ITERATIONS="$ITERATIONS" \
bash scripts/run-onednn-moe-island-resident.sh
