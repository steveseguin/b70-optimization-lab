#!/usr/bin/env bash
# Build the llama.cpp server used by this recipe: upstream llama.cpp c926ad098 plus one aggregate patch (the lab's
# B70 changes, the LFM2.5 exact fast-path kernels, the exact kernel fusions and a steadier prompt-path conversion).
# Needs git, cmake, ninja and Intel oneAPI (measured with 2026.1).
#
#   SOURCE_DIR=/path/to/new/dir repro/lfm25-24b-a2b-q8-b70/build.sh
#
# SOURCE_DIR must not exist yet. BUILD_JOBS (default 4) limits parallel compiles: each icpx job can use 1-2 GiB of RAM.
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/../.." && pwd)
source_dir=${SOURCE_DIR:-}
jobs=${BUILD_JOBS:-4}
base_commit=c926ad09857517978575d6a74d225b463f7417a0
patch_rel=patches/lfm25-24b-a2b-q8-b70/llama-cpp-c926ad098-lfm25-24b-a2b-exact-fused-prefill-20261015.diff.gz.b64
patch_sha=4b1a4cd014daafb74e2e44d2fc9c19e49d9d9e2626d1a29b998d919ce8d7af07

[[ -n ${source_dir} ]] || { echo 'Set SOURCE_DIR to a new, empty destination.' >&2; exit 2; }
[[ ! -e ${source_dir} ]] || { echo "Refusing to overwrite existing path: ${source_dir}" >&2; exit 2; }
[[ ${jobs} =~ ^[1-9][0-9]*$ ]] || { echo 'BUILD_JOBS must be a positive number.' >&2; exit 2; }
[[ -f /opt/intel/oneapi/setvars.sh ]] || { echo 'Intel oneAPI not found at /opt/intel/oneapi (install the Base Toolkit).' >&2; exit 1; }
build_dir=${BUILD_DIR:-${source_dir}/build}

decoded=$(mktemp)
trap 'rm -f "${decoded}"' EXIT
base64 -d "${repo_root}/${patch_rel}" | gzip -dc > "${decoded}"
echo "${patch_sha}  ${decoded}" | sha256sum --check --status || { echo 'Patch checksum mismatch.' >&2; exit 1; }

git clone --branch b9769 --depth 1 https://github.com/ggml-org/llama.cpp.git "${source_dir}"
[[ $(git -C "${source_dir}" rev-parse HEAD) == "${base_commit}" ]] || { echo 'Upstream commit mismatch after clone.' >&2; exit 1; }
git -C "${source_dir}" apply --check "${decoded}"
git -C "${source_dir}" apply "${decoded}"

set +u
# shellcheck disable=SC1091
source /opt/intel/oneapi/setvars.sh --force >/dev/null
set -u
cmake -S "${source_dir}" -B "${build_dir}" -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_COMPILER=icx -DCMAKE_CXX_COMPILER=icpx \
  -DCMAKE_CXX_FLAGS=-DGGML_SYCL_REORDER_Q8_0_VDR_MMVQ=2 \
  -DGGML_SYCL=ON -DGGML_SYCL_TARGET=INTEL -DGGML_SYCL_DEVICE_ARCH=bmg-g31 \
  -DGGML_SYCL_F16=ON -DGGML_SYCL_GRAPH=ON -DGGML_SYCL_DNN=ON -DGGML_SYCL_HOST_MEM_FALLBACK=ON \
  -DLLAMA_BUILD_UI=OFF -DLLAMA_USE_PREBUILT_UI=OFF
cmake --build "${build_dir}" --target llama-server llama-bench -j"${jobs}"

receipt=${build_dir}/lfm25-24b-a2b-build.json
cat > "${receipt}" <<EOF
{
  "base_commit": "${base_commit}",
  "aggregate_patch_sha256": "${patch_sha}",
  "icpx_version": "$(icpx --version | head -1)",
  "llama_server_sha256": "$(sha256sum "${build_dir}/bin/llama-server" | awk '{print $1}')"
}
EOF
printf 'BUILD COMPLETE\nllama-server: %s/bin/llama-server\nreceipt: %s\n' "${build_dir}" "${receipt}"
