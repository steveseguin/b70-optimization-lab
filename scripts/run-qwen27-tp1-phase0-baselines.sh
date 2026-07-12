#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GPU_INDEX="${GPU_INDEX:-1}"
PORT="${PORT:-19431}"
PROFILES="${PROFILES:-no-spec mtp3 dflash5 dflash8 dflash15}"
OUT_DIR="${OUT_DIR:-$ROOT/data/qwen27-dflash-sycl-b70-phase0}"
RUN_ROOT="${RUN_ROOT:-/mnt/fast-ai/bench-results/qwen27-dflash-sycl-b70/phase0-strict}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"

mkdir -p "$OUT_DIR" "$RUN_ROOT"

for profile in $PROFILES; do
  label="qwen27-q4_0-kv8-${profile}-graph${GGML_SYCL_ENABLE_GRAPH:-0}-strict128"
  run_dir="$RUN_ROOT/${label}-${STAMP}"
  out="$OUT_DIR/${label}-${STAMP}.json"

  echo "starting profile=$profile gpu=$GPU_INDEX out=$out" >&2
  GPU_INDEX="$GPU_INDEX" \
  PORT="$PORT" \
  SPEC_PROFILE="$profile" \
  LABEL="$label" \
  RUN_DIR="$run_dir" \
  OUT="$out" \
  CACHE_TYPE_K="${CACHE_TYPE_K:-q8_0}" \
  CACHE_TYPE_V="${CACHE_TYPE_V:-q8_0}" \
  GGML_SYCL_ENABLE_GRAPH="${GGML_SYCL_ENABLE_GRAPH:-0}" \
  GGML_SYCL_ENABLE_DNN="${GGML_SYCL_ENABLE_DNN:-1}" \
  GGML_SYCL_ENABLE_OPT="${GGML_SYCL_ENABLE_OPT:-1}" \
  GGML_SYCL_ENABLE_VMM="${GGML_SYCL_ENABLE_VMM:-1}" \
    "$ROOT/scripts/run-qwen36-27b-mtp-gguf-candidate.sh"
done
