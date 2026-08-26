#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/../.." && pwd)
build_root=${BUILD_ROOT:?set BUILD_ROOT to a dedicated writable build directory}
host_oneapi_root=${HOST_ONEAPI_ROOT:-/opt/intel/oneapi}
base_image=${BASE_IMAGE:-neural-download/vllm-openai-xpu:f01e-kernel-1e90-w8a16-r122}
image=${IMAGE:-neural-download/vllm-openai-xpu:f01e-kernel-1e90-w8a16-dynamic-mtp-width-r1}
base_image_id=sha256:61bd8edb385c03b40cdadaba068608355b144a5011722597e7ca437f37346ecd
kernel_head=1e90ffa672ba02f17a909da11838a4c55b199783
source_url=https://github.com/vllm-project/vllm-xpu-kernels.git
source_dir=${build_root}/vllm-xpu-kernels-${kernel_head}-dynamic-mtp-active-width-r1
dist_dir=${build_root}/dist
context_dir=${build_root}/overlay-context
patch=${repo_root}/experiments/qwen38-27b-b70/patches/vllm-xpu-kernels-qwen38-dynamic-mtp-active-width-20260826.patch
patch_sha256=68c486a9a10a2f7e85d7d88783a05f89919e931d2b81922f85be733bfb59f1b5
dockerfile=${repo_root}/experiments/qwen38-27b-b70/docker/Dockerfile.fp8-w8a16-dynamic-mtp-active-width-r1

for command_name in docker git sha256sum unzip; do
  command -v "${command_name}" >/dev/null || {
    printf '%s is required\n' "${command_name}" >&2
    exit 1
  }
done
for required in "${patch}" "${dockerfile}" "${host_oneapi_root}/setvars.sh"; do
  [[ -e "${required}" ]] || { printf 'missing %s\n' "${required}" >&2; exit 1; }
done
[[ "$(sha256sum "${patch}" | awk '{print $1}')" == "${patch_sha256}" ]] || {
  printf 'dynamic-MTP active-width patch digest mismatch\n' >&2
  exit 1
}
docker image inspect "${base_image}" >/dev/null 2>&1 || {
  printf 'missing base image: %s\nBuild the pinned MTP1 kernel and W8A16 overlays first.\n' \
    "${base_image}" >&2
  exit 1
}
[[ "$(docker image inspect "${base_image}" --format '{{.Id}}')" == "${base_image_id}" ]] || {
  printf 'base image ID mismatch for %s\n' "${base_image}" >&2
  exit 1
}

mkdir -p "${build_root}"
if ! git -C "${source_dir}" rev-parse --git-dir >/dev/null 2>&1; then
  [[ ! -e "${source_dir}" ]] || {
    printf 'refusing non-git source path: %s\n' "${source_dir}" >&2
    exit 1
  }
  git clone --filter=blob:none --no-checkout "${source_url}" "${source_dir}"
  git -C "${source_dir}" checkout --detach "${kernel_head}"
fi
[[ "$(git -C "${source_dir}" rev-parse HEAD)" == "${kernel_head}" ]] || {
  printf 'source checkout is not pinned commit %s\n' "${kernel_head}" >&2
  exit 1
}
[[ -z "$(git -C "${source_dir}" status --porcelain)" ]] || {
  printf 'source checkout is dirty; use a dedicated clean BUILD_ROOT\n' >&2
  exit 1
}
git -C "${source_dir}" apply --check "${patch}"
git -C "${source_dir}" apply "${patch}"
git -C "${source_dir}" diff --check

[[ ! -e "${dist_dir}" && ! -e "${context_dir}" ]] || {
  printf 'refusing existing dist/context under %s\n' "${build_root}" >&2
  exit 1
}
mkdir -p "${dist_dir}" "${context_dir}"

docker run --rm --memory 14g --memory-swap 28g \
  --volume "${source_dir}:/src" \
  --volume "${dist_dir}:/out" \
  --volume "${host_oneapi_root}:/opt/intel/oneapi:ro" \
  --entrypoint /bin/bash "${base_image}" -lc '
    set -euo pipefail
    git config --global --add safe.directory /src
    source /opt/intel/oneapi/setvars.sh >/dev/null 2>&1
    cd /src
    MAX_JOBS=1 CMAKE_BUILD_TYPE=Release \
    BASIC_KERNELS_ENABLED=0 FA2_KERNELS_ENABLED=0 MOE_KERNELS_ENABLED=0 \
    GDN_KERNELS_ENABLED=1 MQA_LOGITS_KERNELS_ENABLED=0 \
    MHC_KERNELS_ENABLED=1 XPU_SPECIFIC_KERNELS_ENABLED=1 \
    XPUMEM_ALLOCATOR_ENABLED=0 BUILD_SYCL_TLA_KERNELS=1 \
    VLLM_XPU_ENABLE_XE2=1 VLLM_XPU_ENABLE_XE_DEFAULT=0 \
    /opt/venv/bin/python setup.py bdist_wheel \
      --dist-dir /out --py-limited-api=cp38
  '

mapfile -t wheels < <(find "${dist_dir}" -maxdepth 1 -type f -name '*.whl')
[[ "${#wheels[@]}" == 1 ]] || {
  printf 'expected exactly one wheel, found %s\n' "${#wheels[@]}" >&2
  exit 1
}
unzip -t "${wheels[0]}" >/dev/null
unzip -j "${wheels[0]}" \
  vllm_xpu_kernels/_xpu_C.abi3.so \
  vllm_xpu_kernels/libgdn_attn_kernels_xe_2.so \
  -d "${context_dir}"
xpu_extension_sha256=$(sha256sum "${context_dir}/_xpu_C.abi3.so" | awk '{print $1}')
gdn_library_sha256=$(sha256sum "${context_dir}/libgdn_attn_kernels_xe_2.so" | awk '{print $1}')

docker build --pull=false \
  --build-arg "BASE_IMAGE=${base_image}" \
  --build-arg "PATCH_SHA256=${patch_sha256}" \
  --build-arg "XPU_EXTENSION_SHA256=${xpu_extension_sha256}" \
  --build-arg "GDN_LIBRARY_SHA256=${gdn_library_sha256}" \
  --file "${dockerfile}" --tag "${image}" "${context_dir}"

[[ "$(docker image inspect "${image}" --format '{{ index .Config.Labels "neural.download.kernel.patch.sha256" }}')" == \
  "${patch_sha256}" ]] || { printf 'built image patch label mismatch\n' >&2; exit 1; }
[[ "$(docker image inspect "${image}" --format '{{ index .Config.Labels "neural.download.kernel.xpu-extension.sha256" }}')" == \
  "${xpu_extension_sha256}" ]] || { printf 'built image extension label mismatch\n' >&2; exit 1; }
[[ "$(docker image inspect "${image}" --format '{{ index .Config.Labels "neural.download.kernel.gdn-library.sha256" }}')" == \
  "${gdn_library_sha256}" ]] || { printf 'built image GDN label mismatch\n' >&2; exit 1; }

printf '%s\n' \
  "wheel=$(basename -- "${wheels[0]}")" \
  "wheel_sha256=$(sha256sum "${wheels[0]}" | awk '{print $1}')" \
  "xpu_extension_sha256=${xpu_extension_sha256}" \
  "gdn_library_sha256=${gdn_library_sha256}" \
  "image=${image}" \
  "image_id=$(docker image inspect "${image}" --format '{{.Id}}')"
