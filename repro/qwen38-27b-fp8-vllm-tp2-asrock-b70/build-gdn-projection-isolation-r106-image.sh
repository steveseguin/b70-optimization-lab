#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/../.." && pwd)
build_root=${BUILD_ROOT:?set BUILD_ROOT to a new empty local build directory}
base_image=${BASE_IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-gdn-prefill-output-trace-all-r104}
expected_base_id=${EXPECTED_BASE_IMAGE_ID:-sha256:f1dd575ae2e0effc7991535c253af82b332ac0604b7f60ba796f31b81e26f951}
image=${IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-gdn-projection-isolation-r106}
patch_file=${repo_root}/experiments/qwen38-27b-b70/patches/vllm-qwen38-fp8-gdn-projection-isolation-r106-20260902.patch
expected_patch_sha256=43801a2f80ccf93724228d55873891b3f48b33fabadbc5fd45a09582dc207bf3
expected_installed_sha256=782e6f50f52067a039bcb94d4b41d0ca24a1706d56c54e6cdfdaf68a55965d47
installed_file=/opt/venv/lib/python3.12/site-packages/vllm/model_executor/layers/mamba/gdn/qwen_gdn_linear_attn.py
dockerfile=${script_dir}/Dockerfile.gdn-projection-isolation-r106

for command_name in docker patch sha256sum; do
  command -v "${command_name}" >/dev/null || {
    printf 'ERROR: required command is missing: %s\n' "${command_name}" >&2
    exit 2
  }
done
for required in "${dockerfile}" "${patch_file}"; do
  [[ -f "${required}" ]] || {
    printf 'ERROR: missing build input: %s\n' "${required}" >&2
    exit 2
  }
done
[[ "$(sha256sum "${patch_file}" | awk '{print $1}')" == "${expected_patch_sha256}" ]] || {
  printf 'ERROR: R106 projection-isolation patch mismatch\n' >&2
  exit 2
}
[[ "$(docker image inspect "${base_image}" --format '{{.Id}}')" == "${expected_base_id}" ]] || {
  printf 'ERROR: R104 base image mismatch\n' >&2
  exit 2
}
[[ ! -e "${build_root}" ]] || {
  printf 'ERROR: BUILD_ROOT must not already exist: %s\n' "${build_root}" >&2
  exit 2
}

mkdir -p "${build_root}"
install -m 0644 "${patch_file}" "${build_root}/$(basename -- "${patch_file}")"

docker build --pull=false \
  --build-arg "BASE_IMAGE=${base_image}" \
  --build-arg "GDN_PROJECTION_ISOLATION_PATCH_SHA256=${expected_patch_sha256}" \
  --file "${dockerfile}" --tag "${image}" "${build_root}"

observed=$(docker run --rm --entrypoint sha256sum "${image}" \
  "${installed_file}" | awk '{print $1}')
[[ "${observed}" == "${expected_installed_sha256}" ]] || {
  printf 'ERROR: installed R106 source mismatch: %s\n' "${observed}" >&2
  exit 2
}
printf '%s\n' \
  "image=${image}" \
  "image_id=$(docker image inspect "${image}" --format '{{.Id}}')" \
  "patch_sha256=${expected_patch_sha256}" \
  "installed_source_sha256=${observed}"
