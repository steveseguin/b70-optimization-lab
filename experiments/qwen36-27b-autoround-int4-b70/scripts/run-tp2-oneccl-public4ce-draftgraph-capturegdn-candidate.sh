#!/usr/bin/env bash
set -euo pipefail

# Promoted Qwen27 TP2 lane: pinned graph-correct public oneCCL, captured
# intrinsic-MTP draft, and GDN cores captured inside their surrounding target
# PIECEWISE segments. The latter reduces the target from 129 to 33 graph
# pieces while preserving the strict target-verified ReplaySSM path.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"

export VLLM_XPU_DDTREE_CAPTURE_GDN_CORE="${VLLM_XPU_DDTREE_CAPTURE_GDN_CORE:-1}"
export CANDIDATE_ENTRYPOINT="$0"

exec "$ROOT/experiments/qwen36-27b-autoround-int4-b70/scripts/run-tp2-oneccl-public4ce-draftgraph-candidate.sh"
