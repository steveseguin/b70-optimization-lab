#!/usr/bin/env bash
set -euo pipefail

# Promoted Qwen27 TP2 lane: graph-correct pinned public oneCCL plus a captured
# intrinsic-MTP draft. The compiled all-gather custom-op boundary avoids
# Inductor's XPU-graph-incompatible functional wait_tensor lowering.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"

export VLLM_XPU_DRAFT_DISABLE_CUDAGRAPHS="${VLLM_XPU_DRAFT_DISABLE_CUDAGRAPHS:-0}"
export VLLM_XPU_COMPILE_ALLGATHER_CUSTOM_OP="${VLLM_XPU_COMPILE_ALLGATHER_CUSTOM_OP:-1}"
export CANDIDATE_ENTRYPOINT="$0"

exec "$ROOT/experiments/qwen36-27b-autoround-int4-b70/scripts/run-tp2-oneccl-public4ce-candidate.sh"
