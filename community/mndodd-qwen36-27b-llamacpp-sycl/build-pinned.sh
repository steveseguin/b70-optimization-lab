#!/usr/bin/env bash
set -euo pipefail

ENTRY_DIR=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
LLAMA_ROOT=${LLAMA_ROOT:-/mnt/fast-ai/src/llama.cpp-mndodd-4302fb59}
BUILD_DIR=${BUILD_DIR:-$LLAMA_ROOT/build-sycl-aot-bmg-g31}
JOBS=${JOBS:-2}
FORK_URL=https://github.com/mndodd/llama.cpp.git
FORK_COMMIT=4302fb59969a5d8cf9f8e5f55fdd4506d0ed2126
PATCH=$ENTRY_DIR/patches/0001-asrock-lab-lowram-dnnless-tp2.patch

if [[ ${ALLOW_BUILD_WITH_MODEL:-0} != 1 ]] && pgrep -x llama-server >/dev/null; then
    printf 'Refusing to overlap BMG AOT compilation with a live llama-server.\n' >&2
    printf 'Stop the model service first; the lab observed a GPU reset from this overlap.\n' >&2
    exit 1
fi

if [[ -e "$LLAMA_ROOT" ]]; then
    printf 'Refusing to alter existing path: %s\nChoose a new LLAMA_ROOT.\n' "$LLAMA_ROOT" >&2
    exit 1
fi

git clone --filter=blob:none --branch intel-sycl-optimization "$FORK_URL" "$LLAMA_ROOT"
git -C "$LLAMA_ROOT" checkout --detach "$FORK_COMMIT"
git -C "$LLAMA_ROOT" apply --unidiff-zero --check "$PATCH"
git -C "$LLAMA_ROOT" apply --unidiff-zero "$PATCH"

set +u
source /opt/intel/oneapi/tbb/2023.1/env/vars.sh >/dev/null
source /opt/intel/oneapi/compiler/2026.1/env/vars.sh >/dev/null
source /opt/intel/oneapi/mkl/2026.1/env/vars.sh >/dev/null
source /opt/intel/oneapi/umf/1.0/env/vars.sh >/dev/null
set -u

cmake --fresh -S "$LLAMA_ROOT" -B "$BUILD_DIR" \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_CXX_COMPILER=/opt/intel/oneapi/compiler/2026.1/bin/icpx \
    -DGGML_BACKEND_DL=OFF \
    -DGGML_SYCL=ON \
    -DGGML_SYCL_TARGET=INTEL \
    -DGGML_SYCL_DEVICE_ARCH=bmg_g31 \
    -DGGML_SYCL_F16=ON \
    -DGGML_SYCL_GRAPH=OFF \
    -DGGML_SYCL_DNN=OFF \
    -DGGML_SYCL_SUPPORT_LEVEL_ZERO_API=ON \
    -DGGML_SYCL_HOST_MEM_FALLBACK=OFF \
    -DLLAMA_CURL=OFF \
    -DLLAMA_BUILD_UI=OFF \
    -DLLAMA_USE_PREBUILT_UI=OFF

cmake --build "$BUILD_DIR" --target llama-bench llama-cli llama-server llama-perplexity -j "$JOBS"

git -C "$LLAMA_ROOT" status --short
sha256sum \
    "$BUILD_DIR/bin/llama-bench" \
    "$BUILD_DIR/bin/llama-server" \
    "$BUILD_DIR/bin/libggml-sycl.so"
