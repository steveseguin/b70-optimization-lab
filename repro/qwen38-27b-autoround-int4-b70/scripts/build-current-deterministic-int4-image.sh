#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/../../.." && pwd)
build_root=${BUILD_ROOT:?set BUILD_ROOT to a dedicated, absent build directory}
host_oneapi_root=${HOST_ONEAPI_ROOT:-/opt/intel/oneapi}
base_image=${BASE_IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-rms-serial-r31}
expected_base_image_id=${EXPECTED_BASE_IMAGE_ID:?set EXPECTED_BASE_IMAGE_ID to the local base image ID}
image=${IMAGE:-neural-download/vllm-openai-xpu:qwen38-autoround-current-deterministic-r1}
max_jobs=${MAX_JOBS:-1}
resume_build=${RESUME_BUILD:-0}
build_container_memory=${BUILD_CONTAINER_MEMORY:-12g}
build_container_memory_swap=${BUILD_CONTAINER_MEMORY_SWAP:-28g}
kernel_head=1e90ffa672ba02f17a909da11838a4c55b199783
source_url=https://github.com/vllm-project/vllm-xpu-kernels.git
patch=${repo_root}/experiments/qwen38-27b-b70/patches/vllm-xpu-kernels-qwen38-onednn-int4-determinism-pad-kernel1e90-20260828.patch
patch_sha256=8237fd2a5f11c772269275598bc005d7a146f86de741cef753fc0ec74cb1a408
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
[[ "${max_jobs}" =~ ^[1-9][0-9]*$ ]] || {
  printf 'MAX_JOBS must be a positive integer\n' >&2
  exit 1
}
for required in "${patch}" "${dockerfile}" "${host_oneapi_root}/setvars.sh"; do
  [[ -e "${required}" ]] || { printf 'missing %s\n' "${required}" >&2; exit 1; }
done
[[ "${resume_build}" == 0 || "${resume_build}" == 1 ]] || {
  printf 'RESUME_BUILD must be 0 or 1\n' >&2
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

if [[ "${resume_build}" == 0 ]]; then
  [[ ! -e "${build_root}" ]] || {
    printf 'BUILD_ROOT must be absent: %s\n' "${build_root}" >&2
    exit 1
  }
  mkdir -p "${build_root}"
  git clone --filter=blob:none --no-checkout "${source_url}" "${source_dir}"
  git -C "${source_dir}" checkout --detach "${kernel_head}"
  git -C "${source_dir}" apply --check "${patch}"
  git -C "${source_dir}" apply "${patch}"
else
  [[ -d "${source_dir}/.git" ]] || {
    printf 'resume source checkout missing: %s\n' "${source_dir}" >&2
    exit 1
  }
  git -C "${source_dir}" apply --reverse --check "${patch}" || {
    printf 'resume source does not contain exactly the required patch\n' >&2
    exit 1
  }
fi
[[ "$(git -C "${source_dir}" rev-parse HEAD)" == "${kernel_head}" ]] || {
  printf 'source checkout identity mismatch\n' >&2
  exit 1
}
git -C "${source_dir}" diff --check
mapfile -t source_changes < <(git -C "${source_dir}" status --porcelain --untracked-files=all)
[[ "${#source_changes[@]}" == 1 && \
  "${source_changes[0]}" == ' M csrc/xpu/onednn/int4_gemm_w4a16.h' ]] || {
  printf 'source checkout contains changes outside the required patch\n' >&2
  printf '%s\n' "${source_changes[@]}" >&2
  exit 1
}
mkdir -p "${dist_dir}" "${context_dir}"

# Keep the cgroup RAM ceiling below physical host RAM. The largest Xe2
# translation unit needs roughly 15 GiB of anonymous memory; the separate swap
# ceiling lets it finish without forcing the host itself into a global OOM.
docker run --rm --memory "${build_container_memory}" \
  --memory-swap "${build_container_memory_swap}" \
  --volume "${source_dir}:/src" \
  --volume "${dist_dir}:/out" \
  --volume "${host_oneapi_root}:/opt/intel/oneapi:ro" \
  --env "MAX_JOBS=${max_jobs}" \
  --entrypoint /bin/bash "${base_image}" -lc '
    set -eo pipefail
    git config --global --add safe.directory /src
    source /opt/intel/oneapi/setvars.sh >/dev/null 2>&1
    set -u
    expected_compiler="Intel(R) oneAPI DPC++/C++ Compiler 2026.1.1 (2026.1.1.20260724)"
    [[ "$(icpx --version | sed -n "1p")" == "${expected_compiler}" ]] || {
      printf "compiler identity mismatch\n" >&2
      exit 1
    }
    cd /src
    # This Qwen3.8-27B lane is dense, not MoE. Keep the Xe2 TLA libraries its
    # _xpu_C surface actually calls (GDN/MQA/MHC), but do not build grouped-MoE
    # GEMM: that unused translation unit exceeds 30 GiB and cannot affect this
    # model. Disabling all TLA libraries makes the overlay fail to import with
    # unresolved MHC symbols.
    MAX_JOBS="${MAX_JOBS}" CMAKE_BUILD_TYPE=Release \
    BASIC_KERNELS_ENABLED=0 FA2_KERNELS_ENABLED=0 MOE_KERNELS_ENABLED=0 \
    GDN_KERNELS_ENABLED=1 MQA_LOGITS_KERNELS_ENABLED=1 \
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
strings "${context_dir}/_xpu_C.abi3.so" | grep -Fq VLLM_XPU_ONEDNN_INT4_DETERMINISM_PAD

docker build --pull=false \
  --build-arg "BASE_IMAGE=${base_image}" \
  --build-arg "BASE_IMAGE_ID=${expected_base_image_id}" \
  --build-arg "KERNEL_HEAD=${kernel_head}" \
  --build-arg "PATCH_SHA256=${patch_sha256}" \
  --build-arg "XPU_EXTENSION_SHA256=${xpu_extension_sha256}" \
  --build-arg "GDN_LIBRARY_SHA256=${gdn_library_sha256}" \
  --file "${dockerfile}" --tag "${image}" "${context_dir}"

[[ "$(docker image inspect "${image}" --format '{{ index .Config.Labels "neural.download.kernel.head" }}')" == "${kernel_head}" ]] || {
  printf 'built image kernel-head label mismatch\n' >&2
  exit 1
}
[[ "$(docker image inspect "${image}" --format '{{ index .Config.Labels "neural.download.kernel.patch.sha256" }}')" == "${patch_sha256}" ]] || {
  printf 'built image patch label mismatch\n' >&2
  exit 1
}
[[ "$(docker image inspect "${image}" --format '{{ index .Config.Labels "neural.download.kernel.xpu-extension.sha256" }}')" == "${xpu_extension_sha256}" ]] || {
  printf 'built image XPU-extension label mismatch\n' >&2
  exit 1
}
[[ "$(docker image inspect "${image}" --format '{{ index .Config.Labels "neural.download.kernel.gdn-library.sha256" }}')" == "${gdn_library_sha256}" ]] || {
  printf 'built image GDN-library label mismatch\n' >&2
  exit 1
}

printf '%s\n' \
  "source_head=${kernel_head}" \
  "patch_sha256=${patch_sha256}" \
  "wheel=$(basename -- "${wheels[0]}")" \
  "wheel_sha256=$(sha256sum "${wheels[0]}" | awk '{print $1}')" \
  "xpu_extension_sha256=${xpu_extension_sha256}" \
  "gdn_library_sha256=${gdn_library_sha256}" \
  "base_image=${base_image}" \
  "base_image_id=${expected_base_image_id}" \
  "image=${image}" \
  "image_id=$(docker image inspect "${image}" --format '{{.Id}}')"
