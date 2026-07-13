#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
BUILD_DIR=${BUILD_DIR:-"${ROOT}/build"}
XE2_DEVICE_TARGET=${XE2_DEVICE_TARGET:-bmg-g31}
MODULE_BUILD_ID=${MODULE_BUILD_ID:-q6-production-transplant-v1}

if [[ -r /opt/intel/oneapi/setvars.sh ]]; then
    # shellcheck disable=SC1091
    source /opt/intel/oneapi/setvars.sh --force >/dev/null 2>&1
fi

cmake -S "${ROOT}" -B "${BUILD_DIR}" -G Ninja \
    -DCMAKE_CXX_COMPILER=icpx \
    -DCMAKE_BUILD_TYPE=Release \
    -DQ27_XE2_DEVICE="${XE2_DEVICE_TARGET}" \
    -DQ27_XE2_BUILD_ID="${MODULE_BUILD_ID}"
cmake --build "${BUILD_DIR}" --target q27_xe2_module q27_xe2_loader

exec "${BUILD_DIR}/q27_xe2_loader" "${BUILD_DIR}/libq27_xe2_module.so"
