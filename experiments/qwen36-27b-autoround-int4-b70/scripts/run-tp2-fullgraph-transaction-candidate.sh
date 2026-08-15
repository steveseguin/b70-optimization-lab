#!/usr/bin/env bash
set -euo pipefail

# Promoted Qwen27 TP2 short-context lane: graph-safe FlashAttention full target
# graph plus exact ReplaySSM pending-metadata/direct-output transaction fusions.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
STAGE="${STAGE:-$ROOT/experiments/qwen27_graphsafe_flash_attention/staged-package}"

export PYTHONPATH="$STAGE${PYTHONPATH:+:$PYTHONPATH}"
export VLLM_XPU_KERNELS_SRC="$STAGE"
export VLLM_XPU_FA2_FORCE_CHUNK_DECODE="${VLLM_XPU_FA2_FORCE_CHUNK_DECODE:-1}"
export VLLM_XPU_DDTREE_FULL_GRAPH="${VLLM_XPU_DDTREE_FULL_GRAPH:-1}"
export VLLM_XPU_GDN_REPLAYSSM_FUSE_PENDING_METADATA="${VLLM_XPU_GDN_REPLAYSSM_FUSE_PENDING_METADATA:-1}"
export VLLM_XPU_GDN_REPLAYSSM_DIRECT_CORE_OUT="${VLLM_XPU_GDN_REPLAYSSM_DIRECT_CORE_OUT:-1}"
if [[ -z "${COMPILATION_CONFIG:-}" ]]; then
  export COMPILATION_CONFIG='{"cudagraph_mode":"FULL_AND_PIECEWISE","cudagraph_capture_sizes":[4],"max_cudagraph_capture_size":4}'
else
  export COMPILATION_CONFIG
fi
export VLLM_CACHE_ROOT="${VLLM_CACHE_ROOT:-/mnt/usb-models/llm-runtime/vllm-cache/qwen27-fullgraph-transaction-20260711}"
export LABEL="${LABEL:-qwen27-tp2-fp16-fullgraph-transaction}"
export CANDIDATE_ENTRYPOINT="$0"

exec "$ROOT/experiments/qwen36-27b-autoround-int4-b70/scripts/run-tp2-oneccl-public4ce-draftgraph-capturegdn-fp16-candidate.sh"
