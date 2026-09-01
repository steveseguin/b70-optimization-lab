#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/../.." && pwd)
build_root=${BUILD_ROOT:?set BUILD_ROOT to a new empty local build directory}
image=${IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-compiled-allreduce-custom-op-r60}
base_image=${BASE_IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-serial-fa-split-gdn-r50-reprocheck-r55c}
expected_base_id=${EXPECTED_BASE_IMAGE_ID:-sha256:41aec5da9b124497a9b5dbc6b38f17175bf923d930d5702b9913589f107802d4}
patch_file=${repo_root}/experiments/qwen38-27b-b70/patches/vllm-qwen38-xpu-compiled-allreduce-custom-op-r60-20260901.patch
dockerfile=${script_dir}/Dockerfile.compiled-allreduce-custom-op-r60
source_rel=vllm/distributed/device_communicators/xpu_communicator.py

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
[[ ! -e "${build_root}" ]] || {
  printf 'BUILD_ROOT must not already exist: %s\n' "${build_root}" >&2
  exit 1
}

"${script_dir}/verify-image-contract.sh" mtp1-serial-fa-split-gdn "${base_image}"
[[ "$(docker image inspect "${base_image}" --format '{{.Id}}')" == "${expected_base_id}" ]] || {
  printf 'base image identity mismatch\n' >&2
  exit 1
}

mkdir -p "${build_root}/$(dirname -- "${source_rel}")"
container=$(docker create "${base_image}")
cleanup() { docker rm -f "${container}" >/dev/null 2>&1 || true; }
trap cleanup EXIT INT TERM
docker cp \
  "${container}:/opt/venv/lib/python3.12/site-packages/${source_rel}" \
  "${build_root}/${source_rel}"
cleanup
trap - EXIT INT TERM

patch --directory="${build_root}" --strip=1 --forward --batch <"${patch_file}"
source_sha256=$(sha256sum "${build_root}/${source_rel}" | awk '{print $1}')
patch_sha256=$(sha256sum "${patch_file}" | awk '{print $1}')

docker build --pull=false \
  --build-arg "BASE_IMAGE=${base_image}" \
  --build-arg "XPU_COMMUNICATOR_SHA256=${source_sha256}" \
  --build-arg "CUSTOM_OP_PATCH_SHA256=${patch_sha256}" \
  --file "${dockerfile}" --tag "${image}" "${build_root}"

observed=$(docker run --rm --entrypoint sha256sum "${image}" \
  "/opt/venv/lib/python3.12/site-packages/${source_rel}" | awk '{print $1}')
[[ "${observed}" == "${source_sha256}" ]] || {
  printf 'built communicator hash mismatch\n' >&2
  exit 1
}
printf 'image=%s\nimage_id=%s\nxpu_communicator_sha256=%s\npatch_sha256=%s\n' \
  "${image}" "$(docker image inspect "${image}" --format '{{.Id}}')" \
  "${source_sha256}" "${patch_sha256}"
