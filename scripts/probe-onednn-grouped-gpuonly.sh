#!/usr/bin/env bash
set -euo pipefail

VLLM_XPU_KERNELS_DIR="${VLLM_XPU_KERNELS_DIR:-/home/steve/src/vllm-xpu-kernels}"
ONEAPI_COMPILER_ROOT="${ONEAPI_COMPILER_ROOT:-/opt/intel/oneapi/compiler/2025.3}"
BUILD_DIR="${BUILD_DIR:-$VLLM_XPU_KERNELS_DIR/build/onednn-grouped-matmul-gpuonly-20260612c}"
PROBE_BIN="${PROBE_BIN:-/tmp/qwen36-onednn-matmul-grouped-example-20260612d}"
DEVICE_SELECTOR="${DEVICE_SELECTOR:-level_zero:0}"
MAX_JOBS="${MAX_JOBS:-4}"

source "$ONEAPI_COMPILER_ROOT/env/vars.sh" >/tmp/oneapi-compiler2025-onednn-gpuonly-probe-vars.log 2>&1 || true

cmake -S "$VLLM_XPU_KERNELS_DIR/third_party/oneDNN" -B "$BUILD_DIR" -G Ninja \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_C_COMPILER="$ONEAPI_COMPILER_ROOT/bin/icx" \
  -DCMAKE_CXX_COMPILER="$ONEAPI_COMPILER_ROOT/bin/icpx" \
  -DDNNL_EXPERIMENTAL_GROUPED_MEMORY=ON \
  '-DDNNL_ENABLE_PRIMITIVE=MATMUL;SDPA' \
  -DDNNL_ENABLE_PRIMITIVE_GPU_ISA=XE2 \
  -DDNNL_GPU_RUNTIME=SYCL \
  -DDNNL_CPU_RUNTIME=NONE \
  -DDNNL_BUILD_TESTS=OFF \
  -DDNNL_BUILD_EXAMPLES=OFF \
  -DONEDNN_BUILD_GRAPH=OFF \
  -DDNNL_LIBRARY_TYPE=STATIC

cmake --build "$BUILD_DIR" --target dnnl -j "$MAX_JOBS"

"$ONEAPI_COMPILER_ROOT/bin/icpx" -std=c++17 -O2 -fsycl \
  -I"$VLLM_XPU_KERNELS_DIR/third_party/oneDNN/examples" \
  -I"$BUILD_DIR/include" \
  -I"$VLLM_XPU_KERNELS_DIR/third_party/oneDNN/include" \
  "$VLLM_XPU_KERNELS_DIR/third_party/oneDNN/examples/matmul_grouped.cpp" \
  "$BUILD_DIR/src/libdnnl.a" \
  -lpthread -ldl \
  -o "$PROBE_BIN"

export LD_LIBRARY_PATH="$ONEAPI_COMPILER_ROOT/lib:/opt/intel/oneapi/umf/1.1/lib:/opt/intel/oneapi/tcm/1.5/lib:/opt/intel/oneapi/tbb/2023.0/lib/intel64/gcc4.8:${LD_LIBRARY_PATH:-}"
export PATH="$ONEAPI_COMPILER_ROOT/bin:${PATH}"

sycl-ls | head -40
ONEAPI_DEVICE_SELECTOR="$DEVICE_SELECTOR" "$PROBE_BIN" gpu
