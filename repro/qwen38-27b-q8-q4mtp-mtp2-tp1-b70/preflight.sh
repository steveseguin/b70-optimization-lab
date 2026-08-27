#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
target_dir=${TARGET_DIR:?set TARGET_DIR}
draft_dir=${DRAFT_DIR:?set DRAFT_DIR}
build_dir=${BUILD_DIR:?set BUILD_DIR}
server=${build_dir}/bin/llama-server
backend=${build_dir}/bin/libggml-sycl.so

[[ -f "${target_dir}/Qwen3.8-27B-Q8_0.gguf" ]] || { printf 'Missing Q8 target.\n' >&2; exit 1; }
[[ -f "${draft_dir}/mtp-Qwen3.8-27B-Q4_0.gguf" ]] || { printf 'Missing Q4 MTP draft.\n' >&2; exit 1; }
[[ -x "${server}" && -f "${backend}" ]] || { printf 'Missing built runtime.\n' >&2; exit 1; }
[[ "$(sha256sum "${server}" | awk '{print $1}')" == 35f2d2327f05f42feb40f1a015ff46791e7277771ed97653f085be05a6f2c545 ]] || { printf 'llama-server hash mismatch.\n' >&2; exit 1; }
[[ "$(sha256sum "${backend}" | awk '{print $1}')" == 0e7789313ac5776b197da813d482f78e2f396620cc745af0f9c1bb2ec39bd154 ]] || { printf 'SYCL backend hash mismatch.\n' >&2; exit 1; }
TARGET_DIR="${target_dir}" DRAFT_DIR="${draft_dir}" "${script_dir}/verify-models.sh"
printf 'PREFLIGHT PASS: target, draft, and measured runtime identities verified\n'
