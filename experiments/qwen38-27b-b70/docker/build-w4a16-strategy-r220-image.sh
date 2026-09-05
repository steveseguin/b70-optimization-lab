#!/usr/bin/env bash
# R220 (2026-09-05): the R139 kernel-library build plus the W4A16 strategy override/dump oneDNN patch, on the R213b base. See Dockerfile.w4a16-strategy-r220.
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/../.." && pwd)
build_root=${BUILD_ROOT:?set BUILD_ROOT to a new empty local build directory}
host_oneapi_root=${HOST_ONEAPI_ROOT:-/opt/intel/oneapi}
base_image=${BASE_IMAGE:-neural-download/vllm-openai-xpu:qwen38-int4-w4a16-detpad-op-r213b}
expected_base_id=${EXPECTED_BASE_IMAGE_ID:-sha256:cbdc81afe43c28ccd523f6e858c09146f0a4a667a97082a2f1f44dffa3cb8144}
image=${IMAGE:-neural-download/vllm-openai-xpu:qwen38-int4-w4a16-strategy-r220}

kernel_head=1e90ffa672ba02f17a909da11838a4c55b199783
onednn_head=0e2a5bfeef1bfbffc3137464606540233086ce9b
cutlass_head=cd763790ad2f74d7294435ecf77682bac0062c3a
source_dir=${build_root}/vllm-xpu-kernels
onednn_dir=${build_root}/onednn
cutlass_dir=${build_root}/sycl-tla
compile_dir=${build_root}/compile
context_dir=${build_root}/context

gdn_base_patch=${repo_root}/experiments/qwen38-27b-b70/patches/vllm-xpu-kernels-qwen38-dynamic-active-width-serial-gdn-r35-20260828.patch
gdn_split_patch=${repo_root}/experiments/qwen38-27b-b70/patches/vllm-xpu-kernels-qwen38-gdn-split-serial-gates-r50-20260901.patch
fixed_k_patch=${repo_root}/experiments/qwen38-27b-b70/patches/onednn-qwen38-w8a16-fixed-k-align16-r137a-20260902.patch
c_align_patch=${repo_root}/experiments/qwen38-27b-b70/patches/onednn-qwen38-w8a16-c-default-align-r137b-20260902.patch
w4a16_patch=${repo_root}/experiments/qwen38-27b-b70/patches/onednn-qwen38-w4a16-strategy-override-dump-r220-20260905.patch
builder=${repo_root}/scripts/build-vllm-xpu-kernels-xpu-c-only.sh
dockerfile=${repo_root}/experiments/qwen38-27b-b70/docker/Dockerfile.w4a16-strategy-r220

expected_gdn_base_sha256=ad583014c92b8611a9e4e87868a3d492c3b6802ee557814b9ec794f147cd973e
expected_gdn_split_sha256=40ca8c3fc15fea1b7dda8d268761f0b1339eb821f5d8357b3da7600585fe750f
expected_fixed_k_sha256=5d2a93f0a36fa89f0ef13cf21ed5332a72491dd5856519bbe2eb21414112464f
expected_c_align_sha256=feb4f125f69b36dbc3f579ad93743abe655678b7540ba2743fcff797fe35ebd9
expected_w4a16_sha256=63873506f3031d36193c9746be3a26239cbf230582c0fb296d9e90a4d92ed464
expected_builder_sha256=5cbdadc200626ed9da03b6aa4808a59ee848348c671ce76d4d7ada4a37ca464f

for command_name in docker git readelf sha256sum; do
  command -v "${command_name}" >/dev/null || {
    printf '%s is required\n' "${command_name}" >&2
    exit 1
  }
done
[[ ! -e "${build_root}" ]] || {
  printf 'BUILD_ROOT must not already exist: %s\n' "${build_root}" >&2
  exit 1
}
[[ "$(docker image inspect "${base_image}" --format '{{.Id}}')" == "${expected_base_id}" ]] || {
  printf 'base image identity mismatch\n' >&2
  exit 1
}

check_hash() {
  local expected=$1 file=$2
  [[ "$(sha256sum "${file}" | awk '{print $1}')" == "${expected}" ]] || {
    printf 'input identity mismatch: %s\n' "${file}" >&2
    exit 1
  }
}
check_hash "${expected_gdn_base_sha256}" "${gdn_base_patch}"
check_hash "${expected_gdn_split_sha256}" "${gdn_split_patch}"
check_hash "${expected_fixed_k_sha256}" "${fixed_k_patch}"
check_hash "${expected_c_align_sha256}" "${c_align_patch}"
check_hash "${expected_w4a16_sha256}" "${w4a16_patch}"
check_hash "${expected_builder_sha256}" "${builder}"

mkdir -p "${build_root}"
git clone --filter=blob:none --no-checkout https://github.com/vllm-project/vllm-xpu-kernels.git "${source_dir}"
git -C "${source_dir}" checkout --detach "${kernel_head}"
git -C "${source_dir}" apply "${gdn_base_patch}"
git -C "${source_dir}" apply "${gdn_split_patch}"
git -C "${source_dir}" diff --check

git clone --filter=blob:none --no-checkout https://github.com/uxlfoundation/oneDNN.git "${onednn_dir}"
git -C "${onednn_dir}" checkout --detach "${onednn_head}"
git -C "${onednn_dir}" apply "${fixed_k_patch}"
git -C "${onednn_dir}" apply "${c_align_patch}"
git -C "${onednn_dir}" apply "${w4a16_patch}"
git -C "${onednn_dir}" diff --check

git clone --filter=blob:none --no-checkout https://github.com/intel/sycl-tla.git "${cutlass_dir}"
git -C "${cutlass_dir}" checkout --detach "${cutlass_head}"

mkdir -p "${compile_dir}" "${context_dir}"
docker run --rm --network none --memory 14g --memory-swap 28g --entrypoint /bin/bash \
  --volume "${host_oneapi_root}:/opt/intel/oneapi:ro" \
  --volume "${source_dir}:/src:ro" \
  --volume "${compile_dir}:/run" \
  --volume "${onednn_dir}:/deps/onednn:ro" \
  --volume "${cutlass_dir}:/deps/cutlass:ro" \
  --volume "${repo_root}:/lab:ro" \
  --env KERNELS_DIR=/src --env VENV_DIR=/opt/venv \
  --env ONEAPI_VARS=/opt/intel/oneapi/compiler/2026.1/env/vars.sh \
  --env BUILD_DIR=/run/build --env INSTALL_PREFIX=/run/install \
  --env FETCHCONTENT_DIR=/run/fetchcontent \
  --env ONEDNN_SOURCE=/deps/onednn --env CUTLASS_SOURCE=/deps/cutlass \
  --env AOT_DEVICES=bmg-g21-a0 --env JOBS="${JOBS:-12}" \
  --env GDN_KERNELS=ON --env MOE_KERNELS=OFF \
  "${base_image}" /lab/scripts/build-vllm-xpu-kernels-xpu-c-only.sh

install -m 0755 "${compile_dir}/install/vllm_xpu_kernels/_xpu_C.abi3.so" "${context_dir}/_xpu_C.abi3.so"

xpu_sha256=$(sha256sum "${context_dir}/_xpu_C.abi3.so" | awk '{print $1}')
for library in "${context_dir}"/*.so; do
  readelf -d "${library}" | grep -Fq 'Library runpath: [$ORIGIN]' || {
    printf 'non-portable RUNPATH: %s\n' "${library}" >&2
    exit 1
  }
done

docker build --pull=false \
  --build-arg "BASE_IMAGE=${base_image}" \
  --build-arg "XPU_EXTENSION_SHA256=${xpu_sha256}" \
  --build-arg "ONEDNN_PATCH_SHA256=${expected_fixed_k_sha256}+${expected_c_align_sha256}+${expected_w4a16_sha256}" \
  --file "${dockerfile}" --tag "${image}" "${context_dir}"

docker run --rm --network none --entrypoint /bin/bash "${image}" -lc \
  'python -c "import torch; import vllm_xpu_kernels._xpu_C; print(torch.__version__)"'
printf 'image=%s\nimage_id=%s\nxpu_extension_sha256=%s\ngdn_library_sha256=%s\nmhc_library_sha256=%s\n' \
  "${image}" "$(docker image inspect "${image}" --format '{{.Id}}')" \
  "${xpu_sha256}" \
  "$(docker run --rm --network none --entrypoint sha256sum "${image}" /opt/venv/lib/python3.12/site-packages/vllm_xpu_kernels/libgdn_attn_kernels_xe_2.so | awk '{print $1}')" \
  "$(docker run --rm --network none --entrypoint sha256sum "${image}" /opt/venv/lib/python3.12/site-packages/vllm_xpu_kernels/libmhc_kernels_xe_2.so | awk '{print $1}')"
