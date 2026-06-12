#!/usr/bin/env bash
set -euo pipefail

VLLM_XPU_KERNELS_DIR="${VLLM_XPU_KERNELS_DIR:-/home/steve/src/vllm-xpu-kernels}"
ONEAPI_COMPILER_ROOT="${ONEAPI_COMPILER_ROOT:-/opt/intel/oneapi/compiler/2025.3}"
BUILD_DIR="${BUILD_DIR:-$VLLM_XPU_KERNELS_DIR/build/onednn-grouped-matmul-gpuonly-20260612c}"
RUNNER_SRC="${RUNNER_SRC:-/home/steve/llm-optimizations/tools/onednn_moe_island_resident_runner.cpp}"
RUNNER_BIN="${RUNNER_BIN:-/tmp/qwen36-onednn-moe-island-resident-20260612-${BASHPID:-$$}}"
DEVICE_SELECTOR="${DEVICE_SELECTOR:-level_zero:0}"
COMPILE_ONLY=0
if [[ "${1:-}" == "--compile-only" ]]; then
  COMPILE_ONLY=1
fi

set +u
source "$ONEAPI_COMPILER_ROOT/env/vars.sh" >/tmp/oneapi-compiler2025-onednn-moe-island-vars.log 2>&1 || true
set -u

if [[ "${ONEDNN_SKIP_COMPILE:-0}" != "1" || ! -x "$RUNNER_BIN" ]]; then
  "$ONEAPI_COMPILER_ROOT/bin/icpx" -std=c++17 -O2 -fsycl \
    -I"$VLLM_XPU_KERNELS_DIR/third_party/oneDNN/examples" \
    -I"$BUILD_DIR/include" \
    -I"$VLLM_XPU_KERNELS_DIR/third_party/oneDNN/include" \
    "$RUNNER_SRC" \
    "$BUILD_DIR/src/libdnnl.a" \
    -lpthread -ldl \
    -o "$RUNNER_BIN"
fi

if [[ "$COMPILE_ONLY" == "1" ]]; then
  echo "compiled $RUNNER_BIN"
  exit 0
fi

if [[ -z "${ONEDNN_GEMM1_META:-}" || -z "${ONEDNN_GEMM2_META:-}" ]]; then
  echo "ONEDNN_GEMM1_META and ONEDNN_GEMM2_META are required" >&2
  exit 2
fi

export LD_LIBRARY_PATH="$ONEAPI_COMPILER_ROOT/lib:/opt/intel/oneapi/umf/1.1/lib:/opt/intel/oneapi/tcm/1.5/lib:/opt/intel/oneapi/tbb/2023.0/lib/intel64/gcc4.8:${LD_LIBRARY_PATH:-}"
export PATH="$ONEAPI_COMPILER_ROOT/bin:${PATH}"

ONEAPI_DEVICE_SELECTOR="$DEVICE_SELECTOR" "$RUNNER_BIN" gpu
