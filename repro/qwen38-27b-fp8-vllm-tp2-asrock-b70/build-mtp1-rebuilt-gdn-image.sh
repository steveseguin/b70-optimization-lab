#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/../.." && pwd)
build_root=${BUILD_ROOT:?set BUILD_ROOT to a new dedicated writable directory}
host_oneapi_root=${HOST_ONEAPI_ROOT:-/opt/intel/oneapi}
base_image=${BASE_IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-serial-attention-r49}
image=${IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-serial-fa-split-gdn-r50}
kernel_head=1e90ffa672ba02f17a909da11838a4c55b199783
source_url=https://github.com/vllm-project/vllm-xpu-kernels.git
source_dir=${build_root}/vllm-xpu-kernels-${kernel_head}
dist_dir=${build_root}/dist
context_dir=${build_root}/overlay-context
base_gdn_patch=${repo_root}/experiments/qwen38-27b-b70/patches/vllm-xpu-kernels-qwen38-dynamic-active-width-serial-gdn-r35-20260828.patch
split_gdn_patch=${repo_root}/experiments/qwen38-27b-b70/patches/vllm-xpu-kernels-qwen38-gdn-split-serial-gates-r50-20260901.patch
base_gdn_patch_sha256=ad583014c92b8611a9e4e87868a3d492c3b6802ee557814b9ec794f147cd973e
split_gdn_patch_sha256=40ca8c3fc15fea1b7dda8d268761f0b1339eb821f5d8357b3da7600585fe750f
expected_xpu_extension_sha256=1632cafcf2afc0bc039dd49ebbb5eda4e62d626f4c20729aecd9e87874d1dc08
expected_gdn_library_sha256=2c343620d689409bfa371a8b4c3db680e4786f23bc092411e7d03140f1b2a355
expected_xpu_text_sha256=50b4ce36788ba69261825e1d7af95937e4f40521c9da5d9b909416a99298292e
expected_xpu_rodata_sha256=7d44f5949e29e6db50a6eec4aa8f6de46066fad928ad81ab47ee95a9cbec42ec
expected_xpu_data_sha256=4ab38b348d753193ee9684d9c7bede755918a7c3d13f53e35925cc293391a7aa
expected_gdn_text_sha256=1640dcf159af927e5282c45b80aad25e2c78d50521b46b35203ed92556b32914
expected_gdn_rodata_sha256=3a15b3ec75f8af75b4b41196ab4f32e68c1f8015a4f385c9c5751be8e8f2b6ca
expected_gdn_data_sha256=154c9111c82ac7509d6245b64d84a8cc29e34d499ee7e9a6495f29f915a699d7
dockerfile=${script_dir}/Dockerfile.mtp1-rebuilt-gdn

for command_name in docker git objcopy patch readelf sha256sum unzip; do
  command -v "${command_name}" >/dev/null || {
    printf '%s is required\n' "${command_name}" >&2
    exit 1
  }
done
for required in "${dockerfile}" "${base_gdn_patch}" "${split_gdn_patch}" \
  "${host_oneapi_root}/setvars.sh"; do
  [[ -e "${required}" ]] || { printf 'missing build input: %s\n' "${required}" >&2; exit 1; }
done
[[ "$(sha256sum "${base_gdn_patch}" | awk '{print $1}')" == "${base_gdn_patch_sha256}" ]] || {
  printf 'base GDN patch digest mismatch\n' >&2
  exit 1
}
[[ "$(sha256sum "${split_gdn_patch}" | awk '{print $1}')" == "${split_gdn_patch_sha256}" ]] || {
  printf 'split GDN patch digest mismatch\n' >&2
  exit 1
}
[[ ! -e "${build_root}" ]] || {
  printf 'BUILD_ROOT must not already exist: %s\n' "${build_root}" >&2
  exit 1
}

"${script_dir}/verify-image-contract.sh" mtp1-serial-fa "${base_image}"
mkdir -p "${build_root}"
git clone --filter=blob:none --no-checkout "${source_url}" "${source_dir}"
git -C "${source_dir}" checkout --detach "${kernel_head}"
[[ "$(git -C "${source_dir}" rev-parse HEAD)" == "${kernel_head}" ]] || {
  printf 'source checkout is not pinned commit %s\n' "${kernel_head}" >&2
  exit 1
}
git -C "${source_dir}" apply --check "${base_gdn_patch}"
git -C "${source_dir}" apply "${base_gdn_patch}"
git -C "${source_dir}" apply --check "${split_gdn_patch}"
git -C "${source_dir}" apply "${split_gdn_patch}"
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
      printf '"'"'compiler identity mismatch: expected %s, found %s\n'"'"' \
        "${expected_compiler_line}" "${compiler_line}" >&2
      exit 1
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
[[ "${xpu_extension_sha256}" == "${expected_xpu_extension_sha256}" ]] || {
  printf 'rebuilt XPU extension digest mismatch: %s\n' "${xpu_extension_sha256}" >&2
  exit 1
}
[[ "${gdn_library_sha256}" == "${expected_gdn_library_sha256}" ]] || {
  printf 'rebuilt GDN library digest mismatch: %s\n' "${gdn_library_sha256}" >&2
  exit 1
}

# Whole ELF digests are checked above for this pinned clean build. Also bind
# the executable/read-only/data sections: the earlier lab image differs only
# in .dynstr because it retained a host-specific runpath string, while these
# code-bearing sections are byte-identical. Clean builds must use $ORIGIN.
verify_section() {
  local library=$1 section=$2 expected_sha256=$3 output
  output=${context_dir}/$(basename -- "${library}").${section#.}
  objcopy --dump-section "${section}=${output}" "${library}"
  [[ "$(sha256sum "${output}" | awk '{print $1}')" == "${expected_sha256}" ]] || {
    printf 'section digest mismatch: %s %s\n' "${library}" "${section}" >&2
    exit 1
  }
  rm -f "${output}"
}
verify_section "${context_dir}/_xpu_C.abi3.so" .text "${expected_xpu_text_sha256}"
verify_section "${context_dir}/_xpu_C.abi3.so" .rodata "${expected_xpu_rodata_sha256}"
verify_section "${context_dir}/_xpu_C.abi3.so" .data "${expected_xpu_data_sha256}"
verify_section "${context_dir}/libgdn_attn_kernels_xe_2.so" .text "${expected_gdn_text_sha256}"
verify_section "${context_dir}/libgdn_attn_kernels_xe_2.so" .rodata "${expected_gdn_rodata_sha256}"
verify_section "${context_dir}/libgdn_attn_kernels_xe_2.so" .data "${expected_gdn_data_sha256}"
for library in "${context_dir}/_xpu_C.abi3.so" \
  "${context_dir}/libgdn_attn_kernels_xe_2.so"; do
  readelf -d "${library}" | grep -Fq 'Library runpath: [$ORIGIN]' || {
    printf 'non-portable RUNPATH in rebuilt library: %s\n' "${library}" >&2
    exit 1
  }
done

docker build --pull=false \
  --build-arg "BASE_IMAGE=${base_image}" \
  --build-arg "BASE_GDN_PATCH_SHA256=${base_gdn_patch_sha256}" \
  --build-arg "SPLIT_GDN_PATCH_SHA256=${split_gdn_patch_sha256}" \
  --build-arg "XPU_EXTENSION_SHA256=${xpu_extension_sha256}" \
  --build-arg "GDN_LIBRARY_SHA256=${gdn_library_sha256}" \
  --file "${dockerfile}" --tag "${image}" "${context_dir}"

printf '%s\n' \
  "wheel=$(basename -- "${wheels[0]}")" \
  "wheel_sha256=$(sha256sum "${wheels[0]}" | awk '{print $1}')" \
  "xpu_extension_sha256=${xpu_extension_sha256}" \
  "gdn_library_sha256=${gdn_library_sha256}" \
  "image=${image}" \
  "image_id=$(docker image inspect "${image}" --format '{{.Id}}')"
