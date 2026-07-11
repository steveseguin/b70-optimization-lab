#!/usr/bin/env bash
set -euo pipefail

# Base Qwen27 TP2 target-graph / eager-draft candidate. The installed oneCCL
# runtime corrupts this packed-verifier graph shape, so do not invoke this base
# wrapper directly for a promoted run. Use run-tp2-oneccl-public4ce-candidate.sh,
# which checksum-gates and injects the graph-correct public oneCCL build. This
# wrapper still runs the complete strict fresh suite and quality gate.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"

export MODEL_DIR="${MODEL_DIR:-/mnt/fast-ai/llm-cache/hf/hub/models--webhie--Qwen3.6-27B-int4-AutoRound/snapshots/f5750c90b3776db658594df5fe8051098226dd8e}"
export LABEL="${LABEL:-qwen27-tp2-targetgraph-drafteager}"
export GPU_INDEX="${GPU_INDEX:-0,1}"
export ZE_AFFINITY_MASK="${ZE_AFFINITY_MASK:-$GPU_INDEX}"
export ONEAPI_DEVICE_SELECTOR="${ONEAPI_DEVICE_SELECTOR:-level_zero:0,1}"
export TENSOR_PARALLEL_SIZE=2
export PORT="${PORT:-19438}"
export SERVED_MODEL_NAME="${SERVED_MODEL_NAME:-qwen27-tp2-targetgraph-drafteager}"

export MAX_MODEL_LEN="${MAX_MODEL_LEN:-2048}"
export MAX_NUM_BATCHED_TOKENS="${MAX_NUM_BATCHED_TOKENS:-1024}"
export MAX_NUM_SEQS=1
export GPU_MEMORY_UTILIZATION="${GPU_MEMORY_UTILIZATION:-0.95}"
export QWEN36_27B_ENABLE_MTP="${QWEN36_27B_ENABLE_MTP:-1}"
export NUM_SPECULATIVE_TOKENS="${NUM_SPECULATIVE_TOKENS:-3}"

export QWEN36_27B_ENABLE_XPU_GRAPH=1
export VLLM_XPU_ENABLE_XPU_GRAPH=1
export VLLM_XPU_FORCE_GRAPH_WITH_COMM=1
export VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE=1
export VLLM_XPU_DRAFT_DISABLE_CUDAGRAPHS="${VLLM_XPU_DRAFT_DISABLE_CUDAGRAPHS:-1}"
if [[ -z "${COMPILATION_CONFIG:-}" ]]; then
  export COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE","max_cudagraph_capture_size":8}'
else
  export COMPILATION_CONFIG
fi

export VLLM_XPU_GDN_PROMOTE_ACCEPTED_SPEC_STATE=1
export VLLM_XPU_GDN_NONSPEC_POSTPROCESS_ACCEPTED_STATE=0
export VLLM_XPU_GDN_REPLAYSSM_SPEC=1
# ReplaySSM keeps two non-overlapping speculative windows. Derive the minimum
# ring length from k so depth screens cannot silently inherit the MTP3-only
# value of 8; callers may still request a larger power-of-two ring.
export VLLM_XPU_GDN_REPLAYSSM_SPEC_CACHE_LEN="${VLLM_XPU_GDN_REPLAYSSM_SPEC_CACHE_LEN:-$((2 * (NUM_SPECULATIVE_TOKENS + 1)))}"
export VLLM_XPU_GDN_REPLAYSSM_TORCH_FALLBACK="${VLLM_XPU_GDN_REPLAYSSM_TORCH_FALLBACK:-0}"
export VLLM_XPU_GDN_REPLAYSSM_STAGE_CONV_TORCH_FALLBACK="${VLLM_XPU_GDN_REPLAYSSM_STAGE_CONV_TORCH_FALLBACK:-0}"
export VLLM_XPU_GDN_REPLAYSSM_COMMIT_IN_FORWARD=1
export VLLM_XPU_GDN_REPLAYSSM_SLOT_MGMT_TORCH_FALLBACK=1

export VLLM_XPU_LM_HEAD_INT8=1
export VLLM_XPU_LM_HEAD_INT8_SCOPE=all
export VLLM_XPU_LM_HEAD_INT8_SCALE_DTYPE="${VLLM_XPU_LM_HEAD_INT8_SCALE_DTYPE:-bf16}"
export VLLM_XPU_DRAFT_LM_HEAD_INT4=1
export VLLM_XPU_DRAFT_LM_HEAD_INT4_GROUP_SIZE=128
export VLLM_XPU_DRAFT_LM_HEAD_INT4_SCALE_DTYPE="${VLLM_XPU_DRAFT_LM_HEAD_INT4_SCALE_DTYPE:-bf16}"
export VLLM_ENABLE_FLA_PACKED_RECURRENT_DECODE=1

export CCL_ATL_TRANSPORT="${CCL_ATL_TRANSPORT:-ofi}"
export CCL_TOPO_P2P_ACCESS="${CCL_TOPO_P2P_ACCESS:-1}"
export CCL_ZE_IPC_EXCHANGE="${CCL_ZE_IPC_EXCHANGE:-pidfd}"

export BENCH_MAX_TOKENS="${BENCH_MAX_TOKENS:-512}"
export BENCH_METRIC_TOKENS=100
export QUALITY_REPEAT_RUNS="${QUALITY_REPEAT_RUNS:-64}"
export QUALITY_LONG_CONTEXT_TOKENS="${QUALITY_LONG_CONTEXT_TOKENS:-1024}"
export QUALITY_BASELINE_JSON="${QUALITY_BASELINE_JSON:-$ROOT/data/qwen36-27b-autoround-int4-b70-baselines/quality-qwen27-replayssm-draftint4-current-confirm-20260706T140317Z-repeat64-ctx1024-20260706T140317Z.json}"
export CANDIDATE_ENTRYPOINT="${CANDIDATE_ENTRYPOINT:-$0}"

exec "$ROOT/experiments/qwen36-27b-autoround-int4-b70/scripts/run-vllm-candidate.sh"
