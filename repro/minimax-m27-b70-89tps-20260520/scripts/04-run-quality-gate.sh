#!/usr/bin/env bash
set -euo pipefail

THIS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$THIS_DIR/../.." && pwd)"

source "$THIS_DIR/configs/promoted-env.sh"
set -a
source "$THIS_DIR/configs/bench-89.env"
set +a

export OUTDIR="${OUTDIR:-/mnt/fast-ai/bench-results/minimax-m27-b70-89tps/strict}"
export LABEL="${LABEL:-repro-minimax-moe-full-forward-customop-plus-output-ar}"
export BENCH_REPEATS="${BENCH_REPEATS:-2}"
export RUN_EXTENDED_QUALITY="${RUN_EXTENDED_QUALITY:-1}"
export RUN_REPEAT_ARITHMETIC_QUALITY="${RUN_REPEAT_ARITHMETIC_QUALITY:-1}"
export REPEAT_ARITHMETIC_RUNS="${REPEAT_ARITHMETIC_RUNS:-16}"
export QUALITY_TIMEOUT="${QUALITY_TIMEOUT:-45m}"
export BENCH_TIMEOUT="${BENCH_TIMEOUT:-30m}"
export BLOCK_SIZE="${BLOCK_SIZE:-256}"

bash "$REPO_ROOT/scripts/run-minimax-strict-quality-gated-candidate.sh"

