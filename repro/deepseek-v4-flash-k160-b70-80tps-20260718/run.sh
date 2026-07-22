#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(git -C "${script_dir}" rev-parse --show-toplevel)"
launcher="${repo_root}/experiments/deepseek-v4-flash-reap-xpu-b70/scripts/serve-k160-dspark-candidate.sh"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"

export VLLM_TREE="${VLLM_TREE:-/home/steve/src/deepseek-v4-vllm-record-264c7f2f7-exact}"
export VLLM_COMMIT=264c7f2f7df21ddeeab32ecca0353133344f1ac9
export KERNEL_TREE="${KERNEL_TREE:-/home/steve/src/deepseek-v4-xpu-kernels-record-313156737-exact}"
export KERNEL_COMMIT=31315673737d95da0f79179c8f755260ef02c1d6
export ONECCL_SOURCE_TREE="${ONECCL_SOURCE_TREE:-/home/steve/src/oneccl-2021.17.2-b70-sizegate}"
export ONECCL_LIB_DIR="${ONECCL_LIB_DIR:-/mnt/fast-ai/runtime/oneccl-2021.17.2-b70-wideepoch-48fda4f/lib}"
export ONECCL_FORCE_PRELOAD=1
export B70_ONECCL_SYCL_ALLREDUCE_MAX_BYTES=131072

test "$(git -C "${VLLM_TREE}" rev-parse HEAD)" = "${VLLM_COMMIT}"
test "$(git -C "${KERNEL_TREE}" rev-parse HEAD)" = "${KERNEL_COMMIT}"
test "$(git -C "${ONECCL_SOURCE_TREE}" rev-parse HEAD)" = "48fda4f0e074db005596d6899d5227d3f0316c12"
test -z "$(git -C "${VLLM_TREE}" status --porcelain)"
test -z "$(git -C "${KERNEL_TREE}" status --porcelain)"
test -f "${ONECCL_LIB_DIR}/libccl.so.1"

export RUN_DIR="${RUN_DIR:-/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/dspark7-80tps-repro-${stamp}}"
export DSPARK_GRAPH_MODE=piecewise
export DSPARK_DRAFT_GRAPH_MODE=piecewise
export DSPARK_SPEC_TOKENS=7
export VLLM_XPU_DSPARK_EXACT_QUERY_CAPTURE=1
export VLLM_XPU_GREEDY_FUSED_REJECTION=1
export VLLM_XPU_GREEDY_SHARDED_TARGET_ARGMAX=1
export VLLM_XPU_DSPARK_FIXED_M7_TARGET_INPUTS=1
export VLLM_XPU_DSPARK_PERSISTENT_MARKOV=1
export VLLM_XPU_DSPARK_REPLICATED_MARKOV_W1=1
export VLLM_XPU_V4_COMPRESSOR_BATCHED_EXACT_MAX_M=8
export VLLM_XPU_V4_BLOCK_FP8_W8A16_MAX_M=8
export VLLM_XPU_MXFP4_SMALL_M_N=128
export VLLM_XPU_V4_ROUTER_NORM_MAX_M=8

# Fail closed on post-record and rejected experiment selectors.
export VLLM_XPU_DSPARK_PIECEWISE_SAMPLE_GRAPH=0
export VLLM_XPU_DSPARK_FUSED_CONTEXT_WKV=0
export VLLM_XPU_DSPARK_REPLICATED_MARKOV=0
export VLLM_XPU_DSPARK_FIXED_M8_TARGET_BUILDER=0
export VLLM_XPU_DSPARK_PERSISTENT_MARKOV_WIDTH_SCREEN=0
export VLLM_XPU_DSPARK_MARKOV_W2_DPAS=0
export VLLM_XPU_V4_MHC_POST_PRE_M8_DPAS=0
export VLLM_XPU_V4_MHC_POST_PRE_M8_PAIRTILE=0
export VLLM_XPU_DSPARK_SHARDED_MARKOV_ARGMAX=0
export VLLM_XPU_DSPARK_HOST_MARKOV_ARGMAX=0
export VLLM_XPU_DSPARK_IPC_EVENT_MARKOV_ARGMAX=0
export VLLM_XPU_DSPARK_IPC_EVENT_MARKOV7_BUNDLE=0
export VLLM_XPU_DSPARK_DIRECT_DRAFT_OUTPUT=0
export VLLM_XPU_DSPARK_GREEDY_COPY_ELISION=0

printf 'DeepSeek V4 Flash K160 record launcher\n'
printf 'record_high_tok_s=80.820052\n'
printf 'run_dir=%s\n' "${RUN_DIR}"
exec "${launcher}"
