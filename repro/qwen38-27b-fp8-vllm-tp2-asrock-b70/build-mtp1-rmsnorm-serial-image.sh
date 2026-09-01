#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/../.." && pwd)
build_root=${BUILD_ROOT:?set BUILD_ROOT to a dedicated writable build directory}
image=${IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-rms-serial-r31}
base_image=${BASE_IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-collective-work-wait-r15}
expected_base_id=${EXPECTED_BASE_IMAGE_ID:-}
source_url=https://github.com/vllm-project/vllm.git
source_commit=ac7509e2b1db40fec2f03dde1ed4e9dfdc2338c9
source_dir=${build_root}/vllm-${source_commit}
patch=${repo_root}/experiments/qwen38-27b-b70/patches/vllm-qwen38-xpu-gemma-rmsnorm-mtp1-serial-exact-r30-20260828.patch
dockerfile=${script_dir}/Dockerfile.mtp1-rmsnorm-serial

command -v git >/dev/null || { printf 'git is required\n' >&2; exit 1; }
command -v docker >/dev/null || { printf 'docker is required\n' >&2; exit 1; }
for required in "${dockerfile}" "${patch}"; do
  [[ -f "${required}" ]] || {
    printf 'missing build input: %s\n' "${required}" >&2
    exit 1
  }
done
mkdir -p "${build_root}"

if ! git -C "${source_dir}" rev-parse --git-dir >/dev/null 2>&1; then
  [[ ! -e "${source_dir}" ]] || {
    printf 'refusing non-git source path: %s\n' "${source_dir}" >&2
    exit 1
  }
  git clone --filter=blob:none --no-checkout "${source_url}" "${source_dir}"
  git -C "${source_dir}" checkout --detach "${source_commit}"
fi

[[ "$(git -C "${source_dir}" rev-parse HEAD)" == "${source_commit}" ]] || {
  printf 'source checkout is not pinned commit %s\n' "${source_commit}" >&2
  exit 1
}
[[ -z "$(git -C "${source_dir}" status --porcelain)" ]] || {
  printf 'source checkout is dirty; use a dedicated clean BUILD_ROOT\n' >&2
  exit 1
}
git -C "${source_dir}" apply --check "${patch}"
git -C "${source_dir}" apply "${patch}"
git -C "${source_dir}" diff --check

docker image inspect "${base_image}" >/dev/null 2>&1 || {
  printf 'qualified base image is missing: %s\n' "${base_image}" >&2
  exit 1
}
if [[ -n "${expected_base_id}" ]]; then
  [[ "$(docker image inspect "${base_image}" --format '{{.Id}}')" == "${expected_base_id}" ]] || {
    printf 'qualified base image identity mismatch: expected %s\n' "${expected_base_id}" >&2
    exit 1
  }
fi
"${script_dir}/verify-image-contract.sh" mtp0 "${base_image}"
docker build --pull=false --build-arg "BASE_IMAGE=${base_image}" \
  --file "${dockerfile}" --tag "${image}" "${source_dir}"
"${script_dir}/verify-image-contract.sh" mtp1 "${image}"

printf '%s\n' \
  "Built ${image}." \
  "Local image ID: $(docker image inspect "${image}" --format '{{.Id}}')" \
  "Historical validation image ID: sha256:ba42e928e69c60d1c9102df6ec1c0e998e9dd8463f74d5dc0a8b4bb45108fa9b" \
  "The source checkout is intentionally left patched for auditability."
