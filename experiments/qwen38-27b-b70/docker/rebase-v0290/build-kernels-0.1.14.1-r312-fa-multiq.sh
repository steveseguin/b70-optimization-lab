#!/usr/bin/env bash
# R312 kernel library (2026-09-17/18): the R311 build plus vllm-xpu-kernels patch r312 (multi-position paged-decode
# attention op `paged_decode_multiq` for the speculative verifier: one pass over the KV cache for all draft rows with
# the single-row arithmetic) and, for the first time, the flash-attention extension rebuilt from source (default kernel
# sets), since the new op lives in it. The oneDNN and sycl-tla trees are reused read-only from the R310 build root; the
# compile tree is copied from the R311 build root so ninja rebuilds only the attention objects and the new files.
# Build with the service stopped (14 GB cap). SOURCE_TREE names a prepared checkout (the r312 dev tree with its commits).
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
  --env ONEDNN_SOURCE=/deps/onednn --env CUTLASS_SOURCE=/deps/cutlass --env AOT_DEVICES=bmg-g21-a0 --env JOBS="${JOBS:-6}" \
  --env GDN_KERNELS=ON --env MOE_KERNELS=OFF --env FA2_KERNELS=ON \
  --env PAGED_DECODE_CONFIG="${PAGED_DECODE_CONFIG:-paged_decode_default.conf}" --env CHUNK_PREFILL_CONFIG="${CHUNK_PREFILL_CONFIG:-chunk_prefill_default.conf}" \
  "${base}" /lab/scripts/build-vllm-xpu-kernels-xpu-c-fa2.sh
echo "kernel build took $(( $(date +%s) - t0 )) s"
out=${build_root}/compile/install/vllm_xpu_kernels
for f in _xpu_C.abi3.so _vllm_fa2_C.abi3.so; do
  readelf -d "${out}/${f}" | grep -Fq 'Library runpath: [$ORIGIN]' || { echo "non-portable RUNPATH on ${f}" >&2; exit 1; }
done
sha256sum "${out}/_xpu_C.abi3.so" "${out}/_vllm_fa2_C.abi3.so" "${out}/libgdn_attn_kernels_xe_2.so" "${out}/libattn_kernels_xe_2.so"
