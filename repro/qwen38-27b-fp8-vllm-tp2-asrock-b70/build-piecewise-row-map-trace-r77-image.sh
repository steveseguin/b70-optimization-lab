#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(git -C "${script_dir}" rev-parse --show-toplevel)
image=${IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-piecewise-row-map-trace-r77}
base_image=${BASE_IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-piecewise-boundary-trace-r74}
expected_base_id=${EXPECTED_BASE_IMAGE_ID:-sha256:40fffaf5fb9597661802f683af061cfa909ae5bd751d9584bfacd73a0433a09c}
hook=${repo_root}/experiments/qwen38-27b-b70/scripts/qwen38-piecewise-row-map-trace-sitecustomize-r77.py
dockerfile=${script_dir}/Dockerfile.piecewise-row-map-trace-r77

for command_name in docker sha256sum; do
  command -v "${command_name}" >/dev/null || {
    printf 'ERROR: required command is missing: %s\n' "${command_name}" >&2
    exit 2
  }
done

actual_base_id=$(docker image inspect "${base_image}" --format '{{.Id}}')
[[ "${actual_base_id}" == "${expected_base_id}" ]] || {
  printf 'ERROR: base image mismatch\nexpected=%s\nactual=%s\n' \
    "${expected_base_id}" "${actual_base_id}" >&2
  exit 2
}

hook_sha256=$(sha256sum "${hook}" | awk '{print $1}')
build_root=$(mktemp -d /tmp/qwen38-r77-build.XXXXXX)
trap 'find "${build_root}" -xdev -depth -delete' EXIT
cp "${hook}" "${build_root}/"

docker build --network=none --pull=false \
  --build-arg "BASE_IMAGE=${base_image}" \
  --build-arg "TRACE_HOOK_SHA256=${hook_sha256}" \
  -f "${dockerfile}" -t "${image}" "${build_root}"

image_id=$(docker image inspect "${image}" --format '{{.Id}}')
observed=$(docker run --rm --entrypoint sha256sum "${image}" \
  /instrument/sitecustomize.py | awk '{print $1}')
[[ "${observed}" == "${hook_sha256}" ]] || {
  printf 'ERROR: installed trace hook hash mismatch\n' >&2
  exit 2
}

printf 'image=%s\nimage_id=%s\ntrace_hook_sha256=%s\n' \
  "${image}" "${image_id}" "${hook_sha256}"
