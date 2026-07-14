#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
BUILD_DIR=${BUILD_DIR:-"${ROOT}/build"}
XE2_DEVICE_TARGET=${XE2_DEVICE_TARGET:-bmg-g31}
MODULE_BUILD_ID=${MODULE_BUILD_ID:-q5k-gdn-out-m6-v1}
MODEL=${MODEL:-/dev/shm/qwen27-b70-model-cache/20c9c45d4d25b492b82117960b5f715ef9daff75e4e14c4fb878fa3793fb379a/Qwen3.6-27B-Q4_0.gguf}
FIXTURE_DIR=${FIXTURE_DIR:-/mnt/fast-ai/bench-results/qwen27-q5k-gdn-out-m6/capture-v1}
PACK_CACHE=${PACK_CACHE:-/mnt/fast-ai/bench-results/qwen27-q5k-gdn-out-m6/blk0-real-q5k-dpas-v1.pack}
ITERS=${ITERS:-100}

: "${ZE_AFFINITY_MASK:?Set ZE_AFFINITY_MASK to an idle B70 index}"
export ONEAPI_DEVICE_SELECTOR=${ONEAPI_DEVICE_SELECTOR:-level_zero:*}

if [[ -r /opt/intel/oneapi/setvars.sh ]]; then
    # shellcheck disable=SC1091
    source /opt/intel/oneapi/setvars.sh --force >/dev/null 2>&1
fi

cmake -S "${ROOT}" -B "${BUILD_DIR}" -G Ninja \
    -DCMAKE_CXX_COMPILER=icpx \
    -DCMAKE_BUILD_TYPE=Release \
    -DQ27_XE2_DEVICE="${XE2_DEVICE_TARGET}" \
    -DQ27_XE2_BUILD_ID="${MODULE_BUILD_ID}"
cmake --build "${BUILD_DIR}" --target q27_xe2_module q27_q5k_gdn_out_module_compare

exec "${BUILD_DIR}/q27_q5k_gdn_out_module_compare" \
    "${BUILD_DIR}/libq27_xe2_module.so" "${MODEL}" \
    "${FIXTURE_DIR}/input.f32" "${FIXTURE_DIR}/projection.f32" \
    "${PACK_CACHE}" "${ITERS}"
