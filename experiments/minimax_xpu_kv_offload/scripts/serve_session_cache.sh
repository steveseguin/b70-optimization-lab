#!/usr/bin/env bash
set -euo pipefail

shape="${1:-c1}"
if [[ $# -gt 0 ]]; then
  shift
fi

export VLLM_MAX_MODEL_LEN="${VLLM_MAX_MODEL_LEN:-32768}"
export VLLM_MAX_NUM_BATCHED_TOKENS="${VLLM_MAX_NUM_BATCHED_TOKENS:-512}"

case "$shape" in
  c1|prod|production)
    export VLLM_MAX_NUM_SEQS="${VLLM_MAX_NUM_SEQS:-1}"
    unset VLLM_KV_OFFLOADING_SIZE
    unset VLLM_NO_SCHEDULER_RESERVE_FULL_ISL
    ;;
  c2)
    export VLLM_MAX_NUM_SEQS="${VLLM_MAX_NUM_SEQS:-2}"
    export VLLM_KV_OFFLOADING_SIZE="${VLLM_KV_OFFLOADING_SIZE:-16}"
    export VLLM_NO_SCHEDULER_RESERVE_FULL_ISL="${VLLM_NO_SCHEDULER_RESERVE_FULL_ISL:-1}"
    ;;
  c4)
    export VLLM_MAX_NUM_SEQS="${VLLM_MAX_NUM_SEQS:-4}"
    export VLLM_KV_OFFLOADING_SIZE="${VLLM_KV_OFFLOADING_SIZE:-32}"
    export VLLM_NO_SCHEDULER_RESERVE_FULL_ISL="${VLLM_NO_SCHEDULER_RESERVE_FULL_ISL:-1}"
    ;;
  c8)
    export VLLM_MAX_NUM_SEQS="${VLLM_MAX_NUM_SEQS:-8}"
    export VLLM_KV_OFFLOADING_SIZE="${VLLM_KV_OFFLOADING_SIZE:-64}"
    export VLLM_NO_SCHEDULER_RESERVE_FULL_ISL="${VLLM_NO_SCHEDULER_RESERVE_FULL_ISL:-1}"
    ;;
  *)
    echo "Usage: $0 {c1|c2|c4|c8} [extra vLLM args...]" >&2
    exit 2
    ;;
esac

exec /home/steve/bin/minimax-vllm-serve "$@"
