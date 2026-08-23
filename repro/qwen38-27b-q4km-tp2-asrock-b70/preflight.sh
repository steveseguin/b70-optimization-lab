#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/../.." && pwd)
source_dir="${QWEN38_SOURCE_DIR:-}"
build_dir="${QWEN38_BUILD_DIR:-}"
model_file="${QWEN38_MODEL:-}"

fail() { printf 'PREFLIGHT FAIL: %s\n' "$*" >&2; exit 1; }

[[ "$(uname -m)" == x86_64 ]] || fail "this packet was tested only on x86_64"
[[ -r /etc/os-release ]] || fail "cannot identify the host OS"
# shellcheck disable=SC1091
source /etc/os-release
[[ "${ID:-}" == ubuntu && "${VERSION_ID:-}" == 24.04 ]] || \
    fail "tested host is Ubuntu 24.04; found ${PRETTY_NAME:-unknown}"
[[ -n "${source_dir}" && -d "${source_dir}" ]] || fail "set QWEN38_SOURCE_DIR to the patched source tree"
git -C "${source_dir}" rev-parse --is-inside-work-tree >/dev/null 2>&1 || fail "source directory is not a Git worktree"
base_revision=4302fb59969a5d8cf9f8e5f55fdd4506d0ed2126
git -C "${source_dir}" cat-file -e "${base_revision}^{commit}" 2>/dev/null || fail "source tree lacks pinned base revision ${base_revision}"
git -C "${source_dir}" merge-base --is-ancestor "${base_revision}" HEAD || fail "source HEAD does not descend from the pinned base"
grep -Rqs 'GGML_SYCL_FUSED_MMVQ_QUAD_GDN' "${source_dir}/ggml" || fail "full TP2 patch marker is absent from source"
grep -Rqs 'GGML_SYCL_FUSED_MMVQ_SWIGLU_Q4K' "${source_dir}/ggml" || fail "Q4_K TP2 increment marker is absent from source"
[[ -n "${build_dir}" && -d "${build_dir}" ]] || fail "set QWEN38_BUILD_DIR to the matching build"
[[ -x "${build_dir}/bin/llama-server" ]] || fail "missing ${build_dir}/bin/llama-server"
[[ -x "${build_dir}/bin/llama-bench" ]] || fail "missing ${build_dir}/bin/llama-bench"
[[ -f "${build_dir}/bin/libggml-sycl.so" ]] || fail "missing ${build_dir}/bin/libggml-sycl.so"
[[ -n "${model_file}" && -f "${model_file}" ]] || fail "set QWEN38_MODEL to Qwen3.8-27B-Q4_K_M.gguf"
[[ "$(basename -- "${model_file}")" == Qwen3.8-27B-Q4_K_M.gguf ]] || fail "unexpected model filename"
[[ -r /opt/intel/oneapi/setvars.sh ]] || fail "Intel oneAPI setvars.sh is missing"
groups=" $(id -nG) "
[[ "${groups}" == *" render "* ]] || fail "current user is not in the render group"
mapfile -t render_nodes < <(find /dev/dri -maxdepth 1 -type c -name 'renderD*' 2>/dev/null | LC_ALL=C sort)
(( ${#render_nodes[@]} >= 2 )) || fail "two DRM render devices are required"
for node in "${render_nodes[@]:0:2}"; do
    [[ -r "${node}" && -w "${node}" ]] || fail "render device is not readable/writable: ${node}"
    sysfs_device="/sys/class/drm/$(basename -- "${node}")/device"
    [[ "$(<"${sysfs_device}/vendor")" == 0x8086 && "$(<"${sysfs_device}/device")" == 0xe223 ]] || \
        fail "render device is not an Intel Arc Pro B70: ${node}"
done
pgrep -x llama-server >/dev/null && fail "another llama-server is already running"

full_patch="${repo_root}/patches/qwen36-27b-q8-tp2-asrock-b70/llama-cpp-mndodd-4302fb599-lab-tp2-dp4a2-20260815.diff.gz.b64"
increment="${repo_root}/patches/qwen38-27b-q4km-tp2-asrock-b70/llama-cpp-q4k-mmvq-swiglu-tp2-20260815.diff.gz.b64"
full_hash=$(base64 -d "${full_patch}" | gzip -dc | sha256sum | awk '{print $1}')
increment_hash=$(base64 -d "${increment}" | gzip -dc | sha256sum | awk '{print $1}')
[[ "${full_hash}" == f21e9b557c3d024527ac98d5f189cf7ea72fa8c38a5faf2a22ee339fd1988998 ]] || \
    fail "full TP2 patch decoded hash mismatch"
[[ "${increment_hash}" == 0a27858525f6a402cf9c92d1b93daee0a80e2ffaef9137bf7bce784a549b58b6 ]] || \
    fail "Q4_K TP2 increment decoded hash mismatch"

server_hash=$(sha256sum "${build_dir}/bin/llama-server" | awk '{print $1}')
bench_hash=$(sha256sum "${build_dir}/bin/llama-bench" | awk '{print $1}')
sycl_hash=$(sha256sum "${build_dir}/bin/libggml-sycl.so" | awk '{print $1}')
if [[ "${server_hash}" != 6ae782c7e8f7a992e0eeced10ade2a84b3cbb9ba65c65cbb917e52d1ce09777d ||
      "${bench_hash}" != 95a13668005d2dff3bdc6ea2eb48f339d8f6552b824a572207127db040a5926a ||
      "${sycl_hash}" != 375f6d251b022b62367e73d2cd6b7eb0200efc9cc9c854a509af45950938c3ed ]]; then
    [[ "${QWEN38_ALLOW_REBUILT_BINARIES:-0}" == 1 ]] || \
        fail "binary hashes differ from the evidence build; set QWEN38_ALLOW_REBUILT_BINARIES=1 only for a source rebuild that will rerun the full oracle"
    printf 'PREFLIGHT NOTICE: rebuilt binaries accepted by explicit override; they are not the evidence binaries\n'
fi

MODEL_DIR=$(dirname -- "${model_file}") \
    "${repo_root}/repro/qwen38-27b-q4km-tp1-b70/verify-model-direct.sh"

printf 'host_os=%s\nkernel=%s\nrender_devices=%s,%s\nsource_dir=%s\nbuild_dir=%s\nmodel=%s\n' \
    "${PRETTY_NAME}" "$(uname -r)" "${render_nodes[0]}" "${render_nodes[1]}" \
    "${source_dir}" "${build_dir}" "${model_file}"
printf 'PREFLIGHT PASS: host, B70 access, source markers, patch artifacts, binary policy, and direct model identity passed\n'
