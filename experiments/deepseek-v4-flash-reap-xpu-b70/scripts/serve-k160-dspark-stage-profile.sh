#!/usr/bin/env bash
set -euo pipefail

root="/home/steve/llm-optimizations"
serve="${root}/experiments/deepseek-v4-flash-reap-xpu-b70/scripts/serve-k160-dspark-candidate.sh"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
run_dir="${RUN_DIR:-/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/dspark7-exactm7-stage-profile-${stamp}}"
trace_dir="${run_dir}/trace"

test ! -e "${run_dir}"

export RUN_DIR="${run_dir}"
export VLLM_COMMIT="${VLLM_COMMIT:-e19c19f4c1071182d6c772416955f70e936b31f7}"
export DSPARK_GRAPH_MODE=piecewise
export DSPARK_DRAFT_GRAPH_MODE=piecewise
export DSPARK_SPEC_TOKENS=7
export VLLM_XPU_DSPARK_EXACT_QUERY_CAPTURE=1
export VLLM_XPU_DSPARK_PIECEWISE_SAMPLE_GRAPH="${VLLM_XPU_DSPARK_PIECEWISE_SAMPLE_GRAPH:-0}"
export VLLM_CUSTOM_SCOPES_FOR_PROFILING=1
export DSPARK_ADDITIONAL_VLLM_ARGS="--profiler-config.profiler=torch --profiler-config.torch_profiler_dir=${trace_dir} --profiler-config.torch_profiler_with_stack=false --profiler-config.torch_profiler_record_shapes=true --profiler-config.torch_profiler_use_gzip=false"

printf 'run_dir=%s\n' "${run_dir}"
exec "${serve}"
