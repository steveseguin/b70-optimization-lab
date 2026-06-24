#!/usr/bin/env bash
set -euo pipefail

# Thin wrapper for Gemma 4 26B A4B Q8 llama.cpp draft-MTP candidates.
# It keeps the Q8/f16 quality lane fixed and exposes only the MTP knobs that are
# useful for sweeps. The underlying harness still runs chat canaries and a
# sustained-decode benchmark, then writes data/$LABEL/summary.json.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ $# -gt 0 ]]; then
  export LABEL="$1"
fi

MTP_DRAFT_MODEL="${MTP_DRAFT_MODEL:-/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/mtp-gemma-4-26B-A4B-it.gguf}"
MTP_N_MAX="${MTP_N_MAX:-4}"
MTP_N_MIN="${MTP_N_MIN:-}"
MTP_P_MIN="${MTP_P_MIN:-}"
MTP_P_SPLIT="${MTP_P_SPLIT:-}"
MTP_DRAFT_DEVICE="${MTP_DRAFT_DEVICE:-SYCL0}"
MTP_DRAFT_NGL="${MTP_DRAFT_NGL:-all}"
MTP_DRAFT_TYPE_K="${MTP_DRAFT_TYPE_K:-f16}"
MTP_DRAFT_TYPE_V="${MTP_DRAFT_TYPE_V:-f16}"
MTP_BACKEND_SAMPLING="${MTP_BACKEND_SAMPLING:-}"
MTP_DRAFT_POLL="${MTP_DRAFT_POLL:-}"
MTP_DRAFT_THREADS="${MTP_DRAFT_THREADS:-}"
MTP_DRAFT_THREADS_BATCH="${MTP_DRAFT_THREADS_BATCH:-}"
MTP_DRAFT_TOP_K="${MTP_DRAFT_TOP_K:-}"
MTP_DRAFT_LOGIT_GAP_MIN="${MTP_DRAFT_LOGIT_GAP_MIN:-}"
MTP_DRAFT_FAST_TOPK="${MTP_DRAFT_FAST_TOPK:-}"
MTP_DRAFT_FAST_ARGMAX="${MTP_DRAFT_FAST_ARGMAX:-}"
MTP_DRAFT_BACKEND_ARGMAX="${MTP_DRAFT_BACKEND_ARGMAX:-}"
MTP_DRAFT_BACKEND_TOPK="${MTP_DRAFT_BACKEND_TOPK:-}"
MTP_DRAFT_PROFILE="${MTP_DRAFT_PROFILE:-}"
MTP_EXTRA_ARGS="${MTP_EXTRA_ARGS:-}"
LLAMA_PARALLEL="${LLAMA_PARALLEL:-1}"
LLAMA_CACHE_RAM="${LLAMA_CACHE_RAM:-0}"

extra_args=(
  "--parallel" "$LLAMA_PARALLEL"
  "--cache-ram" "$LLAMA_CACHE_RAM"
  "--spec-type" "draft-mtp"
  "--spec-draft-model" "$MTP_DRAFT_MODEL"
  "--spec-draft-n-max" "$MTP_N_MAX"
  "--spec-draft-device" "$MTP_DRAFT_DEVICE"
  "--spec-draft-ngl" "$MTP_DRAFT_NGL"
  "--spec-draft-type-k" "$MTP_DRAFT_TYPE_K"
  "--spec-draft-type-v" "$MTP_DRAFT_TYPE_V"
)

if [[ -n "$MTP_N_MIN" ]]; then
  extra_args+=("--spec-draft-n-min" "$MTP_N_MIN")
fi
if [[ -n "$MTP_P_MIN" ]]; then
  extra_args+=("--spec-draft-p-min" "$MTP_P_MIN")
fi
if [[ -n "$MTP_P_SPLIT" ]]; then
  extra_args+=("--spec-draft-p-split" "$MTP_P_SPLIT")
fi
if [[ "$MTP_BACKEND_SAMPLING" == "0" || "$MTP_BACKEND_SAMPLING" == "false" ]]; then
  extra_args+=("--no-spec-draft-backend-sampling")
fi
if [[ -n "$MTP_DRAFT_POLL" ]]; then
  extra_args+=("--spec-draft-poll" "$MTP_DRAFT_POLL")
fi
if [[ -n "$MTP_DRAFT_THREADS" ]]; then
  extra_args+=("--spec-draft-threads" "$MTP_DRAFT_THREADS")
fi
if [[ -n "$MTP_DRAFT_THREADS_BATCH" ]]; then
  extra_args+=("--spec-draft-threads-batch" "$MTP_DRAFT_THREADS_BATCH")
fi
if [[ -n "$MTP_EXTRA_ARGS" ]]; then
  # Existing harness expects EXTRA_LLAMA_ARGS as a string and splits on spaces.
  # Keep MTP_EXTRA_ARGS for simple scalar flags only.
  read -r -a user_extra <<< "$MTP_EXTRA_ARGS"
  extra_args+=("${user_extra[@]}")
fi

# The underlying replica harness splits EXTRA_LLAMA_ARGS on whitespace. Do not
# shell-escape here: escaped comma lists such as SYCL0\,SYCL1 are passed through
# literally and llama.cpp rejects them as invalid device names.
printf -v EXTRA_LLAMA_ARGS '%s ' "${extra_args[@]}"
EXTRA_LLAMA_ARGS="${EXTRA_LLAMA_ARGS% }"
export EXTRA_LLAMA_ARGS
if [[ -n "$MTP_DRAFT_TOP_K" ]]; then
  export LLAMA_MTP_DRAFT_TOP_K="$MTP_DRAFT_TOP_K"
fi
if [[ -n "$MTP_DRAFT_LOGIT_GAP_MIN" ]]; then
  export LLAMA_MTP_DRAFT_LOGIT_GAP_MIN="$MTP_DRAFT_LOGIT_GAP_MIN"
fi
if [[ -n "$MTP_DRAFT_FAST_TOPK" ]]; then
  export LLAMA_MTP_DRAFT_FAST_TOPK="$MTP_DRAFT_FAST_TOPK"
fi
if [[ -n "$MTP_DRAFT_FAST_ARGMAX" ]]; then
  export LLAMA_MTP_DRAFT_FAST_ARGMAX="$MTP_DRAFT_FAST_ARGMAX"
fi
if [[ -n "$MTP_DRAFT_BACKEND_ARGMAX" ]]; then
  export LLAMA_MTP_DRAFT_BACKEND_ARGMAX="$MTP_DRAFT_BACKEND_ARGMAX"
fi
if [[ -n "$MTP_DRAFT_BACKEND_TOPK" ]]; then
  export LLAMA_MTP_DRAFT_BACKEND_TOPK="$MTP_DRAFT_BACKEND_TOPK"
fi
if [[ -n "$MTP_DRAFT_PROFILE" ]]; then
  export LLAMA_MTP_DRAFT_PROFILE="$MTP_DRAFT_PROFILE"
fi

export LLAMA_SERVER="${LLAMA_SERVER:-/home/steve/src/llama.cpp/build-sycl-b70/bin/llama-server}"
export CTX_SIZE="${CTX_SIZE:-8192}"
export BATCH_SIZE="${BATCH_SIZE:-512}"
export UBATCH_SIZE="${UBATCH_SIZE:-64}"
export THREADS="${THREADS:-16}"
export CACHE_TYPE_K="${CACHE_TYPE_K:-f16}"
export CACHE_TYPE_V="${CACHE_TYPE_V:-f16}"
export POLL="${POLL:-50}"
export FLASH_ATTN="${FLASH_ATTN:-off}"
export REASONING="${REASONING:-off}"
export GGML_SYCL_DISABLE_OPT="${GGML_SYCL_DISABLE_OPT:-0}"
export CANARY_REPEATS="${CANARY_REPEATS:-96}"
export BENCH_PROMPT_MODE="${BENCH_PROMPT_MODE:-long}"
export PROMPT_TOKENS="${PROMPT_TOKENS:-512}"
export MAX_TOKENS="${MAX_TOKENS:-512}"
export BENCH_REPEATS="${BENCH_REPEATS:-8}"
export READINESS_TIMEOUT_S="${READINESS_TIMEOUT_S:-1200}"

cd "$ROOT"
exec scripts/run-gemma4-26b-first-baseline.sh
