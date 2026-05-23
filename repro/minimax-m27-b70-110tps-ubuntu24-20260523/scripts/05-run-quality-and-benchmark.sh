#!/usr/bin/env bash
set -euo pipefail

THIS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$THIS_DIR/../.." && pwd)"
source "$THIS_DIR/configs/runtime-env.sh"
source "$VENV/bin/activate"
source /opt/intel/oneapi/compiler/2025.3/env/vars.sh >/dev/null 2>&1

mkdir -p "$BENCH_ROOT"

export MODEL VENV HF_HOME VLLM_CACHE_ROOT
export PUBLISH_ROOT="$REPO_ROOT"
export OUTDIR="$BENCH_ROOT/strict"
export LABEL="repro-minimax-moe-full-forward-customop-plus-output-ar"
export TP=4
export MAX_MODEL_LEN=2048
export MAX_BATCHED_TOKENS=512
export MAX_NUM_SEQS=1
export INPUT_LEN=512
export OUTPUT_LEN=1536
export NUM_PROMPTS=1
export BLOCK_SIZE=256
export DTYPE=float16
export COMPILATION_CONFIG_JSON='{"use_inductor_graph_partition":true,"compile_sizes":[1],"cudagraph_mode":"PIECEWISE"}'
export RUN_REPEAT_ARITHMETIC_QUALITY="${RUN_REPEAT_ARITHMETIC_QUALITY:-1}"
export RUN_EXTENDED_QUALITY="${RUN_EXTENDED_QUALITY:-1}"
export BENCH_REPEATS="${BENCH_REPEATS:-4}"

bash "$REPO_ROOT/scripts/run-minimax-strict-quality-gated-candidate.sh"
