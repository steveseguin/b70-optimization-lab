#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
image=${IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-piecewise-selected-row1-trace-r76}
base_image=${BASE_IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-piecewise-selected-row-trace-r75}
expected_base_id=${EXPECTED_BASE_IMAGE_ID:-sha256:83c818bd3bacca532342a8b9ada8ac0e3f7330016bdf2f4a62fcaa96678f9cf4}
dockerfile=${script_dir}/Dockerfile.piecewise-selected-row1-trace-r76

command -v docker >/dev/null || {
  printf 'ERROR: docker is required\n' >&2
  exit 2
}

actual_base_id=$(docker image inspect "${base_image}" --format '{{.Id}}')
[[ "${actual_base_id}" == "${expected_base_id}" ]] || {
  printf 'ERROR: base image mismatch\nexpected=%s\nactual=%s\n' \
    "${expected_base_id}" "${actual_base_id}" >&2
  exit 2
}

build_root=$(mktemp -d /tmp/qwen38-r76-build.XXXXXX)
trap 'find "${build_root}" -xdev -depth -delete' EXIT

docker build --network=none --pull=false \
  --build-arg "BASE_IMAGE=${base_image}" \
  -f "${dockerfile}" -t "${image}" "${build_root}"

image_id=$(docker image inspect "${image}" --format '{{.Id}}')
[[ "$(docker image inspect "${image}" --format '{{ index .Config.Env }}' | grep -o 'VLLM_XPU_PW_BOUNDARY_TRACE_ROW=1' || true)" == \
   'VLLM_XPU_PW_BOUNDARY_TRACE_ROW=1' ]] || {
  printf 'ERROR: row-1 trace environment is missing\n' >&2
  exit 2
}

printf 'image=%s\nimage_id=%s\n' "${image}" "${image_id}"
