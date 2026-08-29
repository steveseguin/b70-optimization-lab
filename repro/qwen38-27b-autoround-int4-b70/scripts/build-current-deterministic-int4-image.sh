#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/../../.." && pwd)
build_root=${BUILD_ROOT:?set BUILD_ROOT to a dedicated, absent build directory}
host_oneapi_root=${HOST_ONEAPI_ROOT:-/opt/intel/oneapi}
base_image=${BASE_IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-rms-serial-r31}
expected_base_image_id=${EXPECTED_BASE_IMAGE_ID:?set EXPECTED_BASE_IMAGE_ID to the local base image ID}
image=${IMAGE:-neural-download/vllm-openai-xpu:qwen38-autoround-current-deterministic-r1}
kernel_head=1e90ffa672ba02f17a909da11838a4c55b199783
source_url=https://github.com/vllm-project/vllm-xpu-kernels.git
patch=${repo_root}/experiments/qwen38-27b-b70/patches/vllm-xpu-kernels-qwen38-onednn-int4-determinism-pad-kernel1e90-20260828.patch
patch_sha256=8a2f1cc49d516eeb9093e0b99c4c5ed6b74f76196417fa8951e1f8c3e7405168
dockerfile=${repo_root}/experiments/qwen38-27b-b70/docker/Dockerfile.autoround-detpad-kernel1e90-r1
source_dir=${build_root}/source
dist_dir=${build_root}/dist
context_dir=${build_root}/overlay-context

for command_name in docker git sha256sum strings unzip; do
  command -v "${command_name}" >/dev/null || {
    printf '%s is required\n' "${command_name}" >&2
    exit 1
  }
done
for required in "${patch}" "${dockerfile}" "${host_oneapi_root}/setvars.sh"; do
  [[ -e "${required}" ]] || { printf 'missing %s\n' "${required}" >&2; exit 1; }
done
[[ ! -e "${build_root}" ]] || {
  printf 'BUILD_ROOT must be absent: %s\n' "${build_root}" >&2
  exit 1
}
[[ "$(sha256sum "${patch}" | awk '{print $1}')" == "${patch_sha256}" ]] || {
  printf 'determinism patch digest mismatch\n' >&2
  exit 1
}
[[ "$(docker image inspect "${base_image}" --format '{{.Id}}')" == "${expected_base_image_id}" ]] || {
  printf 'base image identity mismatch\n' >&2
  exit 1
}

mkdir -p "${build_root}"
git clone --filter=blob:none --no-checkout "${source_url}" "${source_dir}"
git -C "${source_dir}" checkout --detach "${kernel_head}"
[[ "$(git -C "${source_dir}" rev-parse HEAD)" == "${kernel_head}" ]] || {
  printf 'source checkout identity mismatch\n' >&2
  exit 1
}
git -C "${source_dir}" apply --check "${patch}"
git -C "${source_dir}" apply "${patch}"
git -C "${source_dir}" diff --check
mkdir -p "${dist_dir}" "${context_dir}"

docker run --rm --memory 16g --memory-swap 28g \
  --volume "${source_dir}:/src" \
  --volume "${dist_dir}:/out" \
  --volume "${host_oneapi_root}:/opt/intel/oneapi:ro" \
  --entrypoint /bin/bash "${base_image}" -lc '
    set -euo pipefail
    git config --global --add safe.directory /src
    source /opt/intel/oneapi/setvars.sh >/dev/null 2>&1
    cd /src
    MAX_JOBS=1 CMAKE_BUILD_TYPE=Release \
    BASIC_KERNELS_ENABLED=1 FA2_KERNELS_ENABLED=0 MOE_KERNELS_ENABLED=0 \
    GDN_KERNELS_ENABLED=0 MQA_LOGITS_KERNELS_ENABLED=0 \
    MHC_KERNELS_ENABLED=0 XPU_SPECIFIC_KERNELS_ENABLED=0 \
    XPUMEM_ALLOCATOR_ENABLED=0 BUILD_SYCL_TLA_KERNELS=0 \
    VLLM_XPU_ENABLE_XE2=0 VLLM_XPU_ENABLE_XE_DEFAULT=0 \
    /opt/venv/bin/python setup.py bdist_wheel \
      --dist-dir /out --py-limited-api=cp38
  '

mapfile -t wheels < <(find "${dist_dir}" -maxdepth 1 -type f -name '*.whl')
[[ "${#wheels[@]}" == 1 ]] || {
  printf 'expected exactly one wheel, found %s\n' "${#wheels[@]}" >&2
  exit 1
}
unzip -t "${wheels[0]}" >/dev/null
unzip -j "${wheels[0]}" vllm_xpu_kernels/_C.abi3.so -d "${context_dir}"
core_extension_sha256=$(sha256sum "${context_dir}/_C.abi3.so" | awk '{print $1}')
strings "${context_dir}/_C.abi3.so" | grep -Fq VLLM_XPU_ONEDNN_INT4_DETERMINISM_PAD

docker build --pull=false \
  --build-arg "BASE_IMAGE=${base_image}" \
  --build-arg "BASE_IMAGE_ID=${expected_base_image_id}" \
  --build-arg "KERNEL_HEAD=${kernel_head}" \
  --build-arg "PATCH_SHA256=${patch_sha256}" \
  --build-arg "CORE_EXTENSION_SHA256=${core_extension_sha256}" \
  --file "${dockerfile}" --tag "${image}" "${context_dir}"

[[ "$(docker image inspect "${image}" --format '{{ index .Config.Labels "neural.download.kernel.head" }}')" == "${kernel_head}" ]] || {
  printf 'built image kernel-head label mismatch\n' >&2
  exit 1
}
[[ "$(docker image inspect "${image}" --format '{{ index .Config.Labels "neural.download.kernel.patch.sha256" }}')" == "${patch_sha256}" ]] || {
  printf 'built image patch label mismatch\n' >&2
  exit 1
}
[[ "$(docker image inspect "${image}" --format '{{ index .Config.Labels "neural.download.kernel.core-extension.sha256" }}')" == "${core_extension_sha256}" ]] || {
  printf 'built image extension label mismatch\n' >&2
  exit 1
}

printf '%s\n' \
  "source_head=${kernel_head}" \
  "patch_sha256=${patch_sha256}" \
  "wheel=$(basename -- "${wheels[0]}")" \
  "wheel_sha256=$(sha256sum "${wheels[0]}" | awk '{print $1}')" \
  "core_extension_sha256=${core_extension_sha256}" \
  "base_image=${base_image}" \
  "base_image_id=${expected_base_image_id}" \
  "image=${image}" \
  "image_id=$(docker image inspect "${image}" --format '{{.Id}}')"
