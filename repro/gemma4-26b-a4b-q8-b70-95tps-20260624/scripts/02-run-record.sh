#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPRO_DIR="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(git -C "${REPRO_DIR}" rev-parse --show-toplevel)"

# shellcheck source=../configs/record.env
source "${REPRO_DIR}/configs/record.env"

LLAMA_SERVER_BIN="${LLAMA_SERVER:-${LLAMA_CPP_BUILD_DIR}/bin/llama-server}"
if [[ ! -x "${LLAMA_SERVER_BIN}" ]]; then
  echo "Missing llama-server: ${LLAMA_SERVER_BIN}" >&2
  echo "Run scripts/00-build-llama-cpp-record-stack.sh first, or set LLAMA_SERVER." >&2
  exit 1
fi

if [[ ! -f "${GEMMA_Q8_MODEL}" ]]; then
  echo "Missing Q8 target model: ${GEMMA_Q8_MODEL}" >&2
  echo "Run scripts/01-prepare-models.sh first." >&2
  exit 1
fi

if [[ ! -f "${GEMMA_MTP_Q40_MODEL}" ]]; then
  echo "Missing Q4_0 MTP draft model: ${GEMMA_MTP_Q40_MODEL}" >&2
  echo "Run scripts/01-prepare-models.sh first." >&2
  exit 1
fi

RUN_STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_LABEL="${RUN_LABEL:-gemma4-q8-gpu${GPU_INDEX}-mtp-n7-draftq40-repro-${RUN_STAMP}}"

cd "${REPO_ROOT}"

export MODEL_PATH="${GEMMA_Q8_MODEL}"
export LLAMA_SERVER="${LLAMA_SERVER_BIN}"
export MTP_DRAFT_MODEL="${GEMMA_MTP_Q40_MODEL}"

exec env \
  MODEL_PATH="${GEMMA_Q8_MODEL}" \
  LLAMA_SERVER="${LLAMA_SERVER_BIN}" \
  MTP_DRAFT_MODEL="${GEMMA_MTP_Q40_MODEL}" \
  ONEAPI_DEVICE_SELECTOR="${ONEAPI_DEVICE_SELECTOR}" \
  GGML_SYCL_ENABLE_VMM="${GGML_SYCL_ENABLE_VMM}" \
  GGML_SYCL_DISABLE_OPT="${GGML_SYCL_DISABLE_OPT}" \
  MTP_DRAFT_PROFILE="${MTP_DRAFT_PROFILE}" \
  LLAMA_MTP_DRAFT_PROFILE="${MTP_DRAFT_PROFILE}" \
  MTP_DRAFT_FAST_ARGMAX="${MTP_DRAFT_FAST_ARGMAX}" \
  MTP_BACKEND_SAMPLING="${MTP_BACKEND_SAMPLING}" \
  MTP_N_MAX="${MTP_N_MAX}" \
  MTP_N_MIN="${MTP_N_MIN}" \
  MTP_P_MIN="${MTP_P_MIN}" \
  MTP_DRAFT_DEVICE="${MTP_DRAFT_DEVICE}" \
  MTP_DRAFT_THREADS="${MTP_DRAFT_THREADS}" \
  MTP_DRAFT_THREADS_BATCH="${MTP_DRAFT_THREADS_BATCH}" \
  MTP_EXTRA_ARGS="${MTP_EXTRA_ARGS}" \
  GPU_INDEX="${GPU_INDEX}" \
  PORT="${PORT}" \
  CTX_SIZE="${CTX_SIZE}" \
  BATCH_SIZE="${BATCH_SIZE}" \
  UBATCH_SIZE="${UBATCH_SIZE}" \
  POLL="${POLL}" \
  THREADS="${THREADS}" \
  FLASH_ATTN="${FLASH_ATTN}" \
  CANARY_REPEATS="${CANARY_REPEATS}" \
  BENCH_REPEATS="${BENCH_REPEATS}" \
  PROMPT_TOKENS="${PROMPT_TOKENS}" \
  MAX_TOKENS="${MAX_TOKENS}" \
  BENCH_PROMPT_MODE="${BENCH_PROMPT_MODE}" \
  scripts/run-gemma4-26b-mtp-candidate.sh "${RUN_LABEL}"
