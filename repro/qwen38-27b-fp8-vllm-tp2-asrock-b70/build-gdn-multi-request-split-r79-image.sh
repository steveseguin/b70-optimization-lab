#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/../.." && pwd)
build_root=${BUILD_ROOT:?set BUILD_ROOT to a new dedicated writable directory}
host_oneapi_root=${HOST_ONEAPI_ROOT:-/opt/intel/oneapi}
base_image=${BASE_IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-draft-only-int4-r62}
expected_base_id=${EXPECTED_BASE_IMAGE_ID:-sha256:cac17acf96ebbf65bfbe98e45dcea8eb5626c2b027dcac0228bc3bcba0063374}
image=${IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-gdn-multi-request-split-r79}
kernel_head=1e90ffa672ba02f17a909da11838a4c55b199783
source_url=https://github.com/vllm-project/vllm-xpu-kernels.git
source_dir=${build_root}/vllm-xpu-kernels-${kernel_head}
dist_dir=${build_root}/dist
context_dir=${build_root}/overlay-context
patch_file=${repo_root}/experiments/qwen38-27b-b70/patches/vllm-xpu-kernels-qwen38-gdn-multi-request-split-r79-20260901.patch
expected_patch_sha256=beaaf5313d8f0447b8fea5a4c44795b4045794e0bcd1475cf3cd4b14c97a3e46
dockerfile=${script_dir}/Dockerfile.gdn-multi-request-split-r79

for command_name in docker git patch readelf sha256sum unzip; do
  command -v "${command_name}" >/dev/null || {
    printf 'ERROR: required command is missing: %s\n' "${command_name}" >&2
    exit 2
  }
done
for required in "${dockerfile}" "${patch_file}" "${host_oneapi_root}/setvars.sh"; do
  [[ -e "${required}" ]] || {
    printf 'ERROR: missing build input: %s\n' "${required}" >&2
    exit 2
  }
done
[[ "$(sha256sum "${patch_file}" | awk '{print $1}')" == "${expected_patch_sha256}" ]] || {
  printf 'ERROR: cumulative GDN diagnostic patch mismatch\n' >&2
  exit 2
}
[[ ! -e "${build_root}" ]] || {
  printf 'ERROR: BUILD_ROOT must not already exist: %s\n' "${build_root}" >&2
  exit 2
}
[[ "$(docker image inspect "${base_image}" --format '{{.Id}}')" == "${expected_base_id}" ]] || {
  printf 'ERROR: R62 base image mismatch\n' >&2
  exit 2
}

mkdir -p "${build_root}"
git clone --filter=blob:none --no-checkout "${source_url}" "${source_dir}"
git -C "${source_dir}" checkout --detach "${kernel_head}"
[[ "$(git -C "${source_dir}" rev-parse HEAD)" == "${kernel_head}" ]] || {
  printf 'ERROR: source checkout is not pinned\n' >&2
  exit 2
}
git -C "${source_dir}" apply --check "${patch_file}"
git -C "${source_dir}" apply "${patch_file}"
git -C "${source_dir}" diff --check
mkdir -p "${dist_dir}" "${context_dir}"

docker run --rm --memory 14g --memory-swap 28g \
  --volume "${source_dir}:/src" \
  --volume "${dist_dir}:/out" \
  --volume "${host_oneapi_root}:/opt/intel/oneapi:ro" \
  --entrypoint /bin/bash "${base_image}" -lc '
    set -eo pipefail
    git config --global --add safe.directory /src
    source /opt/intel/oneapi/setvars.sh >/dev/null 2>&1
    set -u
    compiler_line=$(icpx --version | sed -n "1p")
    expected_compiler_line='"'"'Intel(R) oneAPI DPC++/C++ Compiler 2026.1.1 (2026.1.1.20260724)'"'"'
    [[ "${compiler_line}" == "${expected_compiler_line}" ]] || {
      printf '"'"'ERROR: compiler identity mismatch\nexpected=%s\nactual=%s\n'"'"' \
        "${expected_compiler_line}" "${compiler_line}" >&2
      exit 2
    }
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
  printf 'ERROR: expected exactly one wheel, found %s\n' "${#wheels[@]}" >&2
  exit 2
}
unzip -t "${wheels[0]}" >/dev/null
unzip -j "${wheels[0]}" \
  vllm_xpu_kernels/_xpu_C.abi3.so \
  vllm_xpu_kernels/libgdn_attn_kernels_xe_2.so \
  -d "${context_dir}"
xpu_extension_sha256=$(sha256sum "${context_dir}/_xpu_C.abi3.so" | awk '{print $1}')
gdn_library_sha256=$(sha256sum "${context_dir}/libgdn_attn_kernels_xe_2.so" | awk '{print $1}')
for library in "${context_dir}/_xpu_C.abi3.so" \
  "${context_dir}/libgdn_attn_kernels_xe_2.so"; do
  readelf -d "${library}" | grep -Fq 'Library runpath: [$ORIGIN]' || {
    printf 'ERROR: non-portable RUNPATH in %s\n' "${library}" >&2
    exit 2
  }
done

docker build --pull=false \
  --build-arg "BASE_IMAGE=${base_image}" \
  --build-arg "GDN_MULTI_PATCH_SHA256=${expected_patch_sha256}" \
  --build-arg "XPU_EXTENSION_SHA256=${xpu_extension_sha256}" \
  --build-arg "GDN_LIBRARY_SHA256=${gdn_library_sha256}" \
  --file "${dockerfile}" --tag "${image}" "${context_dir}"

printf '%s\n' \
  "wheel=$(basename -- "${wheels[0]}")" \
  "wheel_sha256=$(sha256sum "${wheels[0]}" | awk '{print $1}')" \
  "xpu_extension_sha256=${xpu_extension_sha256}" \
  "gdn_library_sha256=${gdn_library_sha256}" \
  "patch_sha256=${expected_patch_sha256}" \
  "image=${image}" \
  "image_id=$(docker image inspect "${image}" --format '{{.Id}}')"
