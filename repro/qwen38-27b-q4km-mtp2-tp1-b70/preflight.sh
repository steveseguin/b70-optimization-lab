#!/usr/bin/env bash
set -euo pipefail
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
build_dir=${BUILD_DIR:?set BUILD_DIR to the patched llama.cpp build directory}
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
"${script_dir}/verify-models.sh"
printf 'PREFLIGHT PASS: target, draft, runtime paths, and host memory boundary verified\n'
