#!/usr/bin/env bash
# Public-binary route for the R139 row-invariant W8A16 profile: download the
# released _xpu_C.abi3.so, verify its whole-file and section digests against
# the values frozen here (identical to the from-source route's output), and
# install it over an independently built R62 base image. No compiler needed.
# From-source alternative: build-fixed-k-w8a16-r139-image.sh (host oneAPI 2026.1).
set -euo pipefail
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
build_root=${BUILD_ROOT:?set BUILD_ROOT to a new empty local build directory}
base_image=${BASE_IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-draft-only-int4-r62}
expected_base_id=${EXPECTED_BASE_IMAGE_ID:?set EXPECTED_BASE_IMAGE_ID to your independently built R62 image ID (docker image inspect ... --format '{{.Id}}')}
image=${IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-fixed-k-w8a16-r139}
release=${RELEASE_URL:-https://github.com/steveseguin/b70-optimization-lab/releases/download/qwen38-fp8-tp2-r139-20260902}
dockerfile=${script_dir}/Dockerfile.fixed-k-w8a16-r139
expected_xpu_sha256=f912e12de1d79206221142c9a50af2aba70d2c77c735c9cd2d5d8d9def0740d1
expected_xpu_text_sha256=f3a2e478245e12305b1675e3a2fe861f35af6743cf9c1d1aa8c833b0c0272376
expected_xpu_rodata_sha256=d39aedf6e2d68986a08da5d44b23800b682ebf4a4adf8969897c180fb3a514d1
expected_xpu_data_sha256=bce7187e3514ac122931330901c16e5c315f01f3fd260b2a123166bacf6aadd9
expected_xpu_offload_sha256=84661a68aeed81f44ce1ccc5581faa27c033e019a408017d893c6c7158bbb2c7
expected_fixed_k_sha256=5d2a93f0a36fa89f0ef13cf21ed5332a72491dd5856519bbe2eb21414112464f
expected_c_align_sha256=feb4f125f69b36dbc3f579ad93743abe655678b7540ba2743fcff797fe35ebd9
expected_gdn_sha256_a=2c343620d689409bfa371a8b4c3db680e4786f23bc092411e7d03140f1b2a355
expected_gdn_sha256_b=32a13caab7d56e6b584b7396ff61b3755a60362e6647db26337b98fdbd0bb4ec
for command_name in docker curl objcopy readelf sha256sum; do
  command -v "${command_name}" >/dev/null || { printf 'ERROR: missing %s\n' "${command_name}" >&2; exit 2; }
done
[[ -f "${dockerfile}" ]] || { printf 'ERROR: missing %s\n' "${dockerfile}" >&2; exit 2; }
[[ "$(docker image inspect "${base_image}" --format '{{.Id}}')" == "${expected_base_id}" ]] || { printf 'ERROR: R62 base image ID mismatch\n' >&2; exit 2; }
observed_gdn=$(docker run --rm --network none --entrypoint sha256sum "${base_image}" /opt/venv/lib/python3.12/site-packages/vllm_xpu_kernels/libgdn_attn_kernels_xe_2.so | awk '{print $1}')
[[ "${observed_gdn}" == "${expected_gdn_sha256_a}" || "${observed_gdn}" == "${expected_gdn_sha256_b}" ]] || { printf 'ERROR: base image GDN library is not a validated build: %s\n' "${observed_gdn}" >&2; exit 2; }
[[ ! -e "${build_root}" ]] || { printf 'ERROR: BUILD_ROOT must not already exist: %s\n' "${build_root}" >&2; exit 2; }
mkdir -p "${build_root}/context"
curl -fsSL --retry 3 -o "${build_root}/context/_xpu_C.abi3.so" "${release}/_xpu_C.abi3.so"
[[ "$(sha256sum "${build_root}/context/_xpu_C.abi3.so" | awk '{print $1}')" == "${expected_xpu_sha256}" ]] || { printf 'ERROR: downloaded _xpu_C.abi3.so digest mismatch\n' >&2; exit 2; }
verify_section() {
  local section=$1 expected=$2 out=${build_root}/section.bin
  objcopy --dump-section "${section}=${out}" "${build_root}/context/_xpu_C.abi3.so"
  [[ "$(sha256sum "${out}" | awk '{print $1}')" == "${expected}" ]] || { printf 'ERROR: section digest mismatch: %s\n' "${section}" >&2; exit 2; }
  rm -f "${out}"
}
verify_section .text "${expected_xpu_text_sha256}"
verify_section .rodata "${expected_xpu_rodata_sha256}"
verify_section .data "${expected_xpu_data_sha256}"
verify_section OFFLOAD_DEVICE_CODE "${expected_xpu_offload_sha256}"
readelf -d "${build_root}/context/_xpu_C.abi3.so" | grep -Fq 'Library runpath: [$ORIGIN]' || { printf 'ERROR: non-portable RUNPATH\n' >&2; exit 2; }
docker build --pull=false \
  --build-arg "BASE_IMAGE=${base_image}" \
  --build-arg "XPU_EXTENSION_SHA256=${expected_xpu_sha256}" \
  --build-arg "ONEDNN_PATCH_SHA256=${expected_fixed_k_sha256}+${expected_c_align_sha256}" \
  --file "${dockerfile}" --tag "${image}" "${build_root}/context"
docker run --rm --network none --entrypoint /bin/bash "${image}" -lc \
  'python -c "import torch; import vllm_xpu_kernels._xpu_C; print(torch.__version__)"'
printf 'image=%s\nimage_id=%s\nxpu_extension_sha256=%s\n' "${image}" "$(docker image inspect "${image}" --format '{{.Id}}')" "${expected_xpu_sha256}"
