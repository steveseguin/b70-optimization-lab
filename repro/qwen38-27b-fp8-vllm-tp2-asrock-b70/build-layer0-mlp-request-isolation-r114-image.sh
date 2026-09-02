#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/../.." && pwd)
build_root=${BUILD_ROOT:?set BUILD_ROOT to a new empty local build directory}
base_image=${BASE_IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-gdn-projection-isolation-trace-r108}
expected_base_id=${EXPECTED_BASE_IMAGE_ID:-sha256:e08ee7a313c912d8a645a71f7d88d9e436784d0f8e35d69a5fe4fe94f6a3bed4}
image=${IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-layer0-mlp-request-isolation-r114}
patch_file=${repo_root}/experiments/qwen38-27b-b70/patches/vllm-qwen38-fp8-layer0-mlp-request-isolation-r114-20260902.patch
validator=${repo_root}/tools/validate-qwen-layer0-mlp-isolation-r114.py
expected_patch_sha256=be70a949b4de107a648d5e242b0afda5958ee1779f8ab716a5014717f354d7d4
expected_installed_sha256=503b7b6fd254bbe498b5df4865402aa59d6ed23d68b1b6c4bdd292075c4c1ed3
installed_file=/opt/venv/lib/python3.12/site-packages/vllm/model_executor/models/qwen3_next.py
dockerfile=${script_dir}/Dockerfile.layer0-mlp-request-isolation-r114

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
  printf 'ERROR: R114 layer-0 MLP isolation patch mismatch\n' >&2
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
  --build-arg "LAYER0_MLP_ISOLATION_PATCH_SHA256=${expected_patch_sha256}" \
  --file "${dockerfile}" --tag "${image}" "${build_root}"

observed=$(docker run --rm --entrypoint sha256sum "${image}" \
  "${installed_file}" | awk '{print $1}')
[[ "${observed}" == "${expected_installed_sha256}" ]] || {
  printf 'ERROR: installed R114 source mismatch: %s\n' "${observed}" >&2
  exit 2
}
docker run --rm --entrypoint /opt/venv/bin/python \
  --volume "${validator}:/tmp/validate-qwen-layer0-mlp-isolation-r114.py:ro" \
  "${image}" /tmp/validate-qwen-layer0-mlp-isolation-r114.py "${installed_file}"
printf '%s\n' \
  "image=${image}" \
  "image_id=$(docker image inspect "${image}" --format '{{.Id}}')" \
  "patch_sha256=${expected_patch_sha256}" \
  "installed_source_sha256=${observed}"
