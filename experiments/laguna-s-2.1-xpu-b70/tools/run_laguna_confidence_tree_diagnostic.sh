#!/usr/bin/env bash
# Exact-record, non-scored Laguna top-2 confidence diagnostic and analysis.
set -euo pipefail
umask 077

readonly repo_root=/home/steve/llm-optimizations
readonly vllm_root=/home/steve/src/laguna-vllm-confidence-tree-diag-20260731
readonly kernel_root=/home/steve/src/laguna-xpu-kernels-shared-elementwise-m12-20260731
readonly lock="$repo_root/experiments/laguna-s-2.1-xpu-b70/tools/runtime-lock-shared-elementwise-m12.json"
readonly run_root=/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs
readonly analysis_root=/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/analyses
readonly reference_run="$run_root/laguna-shared-elementwise-m12-formal-20260801T053000Z"
readonly stamp="$(date -u +%Y%m%dT%H%M%SZ)"
readonly run_dir="$run_root/laguna-confidence-tree-diag-$stamp"
readonly confidence_root="$run_dir/confidence-attribution"
readonly analysis="$analysis_root/laguna-confidence-tree-$stamp.json"

cd "$repo_root"
mkdir -p -- "$analysis_root"
set -- candidate B1 "$run_dir" 12 11 1 0 0 1 0 0 0 1 1 0 0 "" 64 0 "" \
  6 0 1 0 0 1 0 0.90 0 0 0 1 0 1 1 0 0 0 1 0 "$confidence_root"
[[ "$#" == 41 ]] || { echo "internal argument-count failure" >&2; exit 2; }

env \
  REPRO_VLLM_TREE="$vllm_root" \
  REPRO_KERNEL_TREE="$kernel_root" \
  REPRO_RUNTIME_LOCK="$lock" \
  REPRO_RUNTIME_LOCK_SHA256=64b0f04d29aabcabd65c0f71ff6a4c0923208228abd0559f2308e63fb3334829 \
  REPRO_NATIVE_C_SHA256=36d97dda1438cd06b5f707859edb2a0960fd05d09ef6c6d29a53aa89cdd04095 \
  REPRO_GROUPED_GEMM_SHA256=c4845ed7704a9afcf59e12f9d51e288f293f2e39966e283e2a7e322fed68b839 \
  experiments/laguna-s-2.1-xpu-b70/tools/run_laguna_replemb_measurement_leg.sh \
  "$@"

/home/steve/.venvs/deepseek-v4-xpu/bin/python \
  experiments/laguna-s-2.1-xpu-b70/tools/analyze_laguna_confidence_tree.py \
  --run "$run_dir" \
  --reference-bench "$reference_run/bench.json" \
  --out "$analysis"

printf 'diagnostic_run=%s\nanalysis=%s\n' "$run_dir" "$analysis"
