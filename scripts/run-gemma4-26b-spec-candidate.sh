#!/usr/bin/env bash
set -euo pipefail

# Thin wrapper for Gemma 4 26B A4B Q8 llama.cpp speculative candidates that do
# not necessarily use an MTP draft model. It keeps the same quality/benchmark
# harness as the baseline and exposes draftless n-gram knobs for sweeps.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

SPEC_TYPE="${SPEC_TYPE:-ngram-simple}"
SPEC_EXTRA_ARGS="${SPEC_EXTRA_ARGS:-}"
LLAMA_PARALLEL="${LLAMA_PARALLEL:-1}"
LLAMA_CACHE_RAM="${LLAMA_CACHE_RAM:-0}"

extra_args=(
  "--parallel" "$LLAMA_PARALLEL"
  "--cache-ram" "$LLAMA_CACHE_RAM"
  "--spec-type" "$SPEC_TYPE"
)

if [[ -n "$SPEC_EXTRA_ARGS" ]]; then
  # Keep SPEC_EXTRA_ARGS for simple scalar flags only.
  read -r -a user_extra <<< "$SPEC_EXTRA_ARGS"
  extra_args+=("${user_extra[@]}")
fi

# Downstream run-gemma4-26b-llamacpp-replica.sh splits EXTRA_LLAMA_ARGS with
# read -a rather than shell-eval. Keep this as plain scalar args so comma
# values such as "ngram-mod,draft-mtp" survive unchanged.
EXTRA_LLAMA_ARGS="${extra_args[*]}"
export EXTRA_LLAMA_ARGS

export LLAMA_SERVER="${LLAMA_SERVER:-/home/steve/src/llama.cpp-gemma-record-stack/build-sycl-b70-aot-bmg-g31/bin/llama-server}"
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
export BENCH_PROMPT_MODE="${BENCH_PROMPT_MODE:-filled-long}"
export PROMPT_TOKENS="${PROMPT_TOKENS:-512}"
export MAX_TOKENS="${MAX_TOKENS:-512}"
export BENCH_REPEATS="${BENCH_REPEATS:-8}"
export READINESS_TIMEOUT_S="${READINESS_TIMEOUT_S:-1200}"

cd "$ROOT"
exec scripts/run-gemma4-26b-first-baseline.sh
