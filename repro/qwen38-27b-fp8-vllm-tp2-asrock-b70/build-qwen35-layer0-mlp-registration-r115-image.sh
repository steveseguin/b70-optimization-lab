#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/../.." && pwd)
build_root=${BUILD_ROOT:?set BUILD_ROOT to a new empty local build directory}
base_image=${BASE_IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-layer0-mlp-request-isolation-r114}
expected_base_id=${EXPECTED_BASE_IMAGE_ID:-sha256:996c8e59fe759e5370ec8a7a6e0b5d4a49984d6efc6079ea30f259d9275e375b}
image=${IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-layer0-mlp-request-isolation-r115}
patch_file=${repo_root}/experiments/qwen38-27b-b70/patches/vllm-qwen38-fp8-qwen35-layer0-mlp-registration-r115-20260902.patch
validator=${repo_root}/tools/validate-qwen35-layer0-mlp-registration-r115.py
expected_patch_sha256=73d3008332658a878fe390901797bd19457498c6ff14d0bd13a7028fb147bb60
expected_qwen35_sha256=183f571f401c94567b7f595073bfecbd418162d50f8758164b2dd0d6a4965a0f
expected_qwen_next_sha256=503b7b6fd254bbe498b5df4865402aa59d6ed23d68b1b6c4bdd292075c4c1ed3
qwen35_file=/opt/venv/lib/python3.12/site-packages/vllm/model_executor/models/qwen3_5.py
qwen_next_file=/opt/venv/lib/python3.12/site-packages/vllm/model_executor/models/qwen3_next.py
dockerfile=${script_dir}/Dockerfile.qwen35-layer0-mlp-registration-r115

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
  printf 'ERROR: R115 Qwen3.5 registration patch mismatch\n' >&2
  exit 2
}
[[ "$(docker image inspect "${base_image}" --format '{{.Id}}')" == "${expected_base_id}" ]] || {
  printf 'ERROR: R114 base image mismatch\n' >&2
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
  --build-arg "QWEN35_MLP_REGISTRATION_PATCH_SHA256=${expected_patch_sha256}" \
  --file "${dockerfile}" --tag "${image}" "${build_root}"

observed_qwen35=$(docker run --rm --entrypoint sha256sum "${image}" \
  "${qwen35_file}" | awk '{print $1}')
observed_qwen_next=$(docker run --rm --entrypoint sha256sum "${image}" \
  "${qwen_next_file}" | awk '{print $1}')
[[ "${observed_qwen35}" == "${expected_qwen35_sha256}" ]] || {
  printf 'ERROR: installed R115 qwen3_5.py mismatch: %s\n' "${observed_qwen35}" >&2
  exit 2
}
[[ "${observed_qwen_next}" == "${expected_qwen_next_sha256}" ]] || {
  printf 'ERROR: inherited R114 qwen3_next.py mismatch: %s\n' "${observed_qwen_next}" >&2
  exit 2
}
docker run --rm --entrypoint /opt/venv/bin/python \
  --volume "${validator}:/tmp/validate-qwen35-layer0-mlp-registration-r115.py:ro" \
  "${image}" /tmp/validate-qwen35-layer0-mlp-registration-r115.py "${qwen35_file}"
printf '%s\n' \
  "image=${image}" \
  "image_id=$(docker image inspect "${image}" --format '{{.Id}}')" \
  "patch_sha256=${expected_patch_sha256}" \
  "qwen35_source_sha256=${observed_qwen35}" \
  "qwen_next_source_sha256=${observed_qwen_next}"
