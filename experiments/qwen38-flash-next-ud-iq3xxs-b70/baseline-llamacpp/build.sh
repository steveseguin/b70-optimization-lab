#!/usr/bin/env bash
# CPU compilation only. Never runs the built applications or device discovery.
set -euo pipefail
root=/home/steve/build/flash-next-iq3-baseline-20261010
src=$root/llama.cpp
build=$root/build
commit=23b0202a189c44a54625aadcb37a946dd1d6278d
export OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
export ONEAPI_ROOT=/opt/intel/oneapi
export PATH=/opt/intel/oneapi/compiler/2026.0/bin:/usr/local/bin:/usr/bin:/bin
export LD_LIBRARY_PATH=/opt/intel/oneapi/compiler/2026.0/lib:/opt/intel/oneapi/mkl/2026.0/lib:/opt/intel/oneapi/tbb/2023.0/lib
export MKLROOT=/opt/intel/oneapi/mkl/2026.0
export CMAKE_PREFIX_PATH=/opt/intel/oneapi/compiler/2026.0:/opt/intel/oneapi/mkl/2026.0
mkdir -p "$root"
if [[ ! -d $src/.git ]]; then
    git clone --no-checkout --depth 1 https://github.com/ggml-org/llama.cpp.git "$src"
    git -C "$src" fetch --depth 1 origin "$commit"
    git -C "$src" checkout --detach "$commit"
fi
[[ $(git -C "$src" rev-parse HEAD) == "$commit" ]] || git -C "$src" checkout --detach "$commit"
[[ -z $(git -C "$src" status --porcelain) ]] || { echo 'Source is dirty' >&2; exit 1; }
nice -n 19 cmake -S "$src" -B "$build" -G Ninja \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_C_COMPILER=/usr/bin/cc \
    -DCMAKE_CXX_COMPILER=/opt/intel/oneapi/compiler/2026.0/bin/icpx \
    -DMKL_DIR=/opt/intel/oneapi/mkl/2026.0/lib/cmake/mkl \
    -DTBB_DIR=/opt/intel/oneapi/tbb/2023.0/lib/cmake/tbb \
    -DGGML_CCACHE=OFF \
    -DBUILD_SHARED_LIBS=ON -DGGML_NATIVE=ON \
    -DLLAMA_BUILD_TESTS=OFF -DLLAMA_BUILD_UI=OFF -DLLAMA_USE_PREBUILT_UI=OFF \
    -DGGML_SYCL=ON -DGGML_SYCL_TARGET=INTEL \
    -DGGML_SYCL_DEVICE_ARCH=bmg_g31 -DGGML_SYCL_F16=OFF \
    -DGGML_SYCL_GRAPH=OFF -DGGML_SYCL_DNN=OFF \
    -DGGML_SYCL_HOST_MEM_FALLBACK=OFF -DGGML_SYCL_SUPPORT_LEVEL_ZERO_API=ON \
    > "$root/configure.log" 2>&1
nice -n 19 cmake --build "$build" --parallel 8 --target llama-cli llama-completion \
    > "$root/build.log" 2>&1
