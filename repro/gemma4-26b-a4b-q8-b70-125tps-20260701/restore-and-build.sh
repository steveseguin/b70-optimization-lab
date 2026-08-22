#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/../.." && pwd)
source_dir=${SOURCE_DIR:-}
build_dir=${BUILD_DIR:-}
jobs=${BUILD_JOBS:-2}
base_commit=c926ad09857517978575d6a74d225b463f7417a0
patch_rel=patches/gemma4-26b-a4b-q8-b70/llama-cpp-c926ad098-gemma4-q8-record-source-20260701.diff.gz.b64
patch_sha=2dab9dce3d6a41cba8edad559eb754088c6f5ca1de6531f408c069e45b7f727a

[[ -n ${source_dir} ]] || { printf 'Set SOURCE_DIR to a new, empty destination.\n' >&2; exit 2; }
[[ ! -e ${source_dir} ]] || { printf 'Refusing to overwrite existing path: %s\n' "${source_dir}" >&2; exit 2; }
[[ ${jobs} =~ ^[1-9][0-9]*$ ]] || { printf 'BUILD_JOBS must be positive.\n' >&2; exit 2; }
build_dir=${build_dir:-${source_dir}/build-sycl-b70-aot-bmg-g31-q8reorder-vdr2}

icx=${ICX:-/opt/intel/oneapi/compiler/2026.0/bin/icx}
icpx=${ICPX:-/opt/intel/oneapi/compiler/2026.0/bin/icpx}
[[ -x ${icx} && -x ${icpx} ]] || {
    printf 'The record toolchain was oneAPI 2026.0. Set ICX/ICPX only for a clearly labeled compatibility rebuild.\n' >&2
    exit 1
}

git clone --branch b9769 --depth 1 https://github.com/ggml-org/llama.cpp.git "${source_dir}"
[[ $(git -C "${source_dir}" rev-parse HEAD) == "${base_commit}" ]] || {
    printf 'Base commit mismatch after clone.\n' >&2
    exit 1
}

decoded=$(mktemp)
cleanup() { rm -f "${decoded}"; }
trap cleanup EXIT
base64 -d "${repo_root}/${patch_rel}" | gzip -dc > "${decoded}"
printf '%s  %s\n' "${patch_sha}" "${decoded}" | sha256sum --check --status || {
    printf 'Decoded aggregate patch hash mismatch.\n' >&2
    exit 1
}
git -C "${source_dir}" apply --check "${decoded}"
git -C "${source_dir}" apply "${decoded}"
git -C "${source_dir}" diff --check

set +u
# shellcheck disable=SC1091
source /opt/intel/oneapi/setvars.sh --force >/dev/null
set -u
cmake -S "${source_dir}" -B "${build_dir}" -G Ninja \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_C_COMPILER="${icx}" \
  -DCMAKE_CXX_COMPILER="${icpx}" \
  -DCMAKE_CXX_FLAGS=-DGGML_SYCL_REORDER_Q8_0_VDR_MMVQ=2 \
  -DGGML_SYCL=ON -DGGML_SYCL_TARGET=INTEL \
  -DGGML_SYCL_DEVICE_ARCH=bmg-g31 \
  -DGGML_SYCL_F16=ON -DGGML_SYCL_GRAPH=ON -DGGML_SYCL_DNN=ON \
  -DGGML_SYCL_HOST_MEM_FALLBACK=ON \
  -DLLAMA_BUILD_UI=OFF -DLLAMA_USE_PREBUILT_UI=OFF
cmake --build "${build_dir}" --target llama-server llama-quantize -j"${jobs}"

receipt=${build_dir}/b70-gemma4-record-source.json
server_sha=$(sha256sum "${build_dir}/bin/llama-server" | awk '{print $1}')
cat > "${receipt}" <<EOF
{
  "base_commit": "${base_commit}",
  "aggregate_patch_sha256": "${patch_sha}",
  "compiler_c": "${icx}",
  "compiler_cxx": "${icpx}",
  "vdr_mmvq": 2,
  "llama_server_sha256": "${server_sha}",
  "historical_binary_identity": false
}
EOF
printf 'BUILD COMPLETE\nsource=%s\nbuild=%s\nreceipt=%s\n' "${source_dir}" "${build_dir}" "${receipt}"
