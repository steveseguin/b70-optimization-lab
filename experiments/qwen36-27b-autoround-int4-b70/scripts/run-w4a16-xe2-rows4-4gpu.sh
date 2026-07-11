#!/usr/bin/env bash
set -euo pipefail

# Cross-GPU microbenchmark of oneDNN versus Xe2 DPAS W4A16 at the Qwen27
# MTP3 verifier shape. Diagnostic only; never a LocalMaxxing result.
repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$repo_dir"

STAMP="${STAMP:-$(date -u +%Y%m%dT%H%M%SZ)}"
OUT_DIR="${OUT_DIR:-$repo_dir/experiments/qwen36-27b-autoround-int4-b70/diagnostics}"
KERNEL_PREFIX="${KERNEL_PREFIX:-/home/steve/src/vllm-xpu-kernels}"
PYTHON="${PYTHON:-/home/steve/.venvs/vllm-xpu/bin/python}"
mkdir -p "$OUT_DIR"

run_lane() {
  local gpu="$1"
  local output="$OUT_DIR/qwen27-w4a16-xe2-rows4-gpu${gpu}-${STAMP}.json"
  local log="$OUT_DIR/qwen27-w4a16-xe2-rows4-gpu${gpu}-${STAMP}.log"
  (
    export ZE_AFFINITY_MASK="$gpu"
    export ONEAPI_DEVICE_SELECTOR=level_zero:0
    export LD_LIBRARY_PATH="$KERNEL_PREFIX/vllm_xpu_kernels:/home/steve/.venvs/vllm-xpu/lib:/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/lib:${LD_LIBRARY_PATH:-}"
    "$PYTHON" scripts/bench-qwen27-w4a16-xe2-dense.py \
      --device xpu:0 \
      --rows 4 \
      --warmup 20 \
      --iterations 100 \
      --calls-per-sample 16 \
      --seed $((20260711 + gpu * 100003)) \
      --kernel-prefix "$KERNEL_PREFIX" \
      --output-json "$output" \
      >"$log" 2>&1
  )
}

pids=()
for gpu in 0 1 2 3; do
  run_lane "$gpu" &
  pids+=("$!")
done

rc=0
for pid in "${pids[@]}"; do
  if ! wait "$pid"; then
    rc=1
  fi
done

for gpu in 0 1 2 3; do
  output="$OUT_DIR/qwen27-w4a16-xe2-rows4-gpu${gpu}-${STAMP}.json"
  if [[ -f "$output" ]]; then
    jq -c '{gpu:'"$gpu"', projected:.projected_target_step[0], qkvz:(.results[] | select(.name == "gdn_qkvz") | .rows[0])}' "$output"
  else
    echo "missing output for gpu=$gpu" >&2
  fi
done
exit "$rc"
