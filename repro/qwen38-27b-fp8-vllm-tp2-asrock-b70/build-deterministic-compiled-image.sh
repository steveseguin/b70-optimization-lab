#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/../.." && pwd)
build_root=${BUILD_ROOT:?set BUILD_ROOT to a dedicated writable build directory}
image=${IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-collective-work-wait-r15}
base_image=${BASE_IMAGE:-neural-download/vllm-openai-xpu:f01e-kernel-1e90-r13}
expected_kernel_head=1e90ffa672ba02f17a909da11838a4c55b199783
source_url=https://github.com/vllm-project/vllm.git
source_commit=ac7509e2b1db40fec2f03dde1ed4e9dfdc2338c9
source_dir=${build_root}/vllm-${source_commit}
patches=(
  "${repo_root}/experiments/qwen38-27b-b70/patches/vllm-qwen38-fp8-block-w8a16-20260826.patch"
  "${repo_root}/experiments/qwen38-27b-b70/patches/vllm-qwen38-xpu-deterministic-gdn-ba-state-20260828.patch"
  "${repo_root}/experiments/qwen38-27b-b70/patches/vllm-qwen38-xpu-compiled-gdn-state-ccl-wait-20260828.patch"
)
dockerfile=${script_dir}/Dockerfile.deterministic-compiled

command -v git >/dev/null || { printf 'git is required\n' >&2; exit 1; }
command -v docker >/dev/null || { printf 'docker is required\n' >&2; exit 1; }
for required in "${dockerfile}" "${patches[@]}"; do
  [[ -f "${required}" ]] || { printf 'missing build input: %s\n' "${required}" >&2; exit 1; }
done
mkdir -p "${build_root}"

if ! git -C "${source_dir}" rev-parse --git-dir >/dev/null 2>&1; then
  [[ ! -e "${source_dir}" ]] || { printf 'refusing non-git source path: %s\n' "${source_dir}" >&2; exit 1; }
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
for patch in "${patches[@]}"; do
  git -C "${source_dir}" apply --check "${patch}"
  git -C "${source_dir}" apply "${patch}"
done
git -C "${source_dir}" diff --check

docker image inspect "${base_image}" >/dev/null 2>&1 || {
  printf 'kernel base image is missing: %s; run build-mtp1-kernel-image.sh first\n' "${base_image}" >&2
  exit 1
}
[[ "$(docker image inspect "${base_image}" --format '{{ index .Config.Labels "neural.download.kernel.head" }}')" == "${expected_kernel_head}" ]] || {
  printf 'kernel base identity mismatch: expected %s\n' "${expected_kernel_head}" >&2
  exit 1
}
docker build --pull=false --build-arg "BASE_IMAGE=${base_image}" \
  --file "${dockerfile}" --tag "${image}" "${source_dir}"
"${script_dir}/verify-image-contract.sh" mtp0 "${image}"

printf '%s\n' \
  "Built ${image}." \
  "Local image ID: $(docker image inspect "${image}" --format '{{.Id}}')" \
  "Historical validation image ID: sha256:d19f802ba702a9cb94b155f807a4674a0100702aee838323372f740d7168e34e" \
  "The source checkout is intentionally left patched for auditability."
