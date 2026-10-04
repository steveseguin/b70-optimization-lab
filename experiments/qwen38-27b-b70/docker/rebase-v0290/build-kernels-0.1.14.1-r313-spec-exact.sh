#!/usr/bin/env bash
# R313 kernel library (2026-10-04): the R310 build (vllm-xpu-kernels 6d92b1b + r310, oneDNN r137a+r137b+r221+r309)
# plus vllm-xpu-kernels patch r313 (vllm-xpu-kernels-gdn-spec-decode-exact-r313-20261004.patch): the speculative
# gated-delta-rule kernel carries the SSM state from one verify row to the next through the slot's StateT (float16)
# rounding, as the one-token decode kernel does, so every verify row and every stored prefix state equals
# token-by-token decode. Only csrc/xpu/gdn_attn/gated_delta_rule.hpp changes; it is compiled into _xpu_C through
# gdn_attn_interface.cpp. libgdn_attn_kernels_xe_2.so (the chunked prefill kernels) is not touched.
#
# Same builder image, host oneAPI 2026.1.1, oneDNN and sycl-tla trees as R310 (reused read-only from the R310 build
# root). The R310 source tree and compile tree are copied with cp -a (mtimes kept), so ninja recompiles only
# gdn_attn_interface.cpp.o and relinks _xpu_C (R311b did the same kind of rebuild in about 1 minute). A preflight
# refuses to start if anything other than gated_delta_rule.hpp is newer than the R310 objects, because a full rebuild
# at JOBS=8 was OOM-killed once (R311, chunk_gated_delta_rule_xe2.cpp).
#
# CPU only. 15 GiB host: run it with no model server and no other build or MiniMax job running.
#   BUILD_ROOT=/mnt/fast-ai/build/kernels-r313-spec-exact-20261004 \
#     bash experiments/qwen38-27b-b70/docker/rebase-v0290/build-kernels-0.1.14.1-r313-spec-exact.sh
# Then build the image with the command at the top of Dockerfile.r313-spec-exact.
set -euo pipefail
lab=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../../.." && pwd)
r310=${R310_ROOT:-/mnt/fast-ai/build/kernels-r310-gdn-barriers-20260915}
build_root=${BUILD_ROOT:?set BUILD_ROOT to a new empty directory}
# RESUME=1 reruns the compile in an existing build root (ninja rebuilds only what failed, e.g. after an OOM kill).
resume=${RESUME:-0}
[[ "${resume}" == 1 || ! -e "${build_root}" ]] || { echo "BUILD_ROOT exists: ${build_root}" >&2; exit 1; }
base=${BASE_IMAGE:-vllm/vllm-openai-xpu@sha256:96db42e248d48760a4937eb3d04c4878b39d13a9814efea95d510393e097a901}
P=${lab}/experiments/qwen38-27b-b70/patches
r310_xpu_c_sha=043083fc64cd6f4e779004dc05515d4bfbdefa9e5febaf7ec057199558859057
r310_gdn_sha=5b00b4d44f51169d0e610ae682aa90d7120ad6ac6a389c9d898c4d9141abec4a
src=${build_root}/vllm-xpu-kernels
if [[ "${resume}" != 1 ]]; then
  # The R310 build root must be the one the R310 image was made from.
  echo "${r310_xpu_c_sha}  ${r310}/compile/install/vllm_xpu_kernels/_xpu_C.abi3.so" | sha256sum -c -
  mkdir -p "${build_root}"
  cp -a "${r310}/vllm-xpu-kernels" "${src}"
  [[ "$(git -C "${src}" rev-parse HEAD)" == 6d92b1bfbf32767ecda8e819613eb151e70030ad ]] || { echo "unexpected kernels commit" >&2; exit 1; }
  git -C "${src}" apply --reverse --check "${P}/vllm-xpu-kernels-gdn-fwd-o-global-barriers-r310-20260915.patch"
  [[ "$(git -C "${src}" status --porcelain)" == " M csrc/xpu/gdn_attn/xe_2/chunk_gated_delta_rule_kernels_xe2.hpp" ]] \
    || { echo "R310 source tree is not exactly 6d92b1b + r310" >&2; git -C "${src}" status --porcelain >&2; exit 1; }
  cp -a "${r310}/compile" "${build_root}/compile"
  rm -rf "${build_root}/compile/install"
  git -C "${src}" apply "${P}/vllm-xpu-kernels-gdn-spec-decode-exact-r313-20261004.patch"
  git -C "${src}" diff --stat
  newer=$(cd "${src}" && find . -path ./.git -prune -o -type f -newer "${build_root}/compile/build/.ninja_log" -print)
  [[ "${newer}" == "./csrc/xpu/gdn_attn/gated_delta_rule.hpp" ]] \
    || { echo "sources newer than the R310 objects (would trigger a bigger rebuild):" >&2; echo "${newer}" >&2; exit 1; }
fi
cd "${build_root}"
touch "${build_root}/build-start.stamp"
t0=$(date +%s)
docker run --rm --network none --memory "${BUILD_MEMORY:-10g}" --memory-swap "${BUILD_MEMORY_SWAP:-20g}" --entrypoint /bin/bash \
  --volume /opt/intel/oneapi:/opt/intel/oneapi:ro --volume "${src}:/src:ro" --volume "${build_root}/compile:/run" \
  --volume "${r310}/onednn:/deps/onednn:ro" --volume "${r310}/sycl-tla:/deps/cutlass:ro" --volume "${lab}:/lab:ro" \
  --env KERNELS_DIR=/src --env VENV_DIR=/opt/venv --env ONEAPI_VARS=/opt/intel/oneapi/compiler/2026.1/env/vars.sh \
  --env BUILD_DIR=/run/build --env INSTALL_PREFIX=/run/install --env FETCHCONTENT_DIR=/run/fetchcontent \
  --env ONEDNN_SOURCE=/deps/onednn --env CUTLASS_SOURCE=/deps/cutlass --env AOT_DEVICES=bmg-g21-a0 --env JOBS="${JOBS:-2}" \
  --env GDN_KERNELS=ON --env MOE_KERNELS=OFF "${base}" /lab/scripts/build-vllm-xpu-kernels-xpu-c-only.sh
echo "kernel build took $(( $(date +%s) - t0 )) s"
echo "objects recompiled by this build:"
find "${build_root}/compile/build" -name '*.o' -newer "${build_root}/build-start.stamp" -printf '  %P\n'
out=${build_root}/compile/install/vllm_xpu_kernels
readelf -d "${out}/_xpu_C.abi3.so" | grep -Fq 'Library runpath: [$ORIGIN]' || { echo "non-portable RUNPATH on _xpu_C" >&2; exit 1; }
sha256sum "${out}/_xpu_C.abi3.so" "${out}/libgdn_attn_kernels_xe_2.so"
[[ "$(sha256sum < "${out}/_xpu_C.abi3.so" | cut -d' ' -f1)" != "${r310_xpu_c_sha}" ]] || { echo "_xpu_C unchanged: patch not compiled in" >&2; exit 1; }
if [[ "$(sha256sum < "${out}/libgdn_attn_kernels_xe_2.so" | cut -d' ' -f1)" != "${r310_gdn_sha}" ]]; then
  echo "note: libgdn_attn_kernels_xe_2.so was relinked and differs from R310's; the R313 image keeps R310's copy" >&2
fi
# Build context for Dockerfile.r313-spec-exact: only the new _xpu_C.
mkdir -p "${build_root}/image"
cp "${out}/_xpu_C.abi3.so" "${build_root}/image/"
sha256sum "${build_root}/image/_xpu_C.abi3.so" | tee "${build_root}/image/_xpu_C.abi3.so.sha256"
echo "next: docker build --network none -f ${lab}/experiments/qwen38-27b-b70/docker/rebase-v0290/Dockerfile.r313-spec-exact \\"
echo "        -t neural-download/vllm-openai-xpu:qwen38-fp8-v0290-r313-spec-exact ${build_root}/image"
