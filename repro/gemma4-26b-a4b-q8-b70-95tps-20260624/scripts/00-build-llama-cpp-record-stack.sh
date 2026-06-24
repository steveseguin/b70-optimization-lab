#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPRO_DIR="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(git -C "${REPRO_DIR}" rev-parse --show-toplevel)"

# shellcheck source=../configs/record.env
source "${REPRO_DIR}/configs/record.env"

PATCH_FILE="${REPRO_DIR}/patches/llama-cpp-gemma-record-stack-c926ad098-20260624.patch"

if [[ ! -d "${LLAMA_CPP_DIR}/.git" ]]; then
  mkdir -p "$(dirname -- "${LLAMA_CPP_DIR}")"
  git clone https://github.com/ggml-org/llama.cpp.git "${LLAMA_CPP_DIR}"
fi

cd "${LLAMA_CPP_DIR}"
git fetch --tags origin

if ! git diff --quiet || ! git diff --cached --quiet; then
  current_commit="$(git rev-parse HEAD)"
  if [[ "${current_commit}" == "${LLAMA_CPP_COMMIT}" ]] && git apply --reverse --check "${PATCH_FILE}" >/dev/null 2>&1; then
    echo "Record patch is already applied."
  else
    echo "llama.cpp worktree has local changes: ${LLAMA_CPP_DIR}" >&2
    echo "Use a clean worktree or set LLAMA_CPP_DIR to a fresh path." >&2
    exit 1
  fi
elif git checkout --detach "${LLAMA_CPP_COMMIT}" && git apply --reverse --check "${PATCH_FILE}" >/dev/null 2>&1; then
  echo "Record patch is already applied."
else
  git apply --check "${PATCH_FILE}"
  git apply "${PATCH_FILE}"
fi

if [[ -f /opt/intel/oneapi/setvars.sh ]]; then
  # shellcheck disable=SC1091
  source /opt/intel/oneapi/setvars.sh >/dev/null
fi

cmake -S . -B "${LLAMA_CPP_BUILD_DIR}" \
  -G Ninja \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_C_COMPILER=icx \
  -DCMAKE_CXX_COMPILER=icpx \
  -DGGML_SYCL=ON \
  -DGGML_SYCL_F16=ON \
  -DGGML_SYCL_DEVICE_ARCH="${LLAMA_SYCL_DEVICE_ARCH}"

cmake --build "${LLAMA_CPP_BUILD_DIR}" --target llama-server llama-cli llama-bench llama-quantize -j"$(nproc)"

echo "Built ${LLAMA_CPP_BUILD_DIR}/bin/llama-server"
echo "Repo root for benchmark scripts: ${REPO_ROOT}"
