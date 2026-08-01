#!/usr/bin/env bash
set -euo pipefail
umask 077

readonly repo_root=/home/steve/llm-optimizations
readonly vllm_root=/home/steve/src/laguna-vllm-shared-elementwise-m12-20260731
readonly kernel_root=/home/steve/src/laguna-xpu-kernels-shared-elementwise-m12-20260731
readonly lock="$repo_root/experiments/laguna-s-2.1-xpu-b70/tools/runtime-lock-shared-elementwise-m12.json"
readonly run_dir="/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-shared-elementwise-m12-repro-$(date -u +%Y%m%dT%H%M%SZ)"

cd "$repo_root"
set -- candidate B1 "$run_dir" 12 11 1 0 0 1 0 0 0 1 1 0 0 "" 64 0 "" \
  6 0 1 0 0 1 0 0.90 0 0 0 1 0 1 1 0 0 0 1
[[ "$#" == 39 ]] || { echo "internal argument-count failure" >&2; exit 2; }

env \
  REPRO_VLLM_TREE="$vllm_root" \
  REPRO_KERNEL_TREE="$kernel_root" \
  REPRO_RUNTIME_LOCK="$lock" \
  REPRO_RUNTIME_LOCK_SHA256=64b0f04d29aabcabd65c0f71ff6a4c0923208228abd0559f2308e63fb3334829 \
  REPRO_NATIVE_C_SHA256=36d97dda1438cd06b5f707859edb2a0960fd05d09ef6c6d29a53aa89cdd04095 \
  REPRO_GROUPED_GEMM_SHA256=c4845ed7704a9afcf59e12f9d51e288f293f2e39966e283e2a7e322fed68b839 \
  experiments/laguna-s-2.1-xpu-b70/tools/run_laguna_replemb_measurement_leg.sh \
  "$@"
