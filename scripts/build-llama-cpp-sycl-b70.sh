#!/usr/bin/env bash
set -euo pipefail

LLAMA_CPP_DIR="${LLAMA_CPP_DIR:-/home/steve/src/llama.cpp}"
LLAMA_CPP_REPO="${LLAMA_CPP_REPO:-https://github.com/ggml-org/llama.cpp.git}"
BUILD_DIR="${BUILD_DIR:-$LLAMA_CPP_DIR/build-sycl-b70}"
BUILD_TYPE="${BUILD_TYPE:-Release}"
GGML_SYCL_F16="${GGML_SYCL_F16:-ON}"
GGML_SYCL_DEVICE_ARCH="${GGML_SYCL_DEVICE_ARCH:-}"
JOBS="${JOBS:-$(nproc)}"

if [[ ! -d "$LLAMA_CPP_DIR/.git" ]]; then
  git clone "$LLAMA_CPP_REPO" "$LLAMA_CPP_DIR"
fi

if [[ -f /opt/intel/oneapi/setvars.sh ]]; then
  # shellcheck disable=SC1091
  set +u
  source /opt/intel/oneapi/setvars.sh --force >/dev/null
  set -u
fi

command -v icx >/dev/null
command -v icpx >/dev/null
command -v cmake >/dev/null

CMAKE_ARGS=(
  -S "$LLAMA_CPP_DIR"
  -B "$BUILD_DIR"
  -G Ninja
  -DCMAKE_BUILD_TYPE="$BUILD_TYPE"
  -DCMAKE_C_COMPILER=icx
  -DCMAKE_CXX_COMPILER=icpx
  -DGGML_SYCL=ON
  -DGGML_SYCL_F16="$GGML_SYCL_F16"
)

if [[ -n "$GGML_SYCL_DEVICE_ARCH" ]]; then
  CMAKE_ARGS+=(-DGGML_SYCL_DEVICE_ARCH="$GGML_SYCL_DEVICE_ARCH")
fi

cmake "${CMAKE_ARGS[@]}"

cmake --build "$BUILD_DIR" -j "$JOBS" --target llama-server llama-cli llama-bench

echo "$BUILD_DIR/bin/llama-server"
