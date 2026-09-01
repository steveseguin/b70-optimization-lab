#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/../.." && pwd)
build_root=${BUILD_ROOT:?set BUILD_ROOT to a new empty local build directory}
base_image=${BASE_IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-gdn-retained-lowering-r99}
expected_base_id=${EXPECTED_BASE_IMAGE_ID:-sha256:a2e09416d1f55da2b71ffefbbec7db7d6581089b33ed125c6ea3ed147050eaf8}
image=${IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-gdn-runtime-metadata-selector-r100}
patch_file=${repo_root}/experiments/qwen38-27b-b70/patches/vllm-qwen38-fp8-gdn-runtime-metadata-selector-r100-20260901.patch
operator_check=${script_dir}/check-gdn-runtime-metadata-selector-r100.py
expected_patch_sha256=3d52a55146a6d0c7e44c0f6e99585bb5c206ff45ff56357b99658aa8d9e9d917
dockerfile=${script_dir}/Dockerfile.gdn-runtime-metadata-selector-r100

for command_name in docker patch sha256sum; do
  command -v "${command_name}" >/dev/null || {
    printf 'ERROR: required command is missing: %s\n' "${command_name}" >&2
    exit 2
  }
done
for required in "${dockerfile}" "${patch_file}" "${operator_check}"; do
  [[ -f "${required}" ]] || {
    printf 'ERROR: missing build input: %s\n' "${required}" >&2
    exit 2
  }
done
[[ "$(sha256sum "${patch_file}" | awk '{print $1}')" == "${expected_patch_sha256}" ]] || {
  printf 'ERROR: R100 runtime-selector patch mismatch\n' >&2
  exit 2
}
[[ "$(docker image inspect "${base_image}" --format '{{.Id}}')" == "${expected_base_id}" ]] || {
  printf 'ERROR: R99 base image mismatch\n' >&2
  exit 2
}
[[ ! -e "${build_root}" ]] || {
  printf 'ERROR: BUILD_ROOT must not already exist: %s\n' "${build_root}" >&2
  exit 2
}

mkdir -p "${build_root}"
install -m 0644 "${patch_file}" "${build_root}/$(basename -- "${patch_file}")"
install -m 0644 "${operator_check}" "${build_root}/$(basename -- "${operator_check}")"

docker build --pull=false \
  --build-arg "BASE_IMAGE=${base_image}" \
  --build-arg "GDN_RUNTIME_SELECTOR_PATCH_SHA256=${expected_patch_sha256}" \
  --file "${dockerfile}" --tag "${image}" "${build_root}"

observed=$(docker run --rm --entrypoint sha256sum "${image}" \
  /opt/venv/lib/python3.12/site-packages/vllm/model_executor/layers/mamba/gdn/qwen_gdn_linear_attn.py | awk '{print $1}')
printf '%s\n' \
  "image=${image}" \
  "image_id=$(docker image inspect "${image}" --format '{{.Id}}')" \
  "patch_sha256=${expected_patch_sha256}" \
  "installed_qwen_gdn_sha256=${observed}"
