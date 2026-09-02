#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/../.." && pwd)
build_root=${BUILD_ROOT:?set BUILD_ROOT to a new empty local build directory}
base_image=${BASE_IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-gdn-projection-isolation-trace-r108}
expected_base_id=${EXPECTED_BASE_IMAGE_ID:-sha256:e08ee7a313c912d8a645a71f7d88d9e436784d0f8e35d69a5fe4fe94f6a3bed4}
image=${IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-decoder-boundary-trace-r110}
patch_file=${repo_root}/experiments/qwen38-27b-b70/patches/vllm-qwen38-fp8-decoder-boundary-trace-r110-20260902.patch
validator=${repo_root}/tools/validate-qwen-decoder-boundary-trace.py
expected_patch_sha256=a0f6f75d3df96b81b0cd98b2060ca719681c51ec53e5947b12f7398bfac3c13b
expected_installed_sha256=6440ffc1cad45b6d69ce73bdea9ae8a84c5af1c4d33e3f28da4dd7520bd67862
installed_file=/opt/venv/lib/python3.12/site-packages/vllm/model_executor/models/qwen3_next.py
dockerfile=${script_dir}/Dockerfile.decoder-boundary-trace-r110

for command_name in docker patch python3 sha256sum; do
  command -v "${command_name}" >/dev/null || {
    printf 'ERROR: required command is missing: %s\n' "${command_name}" >&2
    exit 2
  }
done
for required in "${dockerfile}" "${patch_file}" "${validator}"; do
  [[ -f "${required}" ]] || {
    printf 'ERROR: missing build input: %s\n' "${required}" >&2
    exit 2
  }
done
[[ "$(sha256sum "${patch_file}" | awk '{print $1}')" == "${expected_patch_sha256}" ]] || {
  printf 'ERROR: R110 decoder-boundary trace patch mismatch\n' >&2
  exit 2
}
[[ "$(docker image inspect "${base_image}" --format '{{.Id}}')" == "${expected_base_id}" ]] || {
  printf 'ERROR: R108 base image mismatch\n' >&2
  exit 2
}
[[ ! -e "${build_root}" ]] || {
  printf 'ERROR: BUILD_ROOT must not already exist: %s\n' "${build_root}" >&2
  exit 2
}

mkdir -p "${build_root}"
install -m 0644 "${patch_file}" "${build_root}/$(basename -- "${patch_file}")"
install -m 0644 "${validator}" "${build_root}/$(basename -- "${validator}")"

docker build --pull=false \
  --build-arg "BASE_IMAGE=${base_image}" \
  --build-arg "DECODER_BOUNDARY_TRACE_PATCH_SHA256=${expected_patch_sha256}" \
  --file "${dockerfile}" --tag "${image}" "${build_root}"

observed=$(docker run --rm --entrypoint sha256sum "${image}" \
  "${installed_file}" | awk '{print $1}')
[[ "${observed}" == "${expected_installed_sha256}" ]] || {
  printf 'ERROR: installed R110 source mismatch: %s\n' "${observed}" >&2
  exit 2
}
docker run --rm --entrypoint /opt/venv/bin/python \
  --volume "${validator}:/tmp/validate-qwen-decoder-boundary-trace.py:ro" \
  "${image}" /tmp/validate-qwen-decoder-boundary-trace.py "${installed_file}"
printf '%s\n' \
  "image=${image}" \
  "image_id=$(docker image inspect "${image}" --format '{{.Id}}')" \
  "patch_sha256=${expected_patch_sha256}" \
  "installed_source_sha256=${observed}"
