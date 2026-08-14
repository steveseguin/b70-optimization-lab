#!/usr/bin/env bash
set -euo pipefail

source_root=${LLAMA_CPP_ROOT:-"$HOME/src/llama.cpp-muse-q8-woq-repro"}
build_dir=${MUSE_BUILD_DIR:-"$source_root/build-sycl-b70-aot-bmg-g31"}
jobs=${JOBS:-2}

set +u
source /opt/intel/oneapi/setvars.sh --force >/dev/null
set -u

cmake -S "$source_root" -B "$build_dir" -G "Unix Makefiles" \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_C_COMPILER=icx \
    -DCMAKE_CXX_COMPILER=icpx \
    -DBUILD_SHARED_LIBS=ON \
    -DGGML_NATIVE=ON \
    -DGGML_OPENMP=ON \
    -DGGML_SYCL=ON \
    -DGGML_SYCL_TARGET=INTEL \
    -DGGML_SYCL_DEVICE_ARCH=bmg-g31 \
    -DGGML_SYCL_DNN=ON \
    -DGGML_SYCL_GRAPH=ON \
    -DGGML_SYCL_F16=OFF \
    -DGGML_SYCL_HOST_MEM_FALLBACK=ON \
    -DGGML_SYCL_SUPPORT_LEVEL_ZERO_API=ON \
    -DLLAMA_BUILD_SERVER=ON \
    -DLLAMA_BUILD_TESTS=ON \
    -DLLAMA_BUILD_TOOLS=ON \
    -DCMAKE_EXPORT_COMPILE_COMMANDS=ON
cmake --build "$build_dir" --target llama-server -j "$jobs"
"$build_dir/bin/llama-server" --version
sha256sum "$build_dir/bin/llama-server" \
    "$build_dir/bin/libggml-sycl.so.0.19.0" \
    "$build_dir/bin/libllama-server-impl.so"

cat <<'EOF'
Cross-host compiler/build IDs can change binary hashes. Source patch, model
hashes, runtime identity, output gates, and measured results remain mandatory.
The record-host binary hashes are in manifests/source.json.
EOF
