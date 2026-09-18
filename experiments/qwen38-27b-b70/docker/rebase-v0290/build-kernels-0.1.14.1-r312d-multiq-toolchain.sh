#!/usr/bin/env bash
# R312d (2026-09-18): rebuild ONLY libattn_multiq_kernels_xe_2.so from the r312 source tree with the
# upstream wheel's toolchain, to close the 1e-6 rounding gap the r312c census showed against the
# untouched upstream single-row attention kernel (DPC++ 2026.0.0 upstream vs 2026.1.1 in r312c).
#   VARIANT=a  builder image r312d-a: DPC++ 2026.0.0, base image's ocloc 26.27 / IGC 2.38.2
#   VARIANT=b  builder image r312d-b: DPC++ 2026.0.0 + ocloc 26.18.38308.1 / IGC 2.34.4 (upstream profile)
# The compile tree is fresh (no RESUME): only the 16 multiq objects are built. CPU-only; safe beside a
# GPU job with BUILD_MEMORY small and JOBS=1.
set -euo pipefail
lab=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../../.." && pwd)
r310=${R310_ROOT:-/mnt/fast-ai/build/kernels-r310-gdn-barriers-20260915}
source_tree=${SOURCE_TREE:?set SOURCE_TREE to the r312 vllm-xpu-kernels checkout}
build_root=${BUILD_ROOT:?set BUILD_ROOT}
variant=${VARIANT:?set VARIANT to a or b}
builder=neural-download/vllm-xpu-kernels-builder:r312d-${variant}
mkdir -p "${build_root}/${variant}"
if [[ ! -d "${build_root}/vllm-xpu-kernels" ]]; then
  cp -a "${source_tree}" "${build_root}/vllm-xpu-kernels"
  git -C "${build_root}/vllm-xpu-kernels" rev-parse HEAD > "${build_root}/source-commit.txt"
fi
t0=$(date +%s)
docker run --rm --network none --memory "${BUILD_MEMORY:-6g}" --memory-swap "${BUILD_MEMORY_SWAP:-12g}" --entrypoint /bin/bash \
  --volume "${build_root}/vllm-xpu-kernels:/src:ro" --volume "${build_root}/${variant}:/run" \
  --volume "${r310}/onednn:/deps/onednn:ro" --volume "${r310}/sycl-tla:/deps/cutlass:ro" --volume "${lab}:/lab:ro" \
  --env KERNELS_DIR=/src --env VENV_DIR=/opt/venv --env ONEAPI_VARS=/opt/oneapi-2026.0/compiler/2026.0/env/vars.sh \
  --env BUILD_DIR=/run/build --env INSTALL_PREFIX=/run/install --env FETCHCONTENT_DIR=/run/fetchcontent \
  --env ONEDNN_SOURCE=/deps/onednn --env CUTLASS_SOURCE=/deps/cutlass --env AOT_DEVICES=bmg-g21-a0 --env JOBS="${JOBS:-1}" \
  "${builder}" /lab/scripts/build-vllm-xpu-kernels-multiq-only.sh
echo "multiq build (${variant}) took $(( $(date +%s) - t0 )) s"
out=${build_root}/${variant}/install/vllm_xpu_kernels/libattn_multiq_kernels_xe_2.so
[[ -f "${out}" ]] || { echo "multiq device library missing" >&2; exit 1; }
readelf -p .comment "${out}" | grep -i "dpc++"
sha256sum "${out}"
