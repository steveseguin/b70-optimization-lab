#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
model_dir="${MODEL_DIR:-}"
build_dir="${BUILD_DIR:-}"

fail() { printf 'PREFLIGHT FAIL: %s\n' "$*" >&2; exit 1; }

[[ "$(uname -m)" == x86_64 ]] || fail "this candidate was tested only on x86_64"
[[ -r /etc/os-release ]] || fail "cannot identify the host OS"
# shellcheck disable=SC1091
source /etc/os-release
[[ "${ID:-}" == ubuntu && "${VERSION_ID:-}" == 24.04 ]] || \
    fail "tested host is Ubuntu 24.04; found ${PRETTY_NAME:-unknown}"
[[ -n "${model_dir}" ]] || fail "set MODEL_DIR to the directory containing the GGUF"
[[ -n "${build_dir}" ]] || fail "set BUILD_DIR to the patched llama.cpp build directory"
[[ -x "${build_dir}/bin/llama-server" ]] || fail "missing ${build_dir}/bin/llama-server"
[[ -f "${build_dir}/bin/libggml-sycl.so" ]] || fail "missing ${build_dir}/bin/libggml-sycl.so"
[[ -r /opt/intel/oneapi/setvars.sh ]] || fail "Intel oneAPI setvars.sh is missing"
groups=" $(id -nG) "
[[ "${groups}" == *" render "* ]] || fail "current user is not in the render group"
mapfile -t render_nodes < <(find /dev/dri -maxdepth 1 -type c -name 'renderD*' 2>/dev/null | LC_ALL=C sort)
(( ${#render_nodes[@]} >= 1 )) || fail "one DRM render device is required"
[[ -r "${render_nodes[0]}" && -w "${render_nodes[0]}" ]] || \
    fail "render device is not readable/writable: ${render_nodes[0]}"
mem_total_kib=$(awk '/^MemTotal:/ {print $2}' /proc/meminfo)
(( mem_total_kib >= 64 * 1024 * 1024 )) || \
    fail "candidate preflight conservatively requires 64 GiB host RAM"
pgrep -x llama-server >/dev/null && fail "another llama-server is already running"

"${script_dir}/verify-model-direct.sh" "${model_dir}"
printf 'host_os=%s\nkernel=%s\nrender_device=%s\nmodel_dir=%s\nbuild_dir=%s\n' \
    "${PRETTY_NAME}" "$(uname -r)" "${render_nodes[0]}" "${model_dir}" "${build_dir}"
printf 'PREFLIGHT PASS: prerequisites and direct/ordinary model identities match\n'
