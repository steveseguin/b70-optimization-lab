#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/../.." && pwd)
artifact_dir=${KERNEL_ARTIFACT_DIR:?set KERNEL_ARTIFACT_DIR to the directory containing the two pinned R35 kernel binaries}
image=${IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-serial-gdn-r46}
base_image=${BASE_IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-rms-serial-r31}
expected_base_id=${EXPECTED_BASE_IMAGE_ID:-sha256:ba42e928e69c60d1c9102df6ec1c0e998e9dd8463f74d5dc0a8b4bb45108fa9b}
kernel_patch=${repo_root}/experiments/qwen38-27b-b70/patches/vllm-xpu-kernels-qwen38-dynamic-active-width-serial-gdn-r35-20260828.patch
kernel_patch_sha256=ad583014c92b8611a9e4e87868a3d492c3b6802ee557814b9ec794f147cd973e
xpu_extension_sha256=a190f22ccd9b2b6e638d7e0bc57e8a67946064219768d697a134786e8f6ee12d
gdn_library_sha256=2c343620d689409bfa371a8b4c3db680e4786f23bc092411e7d03140f1b2a355
dockerfile=${script_dir}/Dockerfile.mtp1-serial-gdn

for command_name in docker sha256sum; do
  command -v "${command_name}" >/dev/null || {
    printf '%s is required\n' "${command_name}" >&2
    exit 1
  }
done
for required in "${dockerfile}" "${kernel_patch}" \
  "${artifact_dir}/_xpu_C.abi3.so" \
  "${artifact_dir}/libgdn_attn_kernels_xe_2.so"; do
  [[ -f "${required}" ]] || { printf 'missing build input: %s\n' "${required}" >&2; exit 1; }
done
[[ "$(sha256sum "${kernel_patch}" | awk '{print $1}')" == "${kernel_patch_sha256}" ]] || {
  printf 'kernel patch digest mismatch\n' >&2
  exit 1
}
[[ "$(sha256sum "${artifact_dir}/_xpu_C.abi3.so" | awk '{print $1}')" == "${xpu_extension_sha256}" ]] || {
  printf 'XPU extension digest mismatch\n' >&2
  exit 1
}
[[ "$(sha256sum "${artifact_dir}/libgdn_attn_kernels_xe_2.so" | awk '{print $1}')" == "${gdn_library_sha256}" ]] || {
  printf 'GDN library digest mismatch\n' >&2
  exit 1
}
[[ "$(docker image inspect "${base_image}" --format '{{.Id}}')" == "${expected_base_id}" ]] || {
  printf 'qualified MTP1 base image identity mismatch\n' >&2
  exit 1
}

docker build --pull=false \
  --build-arg "BASE_IMAGE=${base_image}" \
  --build-arg "KERNEL_PATCH_SHA256=${kernel_patch_sha256}" \
  --build-arg "XPU_EXTENSION_SHA256=${xpu_extension_sha256}" \
  --build-arg "GDN_LIBRARY_SHA256=${gdn_library_sha256}" \
  --file "${dockerfile}" --tag "${image}" "${artifact_dir}"

printf 'image=%s\nimage_id=%s\n' \
  "${image}" "$(docker image inspect "${image}" --format '{{.Id}}')"
