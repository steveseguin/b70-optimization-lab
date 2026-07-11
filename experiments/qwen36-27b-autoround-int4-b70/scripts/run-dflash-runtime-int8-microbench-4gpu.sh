#!/usr/bin/env bash
set -euo pipefail

# Diagnostic only: benchmark actual DFlash checkpoint linears on four B70s.
repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
python_bin="${PYTHON_BIN:-/home/steve/.venvs/vllm-xpu/bin/python}"
kernels_dir="${VLLM_XPU_KERNELS_SRC:-/home/steve/src/vllm-xpu-kernels}"
stamp="${STAMP:-$(date -u +%Y%m%dT%H%M%SZ)}"
out_dir="${OUT_DIR:-$repo_dir/data/qwen36-27b-autoround-int4-b70-diagnostics}"
mkdir -p "$out_dir"

export LD_LIBRARY_PATH="$kernels_dir/vllm_xpu_kernels:/home/steve/.venvs/vllm-xpu/lib:/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/lib:${LD_LIBRARY_PATH:-}"

run_case() {
  local gpu="$1"
  local case_name="$2"
  ZE_AFFINITY_MASK="$gpu" \
  ONEAPI_DEVICE_SELECTOR="level_zero:0" \
  "$python_bin" \
    "$repo_dir/experiments/qwen36-27b-autoround-int4-b70/scripts/bench-dflash-runtime-int8.py" \
    --case "$case_name" \
    --output-json "$out_dir/qwen27-dflash-runtime-int8-${case_name}-${stamp}.json" \
    >"$out_dir/qwen27-dflash-runtime-int8-${case_name}-${stamp}.log" 2>&1
}

run_case 0 fc & p0=$!
run_case 1 qkv & p1=$!
run_case 2 gate_up & p2=$!
run_case 3 down & p3=$!

rc=0
for pid in "$p0" "$p1" "$p2" "$p3"; do
  if ! wait "$pid"; then
    rc=1
  fi
done

# o_proj is substantially smaller; reuse GPU 1 after qkv completes.
if ! run_case 1 o_proj; then
  rc=1
fi

echo "DFlash runtime INT8 microbench stamp=$stamp output=$out_dir"
for result in "$out_dir"/qwen27-dflash-runtime-int8-*"-$stamp.json"; do
  [[ -f "$result" ]] || continue
  jq -c '{case, weight_shape_out_in, results: [.results[] | {rows, bf16_ms: .bf16_linear.median_ms, int8_f32scale_ms: .w8a8_f32scale_quant_plus_gemm.median_ms, speedup: .w8a8_f32scale_quant_plus_gemm.speedup_vs_bf16, relative_rmse: .accuracy_f32scale.relative_rmse}]}' "$result"
done
exit "$rc"
