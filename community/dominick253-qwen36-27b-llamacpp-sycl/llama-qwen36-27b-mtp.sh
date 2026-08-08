#!/usr/bin/env bash
# Maintainer-hardened launcher derived from PR #19.
# CTX_SIZE and the model hash are required because the submitted packet did not
# establish one exact current context/model artifact identity.
set -euo pipefail

GPU_INDEX="${GPU_INDEX:-0}"
PORT="${PORT:-18020}"
CTX_SIZE="${CTX_SIZE:?Set CTX_SIZE explicitly (the report contains 150K/175K identities)}"
LLAMA_ROOT="${LLAMA_ROOT:?Set LLAMA_ROOT to llama.cpp commit 15586e2d7}"
MODEL="${MODEL:?Set MODEL to Qwen3.6-27B-Q4_K_M.gguf}"
EXPECTED_MODEL_SHA256="${EXPECTED_MODEL_SHA256:?Set EXPECTED_MODEL_SHA256 for the selected GGUF}"
EXPECTED_SERVER_SHA256="${EXPECTED_SERVER_SHA256:?Set EXPECTED_SERVER_SHA256 for the selected llama-server binary}"
EXPECTED_LLAMA_COMMIT="${EXPECTED_LLAMA_COMMIT:-15586e2d7165570fb3aa7c26e0d442e289ef69de}"
ONEAPI_ROOT="${ONEAPI_ROOT:-/opt/intel/oneapi}"
HOST="${HOST:-127.0.0.1}"
DRY_RUN="${DRY_RUN:-0}"

[[ "${GPU_INDEX}" == "0" || "${GPU_INDEX}" == "1" ]] || { echo "GPU_INDEX must be 0 or 1" >&2; exit 2; }
[[ "${PORT}" =~ ^[0-9]+$ ]] && ((PORT >= 1024 && PORT <= 65535)) || { echo "Invalid PORT" >&2; exit 2; }
[[ "${CTX_SIZE}" =~ ^[0-9]+$ ]] && ((CTX_SIZE > 0)) || { echo "Invalid CTX_SIZE" >&2; exit 2; }
[[ "${EXPECTED_MODEL_SHA256}" =~ ^[0-9a-f]{64}$ ]] || { echo "EXPECTED_MODEL_SHA256 must be lowercase SHA-256" >&2; exit 2; }
[[ "${EXPECTED_SERVER_SHA256}" =~ ^[0-9a-f]{64}$ ]] || { echo "EXPECTED_SERVER_SHA256 must be lowercase SHA-256" >&2; exit 2; }
[[ "${EXPECTED_LLAMA_COMMIT}" =~ ^[0-9a-f]{40}$ ]] || { echo "EXPECTED_LLAMA_COMMIT must be a 40-character commit" >&2; exit 2; }
[[ "${HOST}" == "127.0.0.1" || "${HOST}" == "::1" ]] || { echo "Safe launcher only permits loopback HOST" >&2; exit 2; }
[[ "${DRY_RUN}" == "0" || "${DRY_RUN}" == "1" ]] || { echo "DRY_RUN must be 0 or 1" >&2; exit 2; }

server="${LLAMA_ROOT}/build-sycl/bin/llama-server"
if [[ "${DRY_RUN}" == "0" ]]; then
  [[ -x "${server}" ]] || { echo "Missing llama-server: ${server}" >&2; exit 2; }
  [[ -f "${MODEL}" ]] || { echo "Missing model: ${MODEL}" >&2; exit 2; }
  actual_model_sha256="$(sha256sum "${MODEL}" | awk '{print $1}')"
  [[ "${actual_model_sha256}" == "${EXPECTED_MODEL_SHA256}" ]] || { echo "Model SHA-256 mismatch" >&2; exit 2; }
  actual_server_sha256="$(sha256sum "${server}" | awk '{print $1}')"
  [[ "${actual_server_sha256}" == "${EXPECTED_SERVER_SHA256}" ]] || { echo "llama-server SHA-256 mismatch" >&2; exit 2; }
  actual_llama_commit="$(git -C "${LLAMA_ROOT}" rev-parse HEAD 2>/dev/null || true)"
  [[ "${actual_llama_commit}" == "${EXPECTED_LLAMA_COMMIT}" ]] || { echo "llama.cpp commit mismatch" >&2; exit 2; }
  git -C "${LLAMA_ROOT}" diff --quiet && git -C "${LLAMA_ROOT}" diff --cached --quiet || {
    echo "llama.cpp has tracked source changes; use an isolated exact tree" >&2
    exit 2
  }
  [[ -f "${ONEAPI_ROOT}/setvars.sh" ]] || { echo "Missing oneAPI setvars.sh" >&2; exit 2; }
  set +u
  source "${ONEAPI_ROOT}/setvars.sh" >/dev/null
  set -u
fi

export ONEAPI_DEVICE_SELECTOR="level_zero:${GPU_INDEX}"
export UR_L0_ENABLE_RELAXED_ALLOCATION_LIMITS=1
export GGML_SYCL_USE_LEVEL_ZERO_API=1
export GGML_SYCL_ENABLE_FLASH_ATTN=1
export GGML_SYCL_FA_ONEDNN=1
export GGML_SYCL_ENABLE_GRAPH=0

command=(
  "${server}"
  --model "${MODEL}"
  --host "${HOST}"
  --port "${PORT}"
  --ctx-size "${CTX_SIZE}"
  --n-gpu-layers 99
  --device SYCL0
  --split-mode none
  --main-gpu 0
  --parallel 1
  --batch-size 2048
  --ubatch-size 2048
  --cache-type-k f16
  --cache-type-v f16
  --cache-type-k-draft f16
  --cache-type-v-draft f16
  --flash-attn on
  --spec-type draft-mtp
  --spec-draft-n-max 2
  --spec-draft-p-min 0.0
  --temp 0.6
  --top-p 0.95
  --top-k 20
  --min-p 0.0
  --presence-penalty 0.0
  --repeat-penalty 1.0
  --fit off
)

if [[ "${DRY_RUN}" == "1" ]]; then
  printf '%q ' "${command[@]}"
  printf '\n'
  exit 0
fi

exec "${command[@]}"
