#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPRO_DIR="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(git -C "${REPRO_DIR}" rev-parse --show-toplevel)"

# shellcheck source=../configs/record.env
source "${REPRO_DIR}/configs/record.env"

check_size() {
  local path="$1"
  local expected="$2"
  local label="$3"

  if [[ ! -f "${path}" ]]; then
    echo "Missing ${label}: ${path}" >&2
    return 1
  fi

  local actual
  actual="$(stat -c '%s' "${path}")"
  if [[ "${actual}" != "${expected}" ]]; then
    echo "Unexpected ${label} size for ${path}: got ${actual}, expected ${expected}" >&2
    return 1
  fi
}

DEST_DIR="$(dirname -- "${GEMMA_Q8_MODEL}")" \
FILENAME="$(basename -- "${GEMMA_Q8_MODEL}")" \
EXPECTED_BYTES="${GEMMA_Q8_EXPECTED_BYTES}" \
"${REPO_ROOT}/scripts/download-gemma4-26b-q8-gguf.sh"
check_size "${GEMMA_Q8_MODEL}" "${GEMMA_Q8_EXPECTED_BYTES}" "Q8 target"

DEST_DIR="$(dirname -- "${GEMMA_MTP_F16_MODEL}")" \
FILENAME="$(basename -- "${GEMMA_MTP_F16_MODEL}")" \
EXPECTED_BYTES="${GEMMA_MTP_F16_EXPECTED_BYTES}" \
MIN_BYTES=400000000 \
"${REPO_ROOT}/scripts/download-gemma4-26b-q8-gguf.sh"
check_size "${GEMMA_MTP_F16_MODEL}" "${GEMMA_MTP_F16_EXPECTED_BYTES}" "F16 MTP draft"

if [[ -f "${GEMMA_MTP_Q40_MODEL}" ]]; then
  check_size "${GEMMA_MTP_Q40_MODEL}" "${GEMMA_MTP_Q40_EXPECTED_BYTES}" "Q4_0 MTP draft"
  echo "Q4_0 MTP draft already exists: ${GEMMA_MTP_Q40_MODEL}"
  exit 0
fi

LLAMA_QUANTIZE="${LLAMA_QUANTIZE:-${LLAMA_CPP_BUILD_DIR}/bin/llama-quantize}"
if [[ ! -x "${LLAMA_QUANTIZE}" ]]; then
  echo "Missing llama-quantize: ${LLAMA_QUANTIZE}" >&2
  echo "Run scripts/00-build-llama-cpp-record-stack.sh first, or set LLAMA_QUANTIZE." >&2
  exit 1
fi

mkdir -p "$(dirname -- "${GEMMA_MTP_Q40_MODEL}")"
"${LLAMA_QUANTIZE}" "${GEMMA_MTP_F16_MODEL}" "${GEMMA_MTP_Q40_MODEL}" Q4_0
check_size "${GEMMA_MTP_Q40_MODEL}" "${GEMMA_MTP_Q40_EXPECTED_BYTES}" "Q4_0 MTP draft"

echo "Prepared ${GEMMA_Q8_MODEL}"
echo "Prepared ${GEMMA_MTP_Q40_MODEL}"
