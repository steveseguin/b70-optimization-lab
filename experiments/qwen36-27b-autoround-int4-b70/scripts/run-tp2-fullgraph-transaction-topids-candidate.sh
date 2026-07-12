#!/usr/bin/env bash
set -euo pipefail

# Exact greedy verifier consumer: reduce dense rank-local target logits to top
# IDs before TP communication, on top of the promoted fullgraph transaction
# record. This remains diagnostic until crossover and full quality pass.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
export VLLM_XPU_SPEC_GREEDY_TOP_IDS=1
export LABEL="${LABEL:-qwen27-tp2-fullgraph-transaction-topids}"
export VLLM_CACHE_ROOT="${VLLM_CACHE_ROOT:-/mnt/usb-models/llm-runtime/vllm-cache/qwen27-fullgraph-transaction-topids-20260711}"
export CANDIDATE_ENTRYPOINT="$0"

exec "$ROOT/experiments/qwen36-27b-autoround-int4-b70/scripts/run-tp2-fullgraph-transaction-candidate.sh"
