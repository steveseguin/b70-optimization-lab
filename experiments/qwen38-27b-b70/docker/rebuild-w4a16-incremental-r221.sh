#!/usr/bin/env bash
# R221 (2026-09-05): incremental rebuild of _xpu_C in an existing R220 BUILD_ROOT with a replacement oneDNN patch
# (the R220 override/dump patch is reverted, the R221 two-tier fixed-K patch applied), then a new image on the R213b base.
# usage: BUILD_ROOT=<r220 build root> bash rebuild-w4a16-incremental-r221.sh
set -euo pipefail
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd); repo_root=$(cd -- "${script_dir}/../../.." && pwd)
build_root=${BUILD_ROOT:?}; host_oneapi_root=${HOST_ONEAPI_ROOT:-/opt/intel/oneapi}
base_image=${BASE_IMAGE:-neural-download/vllm-openai-xpu:qwen38-int4-w4a16-detpad-op-r213b}
image=${IMAGE:-neural-download/vllm-openai-xpu:qwen38-int4-w4a16-fixed-k-r221}
old_patch=${repo_root}/experiments/qwen38-27b-b70/patches/onednn-qwen38-w4a16-strategy-override-dump-r220-20260905.patch
new_patch=${NEW_PATCH:-${repo_root}/experiments/qwen38-27b-b70/patches/onednn-qwen38-w4a16-fixed-k-two-tier-r221-20260905.patch}
onednn_dir=${build_root}/onednn; source_dir=${build_root}/vllm-xpu-kernels; compile_dir=${build_root}/compile; context_dir=${build_root}/context-r221
git -C "${onednn_dir}" apply --check -R "${old_patch}" && git -C "${onednn_dir}" apply -R "${old_patch}" || true
git -C "${onednn_dir}" apply "${new_patch}"; git -C "${onednn_dir}" diff --check
mkdir -p "${context_dir}"
docker run --rm --network none --memory 14g --memory-swap 28g --entrypoint /bin/bash \
  --volume "${host_oneapi_root}:/opt/intel/oneapi:ro" --volume "${source_dir}:/src:ro" --volume "${compile_dir}:/run" \
  --volume "${onednn_dir}:/deps/onednn:ro" --volume "${build_root}/sycl-tla:/deps/cutlass:ro" --volume "${repo_root}:/lab:ro" \
  --env KERNELS_DIR=/src --env VENV_DIR=/opt/venv --env ONEAPI_VARS=/opt/intel/oneapi/compiler/2026.1/env/vars.sh \
  --env BUILD_DIR=/run/build --env INSTALL_PREFIX=/run/install --env FETCHCONTENT_DIR=/run/fetchcontent \
  --env ONEDNN_SOURCE=/deps/onednn --env CUTLASS_SOURCE=/deps/cutlass --env AOT_DEVICES=bmg-g21-a0 --env JOBS="${JOBS:-12}" \
  --env GDN_KERNELS=ON --env MOE_KERNELS=OFF "${base_image}" /lab/scripts/build-vllm-xpu-kernels-xpu-c-only.sh
install -m 0755 "${compile_dir}/install/vllm_xpu_kernels/_xpu_C.abi3.so" "${context_dir}/_xpu_C.abi3.so"
xpu_sha256=$(sha256sum "${context_dir}/_xpu_C.abi3.so" | awk '{print $1}')
strings "${context_dir}/_xpu_C.abi3.so" | grep -Fq QWEN38_W4A16_FIXED_K
docker build --pull=false --build-arg "BASE_IMAGE=${base_image}" --build-arg "XPU_EXTENSION_SHA256=${xpu_sha256}" \
  --build-arg "ONEDNN_PATCH_SHA256=$(sha256sum "${new_patch}" | awk '{print $1}')" --file "${script_dir}/Dockerfile.w4a16-strategy-r220" --tag "${image}" "${context_dir}"
printf 'image=%s\nimage_id=%s\nxpu_extension_sha256=%s\n' "${image}" "$(docker image inspect "${image}" --format '{{.Id}}')" "${xpu_sha256}"
