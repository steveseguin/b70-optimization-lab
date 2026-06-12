#!/usr/bin/env bash
set -euo pipefail

VLLM_XPU_KERNELS_DIR="${VLLM_XPU_KERNELS_DIR:-/home/steve/src/vllm-xpu-kernels}"
ONEAPI_COMPILER_ROOT="${ONEAPI_COMPILER_ROOT:-/opt/intel/oneapi/compiler/2025.3}"
BUILD_DIR="${BUILD_DIR:-$VLLM_XPU_KERNELS_DIR/build/onednn-grouped-matmul-gpuonly-20260612c}"
PROBE_SRC="${PROBE_SRC:-/home/steve/llm-optimizations/tools/onednn_grouped_int8_dtype_probe.cpp}"
PROBE_BIN="${PROBE_BIN:-/tmp/qwen36-onednn-grouped-int8-dtype-probe-20260612au}"
DEVICE_SELECTOR="${DEVICE_SELECTOR:-level_zero:0}"

set +u
source "$ONEAPI_COMPILER_ROOT/env/vars.sh" >/tmp/oneapi-compiler2025-onednn-int8-probe-vars.log 2>&1 || true
set -u

"$ONEAPI_COMPILER_ROOT/bin/icpx" -std=c++17 -O2 -fsycl \
  -I"$VLLM_XPU_KERNELS_DIR/third_party/oneDNN/examples" \
  -I"$BUILD_DIR/include" \
  -I"$VLLM_XPU_KERNELS_DIR/third_party/oneDNN/include" \
  "$PROBE_SRC" \
  "$BUILD_DIR/src/libdnnl.a" \
  -lpthread -ldl \
  -o "$PROBE_BIN"

export LD_LIBRARY_PATH="$ONEAPI_COMPILER_ROOT/lib:/opt/intel/oneapi/umf/1.1/lib:/opt/intel/oneapi/tcm/1.5/lib:/opt/intel/oneapi/tbb/2023.0/lib/intel64/gcc4.8:${LD_LIBRARY_PATH:-}"
export PATH="$ONEAPI_COMPILER_ROOT/bin:${PATH}"

ONEAPI_DEVICE_SELECTOR="$DEVICE_SELECTOR" "$PROBE_BIN" gpu
