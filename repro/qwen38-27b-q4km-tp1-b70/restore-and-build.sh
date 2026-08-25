#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/../.." && pwd)
source_dir="${SOURCE_DIR:-}"
jobs="${BUILD_JOBS:-2}"
compiler="${CXX_COMPILER:-/opt/intel/oneapi/compiler/2026.0/bin/icpx}"

[[ -n "${source_dir}" ]] || {
    printf 'Set SOURCE_DIR to a new, empty destination directory.\n' >&2
    exit 2
}
[[ ! -e "${source_dir}" ]] || {
    printf 'Refusing to overwrite existing path: %s\n' "${source_dir}" >&2
    exit 2
}
[[ "${jobs}" =~ ^[1-9][0-9]*$ ]] || { printf 'BUILD_JOBS must be positive.\n' >&2; exit 2; }
[[ -r /opt/intel/oneapi/setvars.sh ]] || {
    printf 'Missing Intel oneAPI environment: /opt/intel/oneapi/setvars.sh\n' >&2
    exit 1
}
# CMake needs IntelSYCL, MKL, and their package roots in addition to icpx.
# A direct compiler path alone is not sufficient in a fresh shell.
set +u
# shellcheck disable=SC1091
source /opt/intel/oneapi/setvars.sh >/dev/null 2>&1
set -u
[[ -x "${compiler}" ]] || {
    printf 'Missing compiler: %s\n' "${compiler}" >&2
    exit 1
}

printf 'compiler=%s\n' "${compiler}"
"${compiler}" --version | sed -n '1,2p'

git clone https://github.com/mndodd/llama.cpp.git "${source_dir}"
git -C "${source_dir}" checkout 4302fb59969a5d8cf9f8e5f55fdd4506d0ed2126

apply_b64_patch() {
    local artifact=$1 expected=$2 decoded
    decoded=$(mktemp)
    trap 'rm -f "${decoded}"' RETURN
    base64 -d "${repo_root}/${artifact}" | gzip -dc > "${decoded}"
    printf '%s  %s\n' "${expected}" "${decoded}" | sha256sum --check --status || {
        printf 'Decoded patch identity mismatch: %s\n' "${artifact}" >&2
        return 1
    }
    git -C "${source_dir}" apply --check "${decoded}"
    git -C "${source_dir}" apply "${decoded}"
    rm -f "${decoded}"
    trap - RETURN
}

apply_b64_patch \
  patches/qwen36-27b-q8-tp2-asrock-b70/llama-cpp-mndodd-4302fb599-lab-tp2-dp4a2-20260815.diff.gz.b64 \
  f21e9b557c3d024527ac98d5f189cf7ea72fa8c38a5faf2a22ee339fd1988998
apply_b64_patch \
  patches/qwen38-27b-q4km-tp2-asrock-b70/llama-cpp-q4k-mmvq-swiglu-tp2-20260815.diff.gz.b64 \
  0a27858525f6a402cf9c92d1b93daee0a80e2ffaef9137bf7bce784a549b58b6
apply_b64_patch \
  patches/qwen38-27b-q4km-tp1-b70s/llama-cpp-tp1-gdn-state-io-widen-20260821.diff.gz.b64 \
  1377fd89ea595f4d6e0654ce07387f9e0c2438f6677360c4c94cd99072ce6272
apply_b64_patch \
  patches/qwen38-27b-q4km-tp1-b70s/llama-cpp-tp1-conv-qk-widen-20260821.diff.gz.b64 \
  5b0141e3ef6be67365e638ef796247e25280b1bf1e7c11e61c77aba0657fcb7b
apply_b64_patch \
  patches/qwen38-27b-q4km-tp1-b70s/llama-cpp-tp1-qk-norm-rope-src-widen-20260821.diff.gz.b64 \
  8299e77c2186bc2d024c1a9030ed69aafcad26442296a68523dde1a1b6d46c7e
apply_b64_patch \
  patches/qwen38-27b-q4km-tp1-b70s/llama-cpp-tp1-q8out-rejected-memo320-20260821.diff.gz.b64 \
  717bc1cc3eda198ded7df4e2a0046fd1ce88434c47e702feecaf4dff258142d0

git -C "${source_dir}" diff --check
cmake -G "Unix Makefiles" -S "${source_dir}" -B "${source_dir}/build-sycl-aot-bmg-g31" \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_C_COMPILER=/usr/bin/cc \
  -DCMAKE_CXX_COMPILER="${compiler}" \
  -DBUILD_SHARED_LIBS=ON \
  -DGGML_NATIVE=ON \
  -DLLAMA_CURL=OFF \
  -DLLAMA_BUILD_UI=OFF \
  -DLLAMA_USE_PREBUILT_UI=OFF \
  -DGGML_SYCL=ON \
  -DGGML_SYCL_TARGET=INTEL \
  -DGGML_SYCL_DEVICE_ARCH=bmg_g31 \
  -DGGML_SYCL_F16=ON \
  -DGGML_SYCL_GRAPH=OFF \
  -DGGML_SYCL_DNN=OFF \
  -DGGML_SYCL_HOST_MEM_FALLBACK=OFF \
  -DGGML_SYCL_SUPPORT_LEVEL_ZERO_API=ON
cmake --build "${source_dir}/build-sycl-aot-bmg-g31" \
  --target llama-batched-bench llama-bench llama-server -j"${jobs}"

printf 'BUILD COMPLETE\nsource=%s\nbuild=%s\n' \
  "${source_dir}" "${source_dir}/build-sycl-aot-bmg-g31"
