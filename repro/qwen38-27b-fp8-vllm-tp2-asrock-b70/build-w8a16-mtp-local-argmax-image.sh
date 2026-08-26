#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/../.." && pwd)
build_root=${BUILD_ROOT:?set BUILD_ROOT to a dedicated writable build directory}
image=${IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-w8a16-mtp-local-argmax-r1}
base_image=${BASE_IMAGE:-neural-download/vllm-openai-xpu:f01e-kernel-1e90-r13}
base_image_id=sha256:9403883cdbec3df988f486815f9dd528eb98baf0cc73d04ef3631ff0ac6a35b0
source_url=https://github.com/vllm-project/vllm.git
source_commit=ac7509e2b1db40fec2f03dde1ed4e9dfdc2338c9
source_dir=${build_root}/vllm-${source_commit}
w8a16_patch=${repo_root}/experiments/qwen38-27b-b70/patches/vllm-qwen38-fp8-block-w8a16-20260826.patch
local_argmax_patch=${repo_root}/experiments/qwen38-27b-b70/patches/vllm-qwen38-next-mtp-local-argmax-hook-20260826.patch
dockerfile=${repo_root}/experiments/qwen38-27b-b70/docker/Dockerfile.fp8-w8a16-mtp-local-argmax-r1

for command_name in git docker sha256sum; do
  command -v "${command_name}" >/dev/null || {
    printf '%s is required\n' "${command_name}" >&2
    exit 1
  }
done
for required in "${w8a16_patch}" "${local_argmax_patch}" "${dockerfile}"; do
  [[ -f "${required}" ]] || { printf 'missing %s\n' "${required}" >&2; exit 1; }
done
[[ "$(sha256sum "${w8a16_patch}" | awk '{print $1}')" == \
  "5db7f1af1156f3490ca91d0d74a07aa2d0909e175eeb1ae23f2074c55c44ff8a" ]] || {
  printf 'block-W8A16 patch digest mismatch\n' >&2
  exit 1
}
[[ "$(sha256sum "${local_argmax_patch}" | awk '{print $1}')" == \
  "f5f15e3e97dad905ff20bd5ba69c1cd0fb3493500182753f0627e312f5237c47" ]] || {
  printf 'Qwen3Next MTP local-argmax patch digest mismatch\n' >&2
  exit 1
}
docker image inspect "${base_image}" >/dev/null 2>&1 || {
  printf 'missing kernel base image: %s\nBuild it with build-mtp1-kernel-image.sh first.\n' "${base_image}" >&2
  exit 1
}
[[ "$(docker image inspect "${base_image}" --format '{{.Id}}')" == "${base_image_id}" ]] || {
  printf 'kernel base image ID mismatch for %s\n' "${base_image}" >&2
  exit 1
}

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
git -C "${source_dir}" apply --check "${w8a16_patch}"
git -C "${source_dir}" apply "${w8a16_patch}"
git -C "${source_dir}" apply --check "${local_argmax_patch}"
git -C "${source_dir}" apply "${local_argmax_patch}"
git -C "${source_dir}" diff --check

docker build --pull=false --build-arg "BASE_IMAGE=${base_image}" \
  --file "${dockerfile}" --tag "${image}" "${source_dir}"
[[ "$(docker image inspect "${image}" --format '{{ index .Config.Labels "neural.download.mtp.local_argmax" }}')" == \
  "qwen3-next-hook-r1" ]] || {
  printf 'built image is missing the local-argmax identity label\n' >&2
  exit 1
}
docker image inspect "${image}" --format '{{.Id}}'

printf '%s\n' \
  "Built ${image}." \
  "The source checkout is intentionally left patched for auditability." \
  "Use a new BUILD_ROOT for another clean build."
