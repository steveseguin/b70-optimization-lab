#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/../.." && pwd)
build_root=${BUILD_ROOT:?set BUILD_ROOT to a new empty local build directory}
base_image=${BASE_IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-layer0-mlp-allphase-isolation-r116}
expected_base_id=${EXPECTED_BASE_IMAGE_ID:-sha256:91e591590f96247cd318bb229e7909ea1c036be201e62b646679e1ea02eab08f}
image=${IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-gdn-r99-all-phases-r117}
patch_file=${repo_root}/experiments/qwen38-27b-b70/patches/vllm-qwen38-fp8-gdn-r99-all-phases-r117-20260902.patch
validator=${repo_root}/tools/validate-qwen-gdn-r99-all-phases-r117.py
expected_patch_sha256=2b954a93c1b3ae666a0bb386697a0693987ae351d351bc2fc582d0521f57e806
expected_gdn_sha256=905d2eaf7ac33154f892b80eb2c36133c23820156606bc59d4a584710d4dc568
gdn_file=/opt/venv/lib/python3.12/site-packages/vllm/model_executor/layers/mamba/gdn/qwen_gdn_linear_attn.py
dockerfile=${script_dir}/Dockerfile.gdn-r99-all-phases-r117

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
  printf 'ERROR: R117 patch mismatch\n' >&2
  exit 2
}
[[ "$(docker image inspect "${base_image}" --format '{{.Id}}')" == "${expected_base_id}" ]] || {
  printf 'ERROR: R116 base image mismatch\n' >&2
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
  --build-arg "GDN_R99_ALL_PHASES_PATCH_SHA256=${expected_patch_sha256}" \
  --file "${dockerfile}" --tag "${image}" "${build_root}"

observed_gdn=$(docker run --rm --entrypoint sha256sum "${image}" "${gdn_file}" | awk '{print $1}')
[[ "${observed_gdn}" == "${expected_gdn_sha256}" ]] || {
  printf 'ERROR: installed R117 qwen_gdn_linear_attn.py mismatch: %s\n' "${observed_gdn}" >&2
  exit 2
}
docker run --rm --entrypoint /opt/venv/bin/python \
  --volume "${validator}:/tmp/validate-qwen-gdn-r99-all-phases-r117.py:ro" \
  "${image}" /tmp/validate-qwen-gdn-r99-all-phases-r117.py "${gdn_file}"
printf '%s\n' \
  "image=${image}" \
  "image_id=$(docker image inspect "${image}" --format '{{.Id}}')" \
  "patch_sha256=${expected_patch_sha256}" \
  "gdn_source_sha256=${observed_gdn}"
