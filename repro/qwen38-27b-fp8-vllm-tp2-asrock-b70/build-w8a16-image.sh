#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/../.." && pwd)
build_root=${BUILD_ROOT:?set BUILD_ROOT to a dedicated writable build directory}
image=${IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-block-w8a16-20260826}
base_image=${BASE_IMAGE:-vllm/vllm-openai-xpu@sha256:f01e24f6c7ff01f1e0662234255a1372297d1dbd89d003cf13c8fad3eab1ba4f}
source_url=https://github.com/vllm-project/vllm.git
source_commit=ac7509e2b1db40fec2f03dde1ed4e9dfdc2338c9
source_dir=${build_root}/vllm-${source_commit}
patch=${repo_root}/experiments/qwen38-27b-b70/patches/vllm-qwen38-fp8-block-w8a16-20260826.patch
dockerfile=${script_dir}/Dockerfile.w8a16

command -v git >/dev/null || { printf 'git is required\n' >&2; exit 1; }
command -v docker >/dev/null || { printf 'docker is required\n' >&2; exit 1; }
[[ -f "${patch}" && -f "${dockerfile}" ]] || {
  printf 'repository patch or Dockerfile is missing\n' >&2
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
git -C "${source_dir}" apply --check "${patch}"
git -C "${source_dir}" apply "${patch}"
git -C "${source_dir}" diff --check

docker image inspect "${base_image}" >/dev/null 2>&1 || {
  printf 'base image is missing: %s\n' "${base_image}" >&2
  exit 1
}
docker build --pull=false --build-arg "BASE_IMAGE=${base_image}" \
  --file "${dockerfile}" --tag "${image}" "${source_dir}"
docker image inspect "${image}" --format '{{.Id}}'

printf '%s\n' \
  "Built ${image}." \
  "The source checkout is intentionally left patched for auditability." \
  "Use a new BUILD_ROOT or git apply --reverse ${patch} before rebuilding."
