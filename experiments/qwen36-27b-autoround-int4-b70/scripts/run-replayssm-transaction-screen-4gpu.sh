#!/usr/bin/env bash
set -euo pipefail

# Four-lane strict-fresh screen for low-risk ReplaySSM transaction fusions.
# Quality is intentionally deferred until a lane beats controls outside noise.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
STAMP="${STAMP:-$(date -u +%Y%m%dT%H%M%SZ)}"
EXTENSION="${XPU_C_EXTENSION:-/tmp/vllm-xpu-qwen27-replayssm-transaction-20260710/vllm_xpu_kernels/_xpu_C.abi3.so}"
SOURCE_PACKAGE="${SOURCE_PACKAGE:-/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels}"
MATRIX_DIR="${MATRIX_DIR:-/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/replayssm-transaction-screen-$STAMP}"
OVERLAY_ROOT="$MATRIX_DIR/kernel-overlay"
STAGGER_S="${STAGGER_S:-90}"
LAYOUT="${LAYOUT:-screen}"

if [[ ! -f "$EXTENSION" ]]; then
  echo "Candidate extension not found: $EXTENSION" >&2
  exit 2
fi

mkdir -p "$MATRIX_DIR" "$OVERLAY_ROOT/vllm_xpu_kernels"
for item in \
  __init__.py \
  flash_attn_interface.py \
  fused_moe_interface.py \
  _mx_utils.py \
  _C.abi3.so \
  _moe_C.abi3.so \
  _vllm_fa2_C.abi3.so \
  libattn_kernels_xe_2.so \
  libgdn_attn_kernels_xe_2.so \
  libgrouped_gemm_xe_2.so; do
  ln -s "$SOURCE_PACKAGE/$item" "$OVERLAY_ROOT/vllm_xpu_kernels/$item"
done
ln -s "$EXTENSION" "$OVERLAY_ROOT/vllm_xpu_kernels/_xpu_C.abi3.so"

cat > "$MATRIX_DIR/matrix.env" <<EOF
classification=strict_fresh_diagnostic_no_quality_not_headline
date_utc=$STAMP
xpu_c_extension=$EXTENSION
overlay_root=$OVERLAY_ROOT
stagger_s=$STAGGER_S
layout=$LAYOUT
EOF

run_lane() {
  local gpu="$1"
  local port="$2"
  local lane="$3"
  local fuse_pending="$4"
  local direct_out="$5"

  GPU_INDEX="$gpu" \
  PORT="$port" \
  LABEL="qwen27-replayssm-transaction-$lane-$STAMP" \
  RUN_DIR="$MATRIX_DIR/$lane/run" \
  BENCH_OUT="$MATRIX_DIR/$lane/bench.json" \
  SMOKE_OUT="$MATRIX_DIR/$lane/smoke.json" \
  QUALITY_OUT="$MATRIX_DIR/$lane/quality.json" \
  SUMMARY_OUT="$MATRIX_DIR/$lane/summary.json" \
  VLLM_XPU_KERNELS_SRC="$OVERLAY_ROOT" \
  PYTHONPATH="$OVERLAY_ROOT${PYTHONPATH:+:$PYTHONPATH}" \
  RUN_QUALITY=0 \
  VLLM_XPU_GDN_REPLAYSSM_SPEC=1 \
  VLLM_XPU_GDN_REPLAYSSM_SPEC_CACHE_LEN=8 \
  VLLM_XPU_GDN_REPLAYSSM_TORCH_FALLBACK=0 \
  VLLM_XPU_GDN_REPLAYSSM_STAGE_CONV_TORCH_FALLBACK=0 \
  VLLM_XPU_GDN_REPLAYSSM_COMMIT_IN_FORWARD=1 \
  VLLM_XPU_GDN_REPLAYSSM_SLOT_MGMT_TORCH_FALLBACK=1 \
  VLLM_XPU_GDN_REPLAYSSM_FUSE_PENDING_METADATA="$fuse_pending" \
  VLLM_XPU_GDN_REPLAYSSM_DIRECT_CORE_OUT="$direct_out" \
  VLLM_XPU_LM_HEAD_INT8=1 \
  VLLM_XPU_LM_HEAD_INT8_SCALE_DTYPE=bf16 \
  VLLM_XPU_DRAFT_LM_HEAD_INT4=1 \
  VLLM_XPU_DRAFT_LM_HEAD_INT4_GROUP_SIZE=128 \
  VLLM_XPU_DRAFT_LM_HEAD_INT4_SCALE_DTYPE=bf16 \
  bash "$ROOT/experiments/qwen36-27b-autoround-int4-b70/scripts/run-vllm-candidate.sh" \
    > "$MATRIX_DIR/$lane.stdout.log" 2>&1
}

case "$LAYOUT" in
  screen)
    lane_specs=(
      "0|19480|control|0|0"
      "1|19481|pending|1|0"
      "2|19482|direct|0|1"
      "3|19483|both|1|1"
    )
    ;;
  crossover)
    lane_specs=(
      "0|19480|both-gpu0|1|1"
      "1|19481|control-gpu1|0|0"
      "2|19482|both-gpu2|1|1"
      "3|19483|control-gpu3|0|0"
    )
    ;;
  crossover-reverse)
    lane_specs=(
      "0|19480|control-gpu0|0|0"
      "1|19481|both-gpu1|1|1"
      "2|19482|control-gpu2|0|0"
      "3|19483|both-gpu3|1|1"
    )
    ;;
  *)
    echo "Unsupported LAYOUT=$LAYOUT" >&2
    echo "Expected screen, crossover, or crossover-reverse" >&2
    exit 2
    ;;
esac

declare -a pids=()
declare -a lanes=()
for i in "${!lane_specs[@]}"; do
  IFS='|' read -r gpu port lane fuse_pending direct_out \
    <<< "${lane_specs[$i]}"
  run_lane "$gpu" "$port" "$lane" "$fuse_pending" "$direct_out" &
  pids+=("$!")
  lanes+=("$lane")
  if (( i + 1 < ${#lane_specs[@]} )); then
    sleep "$STAGGER_S"
  fi
done

rc=0
for i in "${!pids[@]}"; do
  if ! wait "${pids[$i]}"; then
    echo "lane ${lanes[$i]} failed; see $MATRIX_DIR/${lanes[$i]}.stdout.log" >&2
    rc=1
  fi
done

python3 - "$MATRIX_DIR" "${lanes[@]}" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
rows = []
for lane in sys.argv[2:]:
    path = root / lane / "summary.json"
    if not path.exists():
        rows.append({"lane": lane, "status": "missing", "path": str(path)})
        continue
    payload = json.loads(path.read_text())
    rows.append({
        "lane": lane,
        "status": payload.get("status"),
        "primary_metric": payload.get("primary_metric"),
        "ttft_ms": payload.get("ttft_ms"),
        "summary": str(path),
    })
out = {
    "classification": "strict_fresh_diagnostic_no_quality_not_headline",
    "localmaxxing_eligible": False,
    "rows": rows,
}
(root / "matrix-summary.json").write_text(
    json.dumps(out, indent=2, sort_keys=True) + "\n")
print(json.dumps(out, indent=2, sort_keys=True))
PY

echo "$MATRIX_DIR"
exit "$rc"
