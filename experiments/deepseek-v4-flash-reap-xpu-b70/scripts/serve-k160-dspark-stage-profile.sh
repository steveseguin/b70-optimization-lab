#!/usr/bin/env bash
set -euo pipefail

root="/home/steve/llm-optimizations"
serve="${root}/experiments/deepseek-v4-flash-reap-xpu-b70/scripts/serve-k160-dspark-candidate.sh"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
run_dir="${RUN_DIR:-/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/dspark7-exactm7-stage-profile-${stamp}}"
trace_dir="${run_dir}/trace"

test ! -e "${run_dir}"

export RUN_DIR="${run_dir}"
export VLLM_COMMIT="${VLLM_COMMIT:-1f6d6be49c57a2d5b71c6ea4926d4b01ca612254}"
export DSPARK_GRAPH_MODE="${DSPARK_PROFILE_GRAPH_MODE:-eager}"
export DSPARK_DRAFT_GRAPH_MODE="${DSPARK_PROFILE_DRAFT_GRAPH_MODE:-eager}"
export DSPARK_SPEC_TOKENS=7
export VLLM_XPU_DSPARK_EXACT_QUERY_CAPTURE=1
export VLLM_XPU_GREEDY_FUSED_REJECTION=1
export VLLM_XPU_DSPARK_FIXED_M7_TARGET_INPUTS=1
export VLLM_XPU_DSPARK_PERSISTENT_MARKOV=1
export VLLM_XPU_DSPARK_REPLICATED_MARKOV_W1=1
export VLLM_XPU_V4_COMPRESSOR_BATCHED_EXACT_MAX_M=8
export VLLM_XPU_V4_BLOCK_FP8_W8A16_MAX_M=8
export VLLM_XPU_MXFP4_SMALL_M_N=128
export VLLM_XPU_DSPARK_PIECEWISE_SAMPLE_GRAPH="${VLLM_XPU_DSPARK_PIECEWISE_SAMPLE_GRAPH:-0}"
export VLLM_CUSTOM_SCOPES_FOR_PROFILING=1
export DSPARK_ADDITIONAL_VLLM_ARGS="--profiler-config.profiler=torch --profiler-config.torch_profiler_dir=${trace_dir} --profiler-config.torch_profiler_with_stack=false --profiler-config.torch_profiler_record_shapes=true --profiler-config.torch_profiler_use_gzip=false"

printf 'run_dir=%s\n' "${run_dir}"
exec "${serve}"
