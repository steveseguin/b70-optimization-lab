#!/usr/bin/env bash
set -euo pipefail

source_dir="${SOURCE_DIR:-}"
build_dir="${BUILD_DIR:-}"
jobs="${BUILD_JOBS:-2}"
compiler="${CXX_COMPILER:-/opt/intel/oneapi/compiler/2026.1/bin/icpx}"
expected_rev=4302fb59969a5d8cf9f8e5f55fdd4506d0ed2126
expected_diff="${EXPECTED_DIFF_SHA:-f24d58bfddb12e7263c2b6974ce8fe2114b47d831f57fe329207ec0edb2f705e}"

fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
[[ -n "${source_dir}" && -n "${build_dir}" ]] || fail 'set SOURCE_DIR and BUILD_DIR'
[[ ! -e "${build_dir}" ]] || fail "BUILD_DIR must not exist: ${build_dir}"
[[ "${jobs}" =~ ^[1-9][0-9]*$ ]] || fail 'BUILD_JOBS must be positive'
[[ "${expected_diff}" =~ ^[0-9a-f]{64}$ ]] || fail 'EXPECTED_DIFF_SHA must be SHA-256'
[[ -x "${compiler}" ]] || fail "missing compiler: ${compiler}"
[[ -r /opt/intel/oneapi/setvars.sh ]] || fail 'missing /opt/intel/oneapi/setvars.sh'
[[ "$(git -C "${source_dir}" rev-parse HEAD)" == "${expected_rev}" ]] || \
  fail 'source revision mismatch'
git -C "${source_dir}" diff --check
actual_diff=$(git -C "${source_dir}" diff --binary | sha256sum | awk '{print $1}')
[[ "${actual_diff}" == "${expected_diff}" ]] || fail "source diff mismatch: ${actual_diff}"

set +u
# shellcheck disable=SC1091
source /opt/intel/oneapi/setvars.sh --force >/dev/null 2>&1
set -u

cmake -G "Unix Makefiles" -S "${source_dir}" -B "${build_dir}" \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_C_COMPILER=/usr/bin/cc \
  -DCMAKE_CXX_COMPILER="${compiler}" \
  -DCMAKE_CXX_FLAGS=-DGGML_SYCL_Q4K_NIBBLE_PLANE=1 \
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
  -DGGML_SYCL_DNN=ON \
  -DGGML_SYCL_HOST_MEM_FALLBACK=OFF \
  -DGGML_SYCL_SUPPORT_LEVEL_ZERO_API=ON
cmake --build "${build_dir}" --target llama-batched-bench -j"${jobs}"

grep -qx 'GGML_SYCL_DNN:BOOL=ON' "${build_dir}/CMakeCache.txt"
grep -Eq '^CMAKE_CXX_FLAGS:STRING=.*GGML_SYCL_Q4K_NIBBLE_PLANE=1' \
  "${build_dir}/CMakeCache.txt"
if ldd "${build_dir}/bin/libggml-sycl.so" | grep -q 'not found'; then
  fail 'built SYCL backend has unresolved libraries'
fi
sha256sum "${build_dir}/bin/llama-batched-bench" "${build_dir}/bin/libggml-sycl.so"
printf 'BUILD PASS: %s\n' "${build_dir}"
