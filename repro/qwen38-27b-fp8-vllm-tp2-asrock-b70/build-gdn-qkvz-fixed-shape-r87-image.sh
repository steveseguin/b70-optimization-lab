#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/../.." && pwd)
build_root=${BUILD_ROOT:?set BUILD_ROOT to a new empty local build directory}
base_image=${BASE_IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-gdn-prefill-input-trace-r86}
expected_base_id=${EXPECTED_BASE_IMAGE_ID:-sha256:3655f4fcdbe387117a6fcf2b58efacd9c8e8e65eb825b0a961e26c91f1952110}
image=${IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-gdn-qkvz-fixed-shape-r87}
patch_file=${repo_root}/experiments/qwen38-27b-b70/patches/vllm-qwen38-fp8-gdn-qkvz-fixed-shape-r87-20260901.patch
expected_patch_sha256=c6384af1eaa45f0f49318f78c82a3f7485db19ebe3f5fe6f63c8f5bcafccf3a5
dockerfile=${script_dir}/Dockerfile.gdn-qkvz-fixed-shape-r87

for command_name in docker patch sha256sum; do
  command -v "${command_name}" >/dev/null || {
    printf 'ERROR: required command is missing: %s\n' "${command_name}" >&2
    exit 2
  }
done
for required in "${dockerfile}" "${patch_file}"; do
  [[ -f "${required}" ]] || {
    printf 'ERROR: missing build input: %s\n' "${required}" >&2
    exit 2
  }
done
[[ "$(sha256sum "${patch_file}" | awk '{print $1}')" == "${expected_patch_sha256}" ]] || {
  printf 'ERROR: R87 fixed-shape qkvz patch mismatch\n' >&2
  exit 2
}
[[ "$(docker image inspect "${base_image}" --format '{{.Id}}')" == "${expected_base_id}" ]] || {
  printf 'ERROR: R86 base image mismatch\n' >&2
  exit 2
}
[[ ! -e "${build_root}" ]] || {
  printf 'ERROR: BUILD_ROOT must not already exist: %s\n' "${build_root}" >&2
  exit 2
}

mkdir -p "${build_root}"
install -m 0644 "${patch_file}" "${build_root}/$(basename -- "${patch_file}")"

docker build --pull=false \
  --build-arg "BASE_IMAGE=${base_image}" \
  --build-arg "GDN_QKVZ_PATCH_SHA256=${expected_patch_sha256}" \
  --file "${dockerfile}" --tag "${image}" "${build_root}"

observed=$(docker run --rm --entrypoint sha256sum "${image}" \
  /opt/venv/lib/python3.12/site-packages/vllm/model_executor/layers/mamba/gdn/qwen_gdn_linear_attn.py | awk '{print $1}')
printf '%s\n' \
  "image=${image}" \
  "image_id=$(docker image inspect "${image}" --format '{{.Id}}')" \
  "patch_sha256=${expected_patch_sha256}" \
  "installed_qwen_gdn_sha256=${observed}"
