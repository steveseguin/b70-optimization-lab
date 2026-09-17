#!/usr/bin/env bash
# R311 kernel library (2026-09-17): the R310 build plus vllm-xpu-kernels patch r311 (single-checkpoint speculative
# GDN state: `gdn_attention_ckpt`, replay-commit of the accepted prefix from an in-page stash; the existing ops are
# untouched). Same sources, builder and flags as build-kernels-0.1.14.1-r310-gdn-barriers.sh. The oneDNN and sycl-tla
# trees are reused read-only from the R310 build root; the compile tree is copied from it so ninja rebuilds only the
# GDN objects.
set -euo pipefail
lab=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../../.." && pwd)
r310=${R310_ROOT:-/mnt/fast-ai/build/kernels-r310-gdn-barriers-20260915}
build_root=${BUILD_ROOT:?set BUILD_ROOT to a new empty directory}
[[ ! -e "${build_root}" ]] || { echo "BUILD_ROOT exists: ${build_root}" >&2; exit 1; }
base=${BASE_IMAGE:-vllm/vllm-openai-xpu@sha256:96db42e248d48760a4937eb3d04c4878b39d13a9814efea95d510393e097a901}
P=${lab}/experiments/qwen38-27b-b70/patches
mkdir -p "${build_root}"
git clone --no-checkout https://github.com/vllm-project/vllm-xpu-kernels.git "${build_root}/vllm-xpu-kernels" 2>/dev/null \
  || cp -a "${r310}/vllm-xpu-kernels" "${build_root}/vllm-xpu-kernels"
cd "${build_root}/vllm-xpu-kernels"
git checkout --detach -q 6d92b1bfbf32767ecda8e819613eb151e70030ad
git checkout -- . && git clean -fdq
git apply "${P}/vllm-xpu-kernels-gdn-fwd-o-global-barriers-r310-20260915.patch"
git apply "${P}/vllm-xpu-kernels-gdn-single-checkpoint-r311-20260917.patch"
cd "${build_root}"
cp -a "${r310}/compile" "${build_root}/compile"
t0=$(date +%s)
docker run --rm --network none --memory "${BUILD_MEMORY:-10g}" --memory-swap "${BUILD_MEMORY_SWAP:-20g}" --entrypoint /bin/bash \
  --volume /opt/intel/oneapi:/opt/intel/oneapi:ro --volume "${build_root}/vllm-xpu-kernels:/src:ro" --volume "${build_root}/compile:/run" \
  --volume "${r310}/onednn:/deps/onednn:ro" --volume "${r310}/sycl-tla:/deps/cutlass:ro" --volume "${lab}:/lab:ro" \
  --env KERNELS_DIR=/src --env VENV_DIR=/opt/venv --env ONEAPI_VARS=/opt/intel/oneapi/compiler/2026.1/env/vars.sh \
  --env BUILD_DIR=/run/build --env INSTALL_PREFIX=/run/install --env FETCHCONTENT_DIR=/run/fetchcontent \
  --env ONEDNN_SOURCE=/deps/onednn --env CUTLASS_SOURCE=/deps/cutlass --env AOT_DEVICES=bmg-g21-a0 --env JOBS="${JOBS:-8}" \
  --env GDN_KERNELS=ON --env MOE_KERNELS=OFF "${base}" /lab/scripts/build-vllm-xpu-kernels-xpu-c-only.sh
echo "kernel build took $(( $(date +%s) - t0 )) s"
out=${build_root}/compile/install/vllm_xpu_kernels
readelf -d "${out}/_xpu_C.abi3.so" | grep -Fq 'Library runpath: [$ORIGIN]' || { echo "non-portable RUNPATH on _xpu_C" >&2; exit 1; }
sha256sum "${out}/_xpu_C.abi3.so" "${out}/libgdn_attn_kernels_xe_2.so"
