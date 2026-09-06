#!/usr/bin/env bash
set -eo pipefail

KERNELS_DIR="${KERNELS_DIR:?set KERNELS_DIR to the vllm-xpu-kernels checkout}"
VENV_DIR="${VENV_DIR:?set VENV_DIR to the build virtualenv}"
ONEAPI_VARS="${ONEAPI_VARS:-/opt/intel/oneapi/compiler/2025.3/env/vars.sh}"
BUILD_DIR="${BUILD_DIR:-${KERNELS_DIR}/build/xpu-c-only-2025}"
INSTALL_PREFIX="${INSTALL_PREFIX:-/tmp/vllm-xpu-xpu-c-only-2025}"
FETCHCONTENT_DIR="${FETCHCONTENT_DIR:-${KERNELS_DIR}/.deps}"
ONEDNN_SOURCE="${ONEDNN_SOURCE:-}"
CUTLASS_SOURCE="${CUTLASS_SOURCE:-}"
AOT_DEVICES="${AOT_DEVICES:-bmg-g21-a0}"
JOBS="${JOBS:-4}"
GDN_KERNELS="${GDN_KERNELS:-ON}"
MOE_KERNELS="${MOE_KERNELS:-ON}"

cd "${KERNELS_DIR}"

source "${ONEAPI_VARS}" >/tmp/oneapi-xpu-c-only-build.log 2>&1
source "${VENV_DIR}/bin/activate"

export VLLM_XPU_AOT_DEVICES="${AOT_DEVICES}"
export VLLM_XPU_XE2_AOT_DEVICES="${AOT_DEVICES}"
if [[ -n "${CUTLASS_SOURCE}" ]]; then
  export VLLM_CUTLASS_SRC_DIR="${CUTLASS_SOURCE}"
fi

dependency_args=()
if [[ -n "${ONEDNN_SOURCE}" ]]; then
  dependency_args+=("-DFETCHCONTENT_SOURCE_DIR_ONEDNN=${ONEDNN_SOURCE}")
fi

if [[ "${CLEAN:-0}" == "1" ]]; then
  rm -rf "${BUILD_DIR}" "${INSTALL_PREFIX}"
fi

python_path="$(
  python3 - <<'PY'
import sys
print(':'.join(sys.path))
PY
)"

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
  -DMOE_KERNELS_ENABLED="${MOE_KERNELS}" \
  -DGDN_KERNELS_ENABLED="${GDN_KERNELS}" \
  -DMQA_LOGITS_KERNELS_ENABLED=OFF \
  -DXPU_SPECIFIC_KERNELS_ENABLED=ON \
  -DXPUMEM_ALLOCATOR_ENABLED=OFF

cmake --build "${BUILD_DIR}" -j="${JOBS}" --target _xpu_C
cmake --install "${BUILD_DIR}" --prefix "${INSTALL_PREFIX}" --component _xpu_C
if [[ "${GDN_KERNELS}" == "ON" ]]; then
  gdn_library="${BUILD_DIR}/libgdn_attn_kernels_xe_2.so"
  if [[ ! -f "${gdn_library}" ]]; then
    printf 'GDN was enabled but its device library is missing: %s\n' \
      "${gdn_library}" >&2
    exit 3
  fi
  install -D -m 0755 "${gdn_library}" \
    "${INSTALL_PREFIX}/vllm_xpu_kernels/libgdn_attn_kernels_xe_2.so"
fi

find "${INSTALL_PREFIX}" -maxdepth 3 -type f \
  \( -name '_xpu_C*.so' -o -name 'libgdn_attn_kernels_xe_2.so' \) \
  -printf '%s %p\n'
