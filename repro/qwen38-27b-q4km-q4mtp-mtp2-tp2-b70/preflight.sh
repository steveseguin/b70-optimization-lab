#!/usr/bin/env bash
set -euo pipefail
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
build_dir=${BUILD_DIR:?set BUILD_DIR to the patched llama.cpp build directory}
allow_rebuilt=${ALLOW_REBUILT_BINARIES:-0}
fail() { printf 'PREFLIGHT FAIL: %s\n' "$*" >&2; exit 1; }
[[ "$(uname -m)" == x86_64 ]] || fail 'tested only on x86_64 Linux'
[[ -x "${build_dir}/bin/llama-server" ]] || fail "missing ${build_dir}/bin/llama-server"
[[ -f "${build_dir}/bin/libggml-sycl.so" ]] || fail "missing ${build_dir}/bin/libggml-sycl.so"
[[ -r /opt/intel/oneapi/setvars.sh ]] || fail 'Intel oneAPI setvars.sh is missing'
pgrep -x llama-server >/dev/null && fail 'another llama-server is running'
mem_kib=$(awk '/^MemTotal:/ {print $2}' /proc/meminfo)
swap_kib=$(awk '/^SwapTotal:/ {print $2}' /proc/meminfo)
(( mem_kib >= 15 * 1024 * 1024 )) || fail 'at least 15 GiB physical host RAM is required by the tested boundary'
(( mem_kib + swap_kib >= 24 * 1024 * 1024 )) || fail 'at least 24 GiB combined RAM plus swap is required'
"${script_dir}/../qwen38-27b-q4km-mtp2-tp1-b70/verify-models.sh"
server_sha=$(sha256sum "${build_dir}/bin/llama-server" | awk '{print $1}')
backend_sha=$(sha256sum "${build_dir}/bin/libggml-sycl.so" | awk '{print $1}')
if [[ "${allow_rebuilt}" != 1 ]]; then
  [[ "${server_sha}" == 35f2d2327f05f42feb40f1a015ff46791e7277771ed97653f085be05a6f2c545 ]] || \
    fail 'llama-server differs from the measured binary; set ALLOW_REBUILT_BINARIES=1 only for a new validation'
  [[ "${backend_sha}" == 0e7789313ac5776b197da813d482f78e2f396620cc745af0f9c1bb2ec39bd154 ]] || \
    fail 'libggml-sycl.so differs from the measured backend; set ALLOW_REBUILT_BINARIES=1 only for a new validation'
fi
set +u
# shellcheck disable=SC1091
source /opt/intel/oneapi/setvars.sh --force >/dev/null 2>&1
set -u
device_count=$(ONEAPI_DEVICE_SELECTOR=level_zero:1,0 sycl-ls 2>/dev/null | grep -c '\[level_zero:gpu\]')
(( device_count >= 2 )) || fail 'the measured selector did not enumerate two Level Zero GPUs'
printf 'PREFLIGHT PASS: two GPUs, target, draft, runtime, and host-memory boundary verified\n'
