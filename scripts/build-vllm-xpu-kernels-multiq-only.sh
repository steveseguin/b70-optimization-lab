#!/usr/bin/env bash
# Build ONLY the r312 multi-position verifier device library (libattn_multiq_kernels_xe_2.so) from a
# vllm-xpu-kernels checkout, with whatever DPC++ toolchain ONEAPI_VARS points at. Same cmake
# configuration as build-vllm-xpu-kernels-xpu-c-only.sh; nothing else is compiled or installed.
# Purpose (2026-09-18): the upstream attention library in the R310/R311 images was compiled with
# DPC++ 2026.0.0 and the r312c multiq library with 2026.1.1, and the two round differently at the
# 1e-6 level. This lets the multiq library be rebuilt with the upstream toolchain alone.
set -eo pipefail

KERNELS_DIR="${KERNELS_DIR:?set KERNELS_DIR to the vllm-xpu-kernels checkout}"
VENV_DIR="${VENV_DIR:?set VENV_DIR to the build virtualenv}"
ONEAPI_VARS="${ONEAPI_VARS:?set ONEAPI_VARS to the compiler env script}"
BUILD_DIR="${BUILD_DIR:?set BUILD_DIR}"
INSTALL_PREFIX="${INSTALL_PREFIX:?set INSTALL_PREFIX}"
FETCHCONTENT_DIR="${FETCHCONTENT_DIR:-${KERNELS_DIR}/.deps}"
ONEDNN_SOURCE="${ONEDNN_SOURCE:-}"
CUTLASS_SOURCE="${CUTLASS_SOURCE:-}"
AOT_DEVICES="${AOT_DEVICES:-bmg-g21-a0}"
JOBS="${JOBS:-2}"

cd "${KERNELS_DIR}"
source "${ONEAPI_VARS}" >/tmp/oneapi-multiq-only-build.log 2>&1
source "${VENV_DIR}/bin/activate"
icpx --version | head -1
ocloc --version 2>/dev/null | head -1 || true

export VLLM_XPU_AOT_DEVICES="${AOT_DEVICES}"
export VLLM_XPU_XE2_AOT_DEVICES="${AOT_DEVICES}"
[[ -n "${CUTLASS_SOURCE}" ]] && export VLLM_CUTLASS_SRC_DIR="${CUTLASS_SOURCE}"
dependency_args=()
[[ -n "${ONEDNN_SOURCE}" ]] && dependency_args+=("-DFETCHCONTENT_SOURCE_DIR_ONEDNN=${ONEDNN_SOURCE}")

python_path="$(python3 -c 'import sys; print(":".join(sys.path))')"

cmake -S . -B "${BUILD_DIR}" -G Ninja \
  -DCMAKE_BUILD_TYPE=Release \
  -DVLLM_TARGET_DEVICE=xpu \
  -DCMAKE_TOOLCHAIN_FILE=cmake/toolchain.cmake \
  -DVLLM_PYTHON_EXECUTABLE="$(which python3)" \
  -DVLLM_PYTHON_PATH="${python_path}" \
  -DFETCHCONTENT_BASE_DIR="${FETCHCONTENT_DIR}" \
  "${dependency_args[@]}" \
  -DBUILD_SYCL_TLA_KERNELS=ON \
  -DVLLM_XPU_ENABLE_XE2=ON \
  -DVLLM_XPU_ENABLE_XE_DEFAULT=OFF \
  -DBASIC_KERNELS_ENABLED=OFF \
  -DFA2_KERNELS_ENABLED=OFF \
  -DMOE_KERNELS_ENABLED=OFF \
  -DGDN_KERNELS_ENABLED=ON \
  -DMQA_LOGITS_KERNELS_ENABLED=OFF \
  -DXPU_SPECIFIC_KERNELS_ENABLED=ON \
  -DXPUMEM_ALLOCATOR_ENABLED=OFF \
  -DVLLM_MULTIQ_DECODE_CONFIG="${MULTIQ_DECODE_CONFIG:-paged_decode_qwen38.conf}"

cmake --build "${BUILD_DIR}" -j"${JOBS}" --target attn_multiq_kernels_xe_2
lib="${BUILD_DIR}/libattn_multiq_kernels_xe_2.so"
[[ -f "${lib}" ]] || { echo "multiq device library missing: ${lib}" >&2; exit 3; }
install -D -m 0755 "${lib}" "${INSTALL_PREFIX}/vllm_xpu_kernels/libattn_multiq_kernels_xe_2.so"
readelf -p .comment "${lib}" | grep -i "dpc++" || true
sha256sum "${INSTALL_PREFIX}/vllm_xpu_kernels/libattn_multiq_kernels_xe_2.so"
