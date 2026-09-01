#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/../.." && pwd)
build_root=${BUILD_ROOT:?set BUILD_ROOT to a new empty local build directory}
image=${IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-cudagraph-boundary-trace-r73}
base_image=${BASE_IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-draft-only-int4-r62}
expected_base_id=${EXPECTED_BASE_IMAGE_ID:-sha256:cac17acf96ebbf65bfbe98e45dcea8eb5626c2b027dcac0228bc3bcba0063374}
hook=${repo_root}/experiments/qwen38-27b-b70/scripts/qwen38-cudagraph-boundary-trace-sitecustomize-r73.py
dockerfile=${script_dir}/Dockerfile.cudagraph-boundary-trace-r73

for command_name in docker sha256sum; do
  command -v "${command_name}" >/dev/null || {
    printf '%s is required\n' "${command_name}" >&2
    exit 1
  }
done
for required in "${hook}" "${dockerfile}"; do
  [[ -f "${required}" ]] || {
    printf 'missing build input: %s\n' "${required}" >&2
    exit 1
  }
done
[[ "$(docker image inspect "${base_image}" --format '{{.Id}}')" == "${expected_base_id}" ]] || {
  printf 'base image identity mismatch\n' >&2
  exit 1
}
[[ ! -e "${build_root}" ]] || {
  printf 'BUILD_ROOT must not already exist: %s\n' "${build_root}" >&2
  exit 1
}
hook_sha256=$(sha256sum "${hook}" | awk '{print $1}')
mkdir -p "${build_root}"
install -m 0644 "${hook}" "${build_root}/sitecustomize.py"

docker build --pull=false \
  --build-arg "BASE_IMAGE=${base_image}" \
  --build-arg "TRACE_HOOK_SHA256=${hook_sha256}" \
  --file "${dockerfile}" --tag "${image}" "${build_root}"

observed=$(docker run --rm --entrypoint sha256sum "${image}" \
  /instrument/sitecustomize.py | awk '{print $1}')
[[ "${observed}" == "${hook_sha256}" ]] || {
  printf 'installed trace hook identity mismatch\n' >&2
  exit 1
}
printf 'image=%s\nimage_id=%s\ntrace_hook_sha256=%s\n' \
  "${image}" "$(docker image inspect "${image}" --format '{{.Id}}')" \
  "${hook_sha256}"
