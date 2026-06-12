#!/usr/bin/env bash
set -euo pipefail

ORACLE_TRACE="${ORACLE_TRACE:-/home/steve/llm-optimizations/data/qwen36-quark-int8-tp4-accepted-restored-current-oracle-baseline-20260612i.json}"
TAG="${TAG:-oracle${NUM_SPECULATIVE_TOKENS:-5}-trace}"

export VLLM_XPU_ORACLE_DRAFT_TRACE="$ORACLE_TRACE"
export VLLM_XPU_ORACLE_DRAFT_MIN_PREFIX="${VLLM_XPU_ORACLE_DRAFT_MIN_PREFIX:-1}"
export VLLM_XPU_ORACLE_DRAFT_LOG="${VLLM_XPU_ORACLE_DRAFT_LOG:-/tmp/qwen36-${TAG}-oracle-draft-20260611.jsonl}"
export VLLM_XPU_ORACLE_DRAFT_LOG_MAX_LINES="${VLLM_XPU_ORACLE_DRAFT_LOG_MAX_LINES:-20000}"

export NUM_SPECULATIVE_TOKENS="${NUM_SPECULATIVE_TOKENS:-5}"
export PROMPT_LOOKUP_MIN="${PROMPT_LOOKUP_MIN:-2}"
export PROMPT_LOOKUP_MAX="${PROMPT_LOOKUP_MAX:-5}"
export TAG
export SPEC_TRACE_FILE="${SPEC_TRACE_FILE:-/tmp/qwen36-${TAG}-spec-trace-20260611.jsonl}"
export LOG_PATH="${LOG_PATH:-/tmp/qwen36-quark-int8-tp4-${TAG}-20260611.log}"

rm -f "$VLLM_XPU_ORACLE_DRAFT_LOG" "$SPEC_TRACE_FILE"

exec "$(dirname "${BASH_SOURCE[0]}")/launch-qwen36-quark-int8-ngram-trace.sh"
