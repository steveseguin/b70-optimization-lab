#!/usr/bin/env bash
set -euo pipefail

# Quality-gated Qwen27 TP2 record lane. FP16 target compute preserves the
# AutoRound INT4 weights and passed exact/repeat128/baseline/1K quality while
# selecting faster B70 kernels than the checkpoint's default BF16 compute.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"

case " ${VLLM_EXTRA_ARGS:-} " in
  *" --dtype float16 "*) ;;
  *) export VLLM_EXTRA_ARGS="--dtype float16${VLLM_EXTRA_ARGS:+ $VLLM_EXTRA_ARGS}" ;;
esac
export CANDIDATE_ENTRYPOINT="$0"

exec "$ROOT/experiments/qwen36-27b-autoround-int4-b70/scripts/run-tp2-oneccl-public4ce-draftgraph-capturegdn-candidate.sh"
