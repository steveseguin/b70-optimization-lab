#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/../.." && pwd)
build_root=${BUILD_ROOT:?set BUILD_ROOT to a dedicated writable build directory}
image=${IMAGE:-neural-download/vllm-openai-xpu:f01e-kernel-1e90-r13}
run_id=32798686770
artifact_name=vllm-xpu-kernels--20260825-014754
wheel_name=vllm_xpu_kernels-0.1.dev1+g1e90ffa67-cp38-abi3-manylinux_2_28_x86_64.whl
wheel_sha256=f3d999060c11ad6db5b4033d50d19c6b665492380075480d041ec4ee58fdfeb6
kernel_head=1e90ffa672ba02f17a909da11838a4c55b199783
artifact_dir=${build_root}/vllm-xpu-kernels-${kernel_head}
dockerfile=${repo_root}/experiments/qwen38-27b-b70/docker/Dockerfile.fp8-kernel-1e90-r13

for command_name in docker gh sha256sum; do
  command -v "${command_name}" >/dev/null || {
    printf '%s is required\n' "${command_name}" >&2
    exit 1
  }
done
[[ -f "${dockerfile}" ]] || { printf 'missing %s\n' "${dockerfile}" >&2; exit 1; }
mkdir -p "${artifact_dir}"

if [[ ! -f "${artifact_dir}/${wheel_name}" ]]; then
  gh run download "${run_id}" \
    --repo vllm-project/vllm-xpu-kernels \
    --name "${artifact_name}" \
    --dir "${artifact_dir}"
fi

[[ "$(sha256sum "${artifact_dir}/${wheel_name}" | awk '{print $1}')" == "${wheel_sha256}" ]] || {
  printf 'kernel wheel digest mismatch\n' >&2
  exit 1
}

docker build --pull=false --file "${dockerfile}" --tag "${image}" "${artifact_dir}"
[[ "$(docker image inspect "${image}" --format '{{ index .Config.Labels "neural.download.kernel.head" }}')" == "${kernel_head}" ]] || {
  printf 'built image does not carry the pinned kernel identity\n' >&2
  exit 1
}
docker image inspect "${image}" --format '{{.Id}}'

