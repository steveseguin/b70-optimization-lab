#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/../.." && pwd)
build_root=${BUILD_ROOT:?set BUILD_ROOT to a new empty local build directory}
image=${IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-global-exact-head-repair-r71}
base_image=${BASE_IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-global-top-token-repair-r69}
expected_base_id=${EXPECTED_BASE_IMAGE_ID:-sha256:c5eed78d05513746fc70f285b64eaf34620bfa6b49bea9d379d740a36d9926fc}
patch_file=${repo_root}/experiments/qwen38-27b-b70/patches/vllm-qwen38-fp8-global-exact-head-repair-r71-20260901.patch
dockerfile=${script_dir}/Dockerfile.global-exact-head-repair-r71
expected_base_sha256=575e9b76e48ce95328e6a72418bd6ecbffacb0e582e80217cbf9c42030aa8f18
expected_patch_sha256=1796e4ecc6b10cd26f164ccc67f4bc4bf1f976388bfd05e948ab1753c083748a
source_rel=vllm/model_executor/layers/logits_processor.py

for command_name in docker patch sha256sum; do
  command -v "${command_name}" >/dev/null || {
    printf '%s is required\n' "${command_name}" >&2
    exit 1
  }
done
for required in "${patch_file}" "${dockerfile}"; do
  [[ -f "${required}" ]] || {
    printf 'missing build input: %s\n' "${required}" >&2
    exit 1
  }
done
[[ "$(sha256sum "${patch_file}" | awk '{print $1}')" == "${expected_patch_sha256}" ]] || {
  printf 'global exact-head repair patch identity mismatch\n' >&2
  exit 1
}
[[ ! -e "${build_root}" ]] || {
  printf 'BUILD_ROOT must not already exist: %s\n' "${build_root}" >&2
  exit 1
}
[[ "$(docker image inspect "${base_image}" --format '{{.Id}}')" == "${expected_base_id}" ]] || {
  printf 'base image identity mismatch\n' >&2
  exit 1
}

mkdir -p "${build_root}/$(dirname -- "${source_rel}")"
container=$(docker create "${base_image}")
cleanup() { docker rm -f "${container}" >/dev/null 2>&1 || true; }
trap cleanup EXIT INT TERM
docker cp "${container}:/opt/venv/lib/python3.12/site-packages/${source_rel}" "${build_root}/${source_rel}"
cleanup
trap - EXIT INT TERM
[[ "$(sha256sum "${build_root}/${source_rel}" | awk '{print $1}')" == "${expected_base_sha256}" ]] || {
  printf 'base source identity mismatch: %s\n' "${source_rel}" >&2
  exit 1
}
patch --directory="${build_root}" --strip=1 --forward --batch <"${patch_file}"
source_sha256=$(sha256sum "${build_root}/${source_rel}" | awk '{print $1}')

docker build --pull=false \
  --build-arg "BASE_IMAGE=${base_image}" \
  --build-arg "LOGITS_PROCESSOR_SOURCE_SHA256=${source_sha256}" \
  --build-arg "GLOBAL_EXACT_HEAD_REPAIR_PATCH_SHA256=${expected_patch_sha256}" \
  --file "${dockerfile}" --tag "${image}" "${build_root}"
observed=$(docker run --rm --entrypoint sha256sum "${image}" "/opt/venv/lib/python3.12/site-packages/${source_rel}" | awk '{print $1}')
[[ "${observed}" == "${source_sha256}" ]] || {
  printf 'built logits processor source hash mismatch\n' >&2
  exit 1
}
printf 'image=%s\nimage_id=%s\nsource_sha256=%s\npatch_sha256=%s\n' \
  "${image}" "$(docker image inspect "${image}" --format '{{.Id}}')" \
  "${source_sha256}" "${expected_patch_sha256}"
