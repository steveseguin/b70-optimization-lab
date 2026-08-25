#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
model_dir="${MODEL_DIR:-}"
build_dir="${BUILD_DIR:-}"
fail() { printf 'PREFLIGHT FAIL: %s\n' "$*" >&2; exit 1; }

[[ "$(uname -m)" == x86_64 ]] || fail 'this candidate was tested only on x86_64'
[[ -r /etc/os-release ]] || fail 'cannot identify host OS'
# shellcheck disable=SC1091
source /etc/os-release
[[ "${ID:-}" == ubuntu && "${VERSION_ID:-}" == 24.04 ]] || fail "tested host is Ubuntu 24.04; found ${PRETTY_NAME:-unknown}"
[[ -n "${model_dir}" && -n "${build_dir}" ]] || fail 'set MODEL_DIR and BUILD_DIR'
[[ -x "${build_dir}/bin/llama-server" && -x "${build_dir}/bin/llama-bench" ]] || fail 'llama-server or llama-bench is missing'
[[ -f "${build_dir}/bin/libggml-sycl.so" ]] || fail 'libggml-sycl.so is missing'
[[ -r /opt/intel/oneapi/setvars.sh ]] || fail 'Intel oneAPI setvars.sh is missing'
groups=" $(id -nG) "; [[ "${groups}" == *' render '* ]] || fail 'current user is not in the render group'
mapfile -t nodes < <(find /dev/dri -maxdepth 1 -type c -name 'renderD*' 2>/dev/null | LC_ALL=C sort)
(( ${#nodes[@]} >= 1 )) || fail 'one DRM render device is required'
[[ -r "${nodes[0]}" && -w "${nodes[0]}" ]] || fail "render device is not readable/writable: ${nodes[0]}"
mem_kib=$(awk '/^MemTotal:/ {print $2}' /proc/meminfo)
swap_kib=$(awk '/^SwapTotal:/ {print $2}' /proc/meminfo)
(( mem_kib >= 15 * 1024 * 1024 )) || fail 'candidate requires at least 15 GiB usable host RAM (16 GB nominal)'
(( mem_kib + swap_kib >= 30 * 1024 * 1024 )) || fail 'candidate requires at least 30 GiB combined RAM and swap'
pgrep -x llama-server >/dev/null && fail 'another llama-server is already running'
"${script_dir}/verify-model-direct.sh" "${model_dir}"
printf 'PREFLIGHT PASS: os=%s kernel=%s render=%s model and runtime present\n' "${PRETTY_NAME}" "$(uname -r)" "${nodes[0]}"
