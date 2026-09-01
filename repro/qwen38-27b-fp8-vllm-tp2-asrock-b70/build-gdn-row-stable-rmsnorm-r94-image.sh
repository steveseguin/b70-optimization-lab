#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/../.." && pwd)
build_root=${BUILD_ROOT:?set BUILD_ROOT to a new empty local build directory}
base_image=${BASE_IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-gdn-prefill-output-trace-r90}
expected_base_id=${EXPECTED_BASE_IMAGE_ID:-sha256:14ffb2f9c46bd5621563c0a39d53edffeb9b9d85513782ad8d8d1f160d43f744}
image=${IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-gdn-row-stable-rmsnorm-r94}
patch_file=${repo_root}/experiments/qwen38-27b-b70/patches/vllm-qwen38-fp8-gdn-row-stable-rmsnorm-r94-20260901.patch
operator_check=${script_dir}/check-gdn-row-stable-rmsnorm-r94.py
expected_patch_sha256=16bf2d0647a357e2faa058e2c1381ee4751ca20f6153e7921382582c423e1ed9
dockerfile=${script_dir}/Dockerfile.gdn-row-stable-rmsnorm-r94

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
  printf 'ERROR: R94 row-stable RMSNorm patch mismatch\n' >&2
  exit 2
}
[[ "$(docker image inspect "${base_image}" --format '{{.Id}}')" == "${expected_base_id}" ]] || {
  printf 'ERROR: R90 base image mismatch\n' >&2
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
  --build-arg "GDN_ROW_STABLE_RMSNORM_PATCH_SHA256=${expected_patch_sha256}" \
  --file "${dockerfile}" --tag "${image}" "${build_root}"

observed=$(docker run --rm --entrypoint sha256sum "${image}" \
  /opt/venv/lib/python3.12/site-packages/vllm/model_executor/layers/mamba/gdn/qwen_gdn_linear_attn.py | awk '{print $1}')
printf '%s\n' \
  "image=${image}" \
  "image_id=$(docker image inspect "${image}" --format '{{.Id}}')" \
  "patch_sha256=${expected_patch_sha256}" \
  "installed_qwen_gdn_sha256=${observed}"
