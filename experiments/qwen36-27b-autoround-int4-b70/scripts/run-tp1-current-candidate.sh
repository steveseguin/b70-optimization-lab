#!/usr/bin/env bash
set -euo pipefail

# Canonical one-B70 Qwen27 recipe. This makes the implicit defaults from the
# 68.236 tok/s record explicit, including captured intrinsic-MTP draft replay.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"

export MODEL_DIR="${MODEL_DIR:-/mnt/fast-ai/llm-cache/hf/hub/models--webhie--Qwen3.6-27B-int4-AutoRound/snapshots/f5750c90b3776db658594df5fe8051098226dd8e}"
export LABEL="${LABEL:-qwen27-tp1-current-draftgraph}"
export GPU_INDEX="${GPU_INDEX:-0}"
export ZE_AFFINITY_MASK="${ZE_AFFINITY_MASK:-$GPU_INDEX}"
export ONEAPI_DEVICE_SELECTOR=level_zero:0
export TENSOR_PARALLEL_SIZE=1
export PORT="${PORT:-19440}"
export SERVED_MODEL_NAME="${SERVED_MODEL_NAME:-qwen27-tp1-current}"

export MAX_MODEL_LEN="${MAX_MODEL_LEN:-2048}"
export MAX_NUM_BATCHED_TOKENS="${MAX_NUM_BATCHED_TOKENS:-1024}"
export MAX_NUM_SEQS=1
export GPU_MEMORY_UTILIZATION="${GPU_MEMORY_UTILIZATION:-0.95}"
export QWEN36_27B_ENABLE_MTP=1
export NUM_SPECULATIVE_TOKENS=3

export QWEN36_27B_ENABLE_XPU_GRAPH=1
export VLLM_XPU_ENABLE_XPU_GRAPH=1
export VLLM_XPU_FORCE_GRAPH_WITH_COMM=1
export VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE=1
export VLLM_XPU_DRAFT_DISABLE_CUDAGRAPHS="${VLLM_XPU_DRAFT_DISABLE_CUDAGRAPHS:-0}"
if [[ -z "${COMPILATION_CONFIG:-}" ]]; then
  export COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE","max_cudagraph_capture_size":8}'
else
  export COMPILATION_CONFIG
fi

export VLLM_XPU_GDN_PROMOTE_ACCEPTED_SPEC_STATE=1
export VLLM_XPU_GDN_NONSPEC_POSTPROCESS_ACCEPTED_STATE=0
export VLLM_XPU_GDN_REPLAYSSM_SPEC=1
export VLLM_XPU_GDN_REPLAYSSM_SPEC_CACHE_LEN=8
export VLLM_XPU_GDN_REPLAYSSM_TORCH_FALLBACK=0
export VLLM_XPU_GDN_REPLAYSSM_STAGE_CONV_TORCH_FALLBACK=0
export VLLM_XPU_GDN_REPLAYSSM_COMMIT_IN_FORWARD=1
export VLLM_XPU_GDN_REPLAYSSM_SLOT_MGMT_TORCH_FALLBACK=1

export VLLM_XPU_LM_HEAD_INT8=1
export VLLM_XPU_LM_HEAD_INT8_SCOPE=all
export VLLM_XPU_LM_HEAD_INT8_SCALE_DTYPE=bf16
export VLLM_XPU_DRAFT_LM_HEAD_INT4=1
export VLLM_XPU_DRAFT_LM_HEAD_INT4_GROUP_SIZE=128
export VLLM_XPU_DRAFT_LM_HEAD_INT4_SCALE_DTYPE=bf16

export BENCH_MAX_TOKENS="${BENCH_MAX_TOKENS:-512}"
export BENCH_METRIC_TOKENS=100
export QUALITY_REPEAT_RUNS="${QUALITY_REPEAT_RUNS:-64}"
export QUALITY_LONG_CONTEXT_TOKENS="${QUALITY_LONG_CONTEXT_TOKENS:-1024}"
# Use ${VAR-default}, not ${VAR:-default}: an explicitly empty value must mean
# "no baseline", not "silently grade against the Qwen3.6 model's baseline".
export QUALITY_BASELINE_JSON="${QUALITY_BASELINE_JSON-$ROOT/data/qwen36-27b-autoround-int4-b70-baselines/quality-qwen27-replayssm-draftint4-current-confirm-20260706T140317Z-repeat64-ctx1024-20260706T140317Z.json}"
export CANDIDATE_ENTRYPOINT="${CANDIDATE_ENTRYPOINT:-$0}"

exec "$ROOT/experiments/qwen36-27b-autoround-int4-b70/scripts/run-vllm-candidate.sh"
