#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
build_root=${BUILD_ROOT:?set BUILD_ROOT to a new dedicated writable directory}
base_image=${BASE_IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-serial-attention-r49}
image=${IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-r55c-public-binaries}
release_base=https://github.com/steveseguin/b70-optimization-lab/releases/download/qwen38-fp8-tp2-r55c-20260901
dockerfile=${script_dir}/Dockerfile.mtp1-rebuilt-gdn

base_gdn_patch_sha256=ad583014c92b8611a9e4e87868a3d492c3b6802ee557814b9ec794f147cd973e
split_gdn_patch_sha256=40ca8c3fc15fea1b7dda8d268761f0b1339eb821f5d8357b3da7600585fe750f
wheel_sha256=fa0288ff90aa75fd182489659f41a11ca2b82bc1eca711ca1c992324cf74905b
xpu_extension_sha256=1632cafcf2afc0bc039dd49ebbb5eda4e62d626f4c20729aecd9e87874d1dc08
gdn_library_sha256=2c343620d689409bfa371a8b4c3db680e4786f23bc092411e7d03140f1b2a355
xpu_offload_device_code_sha256=023a45d0ab8363dd3d4538f7c171ca88e29afa68d048c74086439572e6d8678b
gdn_offload_device_code_sha256=88bf2317b00c74afc9700f3ca3a05fb3c260d69c2277d9dd9eca84a6dad03db7

for command_name in curl docker objcopy readelf sha256sum; do
  command -v "${command_name}" >/dev/null || {
    printf '%s is required\n' "${command_name}" >&2
    exit 1
  }
done
[[ -f "${dockerfile}" ]] || { printf 'missing Dockerfile: %s\n' "${dockerfile}" >&2; exit 1; }
[[ ! -e "${build_root}" ]] || {
  printf 'BUILD_ROOT must not already exist: %s\n' "${build_root}" >&2
  exit 1
}

"${script_dir}/verify-image-contract.sh" mtp1-serial-fa "${base_image}"
mkdir -p "${build_root}"

fetch() {
  local name=$1 expected=$2 partial
  partial=${build_root}/${name}.partial
  curl --fail --location --retry 4 --retry-all-errors \
    --output "${partial}" "${release_base}/${name}"
  [[ "$(sha256sum "${partial}" | awk '{print $1}')" == "${expected}" ]] || {
    printf 'release asset digest mismatch: %s\n' "${name}" >&2
    exit 1
  }
  mv "${partial}" "${build_root}/${name}"
}

fetch _xpu_C.abi3.so "${xpu_extension_sha256}"
fetch libgdn_attn_kernels_xe_2.so "${gdn_library_sha256}"

verify_offload_section() {
  local library=$1 expected=$2 section_file
  section_file=${build_root}/$(basename -- "${library}").OFFLOAD_DEVICE_CODE
  objcopy --dump-section "OFFLOAD_DEVICE_CODE=${section_file}" "${library}"
  [[ "$(sha256sum "${section_file}" | awk '{print $1}')" == "${expected}" ]] || {
    printf 'OFFLOAD_DEVICE_CODE digest mismatch: %s\n' "${library}" >&2
    exit 1
  }
  rm -f "${section_file}"
  readelf -d "${library}" | grep -Fq 'Library runpath: [$ORIGIN]' || {
    printf 'non-portable RUNPATH: %s\n' "${library}" >&2
    exit 1
  }
}

verify_offload_section "${build_root}/_xpu_C.abi3.so" \
  "${xpu_offload_device_code_sha256}"
verify_offload_section "${build_root}/libgdn_attn_kernels_xe_2.so" \
  "${gdn_offload_device_code_sha256}"

docker build --pull=false \
  --build-arg "BASE_IMAGE=${base_image}" \
  --build-arg "BASE_GDN_PATCH_SHA256=${base_gdn_patch_sha256}" \
  --build-arg "SPLIT_GDN_PATCH_SHA256=${split_gdn_patch_sha256}" \
  --build-arg "WHEEL_SHA256=${wheel_sha256}" \
  --build-arg "XPU_EXTENSION_SHA256=${xpu_extension_sha256}" \
  --build-arg "GDN_LIBRARY_SHA256=${gdn_library_sha256}" \
  --build-arg "XPU_OFFLOAD_DEVICE_CODE_SHA256=${xpu_offload_device_code_sha256}" \
  --build-arg "GDN_OFFLOAD_DEVICE_CODE_SHA256=${gdn_offload_device_code_sha256}" \
  --file "${dockerfile}" --tag "${image}" "${build_root}"

"${script_dir}/verify-image-contract.sh" mtp1-serial-fa-split-gdn "${image}"
printf 'PUBLIC R55C BINARY IMAGE COMPLETE\nimage=%s\nimage_id=%s\n' \
  "${image}" "$(docker image inspect "${image}" --format '{{.Id}}')"
