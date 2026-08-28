#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/../.." && pwd)
build_root=${BUILD_ROOT:?set BUILD_ROOT to a dedicated empty build directory}
source_commit=ac7509e2b1db40fec2f03dde1ed4e9dfdc2338c9
source_dir=${build_root}/vllm-${source_commit}
source_url=${VLLM_SOURCE_URL:-https://github.com/vllm-project/vllm.git}
base_image=${BASE_IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-rms-serial-r31}
base_image_id=sha256:ba42e928e69c60d1c9102df6ec1c0e998e9dd8463f74d5dc0a8b4bb45108fa9b
dynamic_image=${DYNAMIC_IMAGE:-neural-download/vllm-openai-xpu:f01e-kernel-1e90-w8a16-dynamic-mamba-r1}
dynamic_image_id=sha256:2b79af686423379e4418aafa92d72e2248e8d09fabe609284dc7e29190cb8cd6
image=${IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-dynamic-deterministic-mtp8-r34}
patch=${repo_root}/experiments/qwen38-27b-b70/patches/vllm-qwen38-xpu-gemma-rmsnorm-mtp1-mtp8-serial-exact-r34-20260828.patch
patch_sha256=98c26561926abfcfa7b057eb83cda3c2774dff908c3641f09586f748c7dbff44
dockerfile=${script_dir}/Dockerfile.dynamic-deterministic-mtp8-r34

for command_name in docker git sha256sum; do
  command -v "${command_name}" >/dev/null || {
    printf '%s is required\n' "${command_name}" >&2
    exit 1
  }
done
for required in "${patch}" "${dockerfile}"; do
  [[ -f "${required}" ]] || { printf 'missing %s\n' "${required}" >&2; exit 1; }
done
[[ "$(sha256sum "${patch}" | awk '{print $1}')" == "${patch_sha256}" ]] || {
  printf 'RMS patch digest mismatch\n' >&2
  exit 1
}
for pair in "${base_image}|${base_image_id}" "${dynamic_image}|${dynamic_image_id}"; do
  image_name=${pair%%|*}
  expected_id=${pair#*|}
  docker image inspect "${image_name}" >/dev/null 2>&1 || {
    printf 'missing prerequisite image: %s\n' "${image_name}" >&2
    exit 1
  }
  [[ "$(docker image inspect "${image_name}" --format '{{.Id}}')" == "${expected_id}" ]] || {
    printf 'image identity mismatch for %s\n' "${image_name}" >&2
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
  printf 'source checkout is dirty; use a dedicated BUILD_ROOT\n' >&2
  exit 1
}
git -C "${source_dir}" apply --check "${patch}"
git -C "${source_dir}" apply "${patch}"
git -C "${source_dir}" diff --check
layernorm_sha256=$(sha256sum "${source_dir}/vllm/model_executor/layers/layernorm.py" | awk '{print $1}')

docker build --pull=false \
  --build-arg "BASE_IMAGE=${base_image}" \
  --build-arg "DYNAMIC_IMAGE=${dynamic_image}" \
  --build-arg "LAYERNORM_SHA256=${layernorm_sha256}" \
  --build-arg "RMS_PATCH_SHA256=${patch_sha256}" \
  --file "${dockerfile}" --tag "${image}" "${source_dir}"

printf '%s\n' \
  "image=${image}" \
  "image_id=$(docker image inspect "${image}" --format '{{.Id}}')" \
  "layernorm_sha256=${layernorm_sha256}" \
  "rms_patch_sha256=${patch_sha256}"
