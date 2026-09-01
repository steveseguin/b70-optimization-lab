#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/../.." && pwd)
artifact_dir=${KERNEL_ARTIFACT_DIR:?set KERNEL_ARTIFACT_DIR to the directory containing the two pinned R50 kernel binaries}
image=${IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-serial-fa-split-gdn-r50}
base_image=${BASE_IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-serial-attention-r49}
expected_base_id=${EXPECTED_BASE_IMAGE_ID:-sha256:a5cee2544c5ec3c68f50dee87ba05e530e05b7c9630d68efaf592f4de596833e}
base_gdn_patch=${repo_root}/experiments/qwen38-27b-b70/patches/vllm-xpu-kernels-qwen38-dynamic-active-width-serial-gdn-r35-20260828.patch
split_gdn_patch=${repo_root}/experiments/qwen38-27b-b70/patches/vllm-xpu-kernels-qwen38-gdn-split-serial-gates-r50-20260901.patch
base_gdn_patch_sha256=ad583014c92b8611a9e4e87868a3d492c3b6802ee557814b9ec794f147cd973e
split_gdn_patch_sha256=40ca8c3fc15fea1b7dda8d268761f0b1339eb821f5d8357b3da7600585fe750f
xpu_extension_sha256=f8013aff50f815b290cbec87d7926936c3fae9daacad6e1cf1f4c01ca60180ef
gdn_library_sha256=32a13caab7d56e6b584b7396ff61b3755a60362e6647db26337b98fdbd0bb4ec
dockerfile=${script_dir}/Dockerfile.mtp1-split-gdn

for command_name in docker sha256sum; do
  command -v "${command_name}" >/dev/null || {
    printf '%s is required\n' "${command_name}" >&2
    exit 1
  }
done
for required in "${dockerfile}" "${base_gdn_patch}" "${split_gdn_patch}" \
  "${artifact_dir}/_xpu_C.abi3.so" \
  "${artifact_dir}/libgdn_attn_kernels_xe_2.so"; do
  [[ -f "${required}" ]] || { printf 'missing build input: %s\n' "${required}" >&2; exit 1; }
done
[[ "$(sha256sum "${base_gdn_patch}" | awk '{print $1}')" == "${base_gdn_patch_sha256}" ]] || {
  printf 'base GDN patch digest mismatch\n' >&2
  exit 1
}
[[ "$(sha256sum "${split_gdn_patch}" | awk '{print $1}')" == "${split_gdn_patch_sha256}" ]] || {
  printf 'split GDN patch digest mismatch\n' >&2
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
  printf 'R49 base image identity mismatch\n' >&2
  exit 1
}

docker build --pull=false \
  --build-arg "BASE_IMAGE=${base_image}" \
  --build-arg "BASE_GDN_PATCH_SHA256=${base_gdn_patch_sha256}" \
  --build-arg "SPLIT_GDN_PATCH_SHA256=${split_gdn_patch_sha256}" \
  --build-arg "XPU_EXTENSION_SHA256=${xpu_extension_sha256}" \
  --build-arg "GDN_LIBRARY_SHA256=${gdn_library_sha256}" \
  --file "${dockerfile}" --tag "${image}" "${artifact_dir}"

printf 'image=%s\nimage_id=%s\n' \
  "${image}" "$(docker image inspect "${image}" --format '{{.Id}}')"
