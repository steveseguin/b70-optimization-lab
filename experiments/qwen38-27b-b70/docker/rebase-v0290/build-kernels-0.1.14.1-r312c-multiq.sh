#!/usr/bin/env bash
# R312c kernel library (2026-09-18): the R311 build plus vllm-xpu-kernels patch r312 in its final form: the multi-position
# verifier attention op `paged_decode_multiq` in the _xpu_C extension with its own device library
# (libattn_multiq_kernels_xe_2.so). The upstream flash-attention extension and device library are neither built nor
# installed (rebuilding them changed rounding: DO-NOT-REPEAT 2026-09-17). Same builder and flags as r311; the compile
# tree is copied from the R311 build root so ninja rebuilds only the new objects. Build with the service stopped.
set -euo pipefail
lab=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../../.." && pwd)
r310=${R310_ROOT:-/mnt/fast-ai/build/kernels-r310-gdn-barriers-20260915}
r311=${R311_ROOT:-/mnt/fast-ai/build/kernels-r311-gdn-checkpoint-20260917}
source_tree=${SOURCE_TREE:?set SOURCE_TREE to the r312 vllm-xpu-kernels checkout}
build_root=${BUILD_ROOT:?set BUILD_ROOT to a new empty directory}
resume=${RESUME:-0}
[[ "${resume}" == 1 || ! -e "${build_root}" ]] || { echo "BUILD_ROOT exists: ${build_root}" >&2; exit 1; }
base=${BASE_IMAGE:-vllm/vllm-openai-xpu@sha256:96db42e248d48760a4937eb3d04c4878b39d13a9814efea95d510393e097a901}
if [[ "${resume}" != 1 ]]; then
  mkdir -p "${build_root}"
  cp -a "${source_tree}" "${build_root}/vllm-xpu-kernels"
  git -C "${build_root}/vllm-xpu-kernels" rev-parse HEAD > "${build_root}/source-commit.txt"
  cp -a "${r311}/compile" "${build_root}/compile"
fi
cd "${build_root}"
t0=$(date +%s)
docker run --rm --network none --memory "${BUILD_MEMORY:-14g}" --memory-swap "${BUILD_MEMORY_SWAP:-28g}" --entrypoint /bin/bash \
  --volume /opt/intel/oneapi:/opt/intel/oneapi:ro --volume "${build_root}/vllm-xpu-kernels:/src:ro" --volume "${build_root}/compile:/run" \
  --volume "${r310}/onednn:/deps/onednn:ro" --volume "${r310}/sycl-tla:/deps/cutlass:ro" --volume "${lab}:/lab:ro" \
  --env KERNELS_DIR=/src --env VENV_DIR=/opt/venv --env ONEAPI_VARS=/opt/intel/oneapi/compiler/2026.1/env/vars.sh \
  --env BUILD_DIR=/run/build --env INSTALL_PREFIX=/run/install --env FETCHCONTENT_DIR=/run/fetchcontent \
  --env ONEDNN_SOURCE=/deps/onednn --env CUTLASS_SOURCE=/deps/cutlass --env AOT_DEVICES=bmg-g21-a0 --env JOBS="${JOBS:-2}" \
  --env GDN_KERNELS=ON --env MOE_KERNELS=OFF "${base}" /lab/scripts/build-vllm-xpu-kernels-xpu-c-only.sh
echo "kernel build took $(( $(date +%s) - t0 )) s"
out=${build_root}/compile/install/vllm_xpu_kernels
readelf -d "${out}/_xpu_C.abi3.so" | grep -Fq 'Library runpath: [$ORIGIN]' || { echo "non-portable RUNPATH on _xpu_C" >&2; exit 1; }
[[ -f "${out}/libattn_multiq_kernels_xe_2.so" ]] || { echo "multiq device library missing" >&2; exit 1; }
sha256sum "${out}/_xpu_C.abi3.so" "${out}/libgdn_attn_kernels_xe_2.so" "${out}/libattn_multiq_kernels_xe_2.so"
