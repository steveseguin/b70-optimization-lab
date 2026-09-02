#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/../.." && pwd)
build_root=${BUILD_ROOT:?set BUILD_ROOT to a new empty local build directory}
base_image=${BASE_IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-layer0-mlp-request-isolation-r115}
expected_base_id=${EXPECTED_BASE_IMAGE_ID:-sha256:1709836b4c8c27f97057049942a69793b7168bdd6245064e6e02900db4529aa7}
image=${IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-layer0-mlp-allphase-isolation-r116}
patch_file=${repo_root}/experiments/qwen38-27b-b70/patches/vllm-qwen38-fp8-layer0-mlp-allphase-isolation-r116-20260902.patch
validator=${repo_root}/tools/validate-qwen-layer0-mlp-allphase-isolation-r116.py
expected_patch_sha256=ce1cdba00fb1775d2f6d317d00db6c6b91c3a36f8627057c5d088d27ea110d51
expected_qwen_next_sha256=6dfe2a1d2cff1cdd9e6965989c707c05027c55a5d05bcb9b718b6b8ce652c6af
expected_qwen35_sha256=183f571f401c94567b7f595073bfecbd418162d50f8758164b2dd0d6a4965a0f
qwen_next_file=/opt/venv/lib/python3.12/site-packages/vllm/model_executor/models/qwen3_next.py
qwen35_file=/opt/venv/lib/python3.12/site-packages/vllm/model_executor/models/qwen3_5.py
dockerfile=${script_dir}/Dockerfile.layer0-mlp-allphase-isolation-r116

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
  printf 'ERROR: R116 all-phase MLP patch mismatch\n' >&2
  exit 2
}
[[ "$(docker image inspect "${base_image}" --format '{{.Id}}')" == "${expected_base_id}" ]] || {
  printf 'ERROR: R115 base image mismatch\n' >&2
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
  --build-arg "LAYER0_MLP_ALLPHASE_PATCH_SHA256=${expected_patch_sha256}" \
  --file "${dockerfile}" --tag "${image}" "${build_root}"

observed_qwen_next=$(docker run --rm --entrypoint sha256sum "${image}" \
  "${qwen_next_file}" | awk '{print $1}')
observed_qwen35=$(docker run --rm --entrypoint sha256sum "${image}" \
  "${qwen35_file}" | awk '{print $1}')
[[ "${observed_qwen_next}" == "${expected_qwen_next_sha256}" ]] || {
  printf 'ERROR: installed R116 qwen3_next.py mismatch: %s\n' "${observed_qwen_next}" >&2
  exit 2
}
[[ "${observed_qwen35}" == "${expected_qwen35_sha256}" ]] || {
  printf 'ERROR: inherited R115 qwen3_5.py mismatch: %s\n' "${observed_qwen35}" >&2
  exit 2
}
docker run --rm --entrypoint /opt/venv/bin/python \
  --volume "${validator}:/tmp/validate-qwen-layer0-mlp-allphase-isolation-r116.py:ro" \
  "${image}" /tmp/validate-qwen-layer0-mlp-allphase-isolation-r116.py "${qwen_next_file}"
printf '%s\n' \
  "image=${image}" \
  "image_id=$(docker image inspect "${image}" --format '{{.Id}}')" \
  "patch_sha256=${expected_patch_sha256}" \
  "qwen_next_source_sha256=${observed_qwen_next}" \
  "qwen35_source_sha256=${observed_qwen35}"
