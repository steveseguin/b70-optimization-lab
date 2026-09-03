#!/usr/bin/env bash
# R181 (2026-09-03): the R176 probe image with --no-async-scheduling (the no-phantom control), same 64-prompt depth-2 pass,
# to compare layer-0 GDN kernel inputs/outputs for the 33rd request against the async-on R176 run.
set -uo pipefail
out=/mnt/fast-ai/bench-results; S=/home/steve/b70-optimization-lab/experiments/qwen38-27b-b70/scripts
env XPU_OPS_SHA256_OVERRIDE=4a996f86f560e22de424b86af1f5f5ab5559fd7718011dd520100d662ce18cd1 LAYERNORM_SHA256_OVERRIDE=50cf5f4f9c72f679e4318cd3e3e021a844f59ac188a891d9a4f9638188f4bce8 \
  GEMMA_TRITON=0 RMSNORM_TRITON=0 GDN_SPLIT_MIXED=1 QUERY_ONLY=1 QUERY_KINDS=mtp1 QUERY_LAUNCH="256 64 512" EXTRA_SERVE_ARGS=--no-async-scheduling \
  QUERY_SCRIPT=$S/repro-qwen38-fp8-mtp2-phantom-first-token.py SPECULATIVE_CONFIG='{"method":"qwen3_next_mtp","num_speculative_tokens":2}' \
  IMAGE_OVERRIDE=neural-download/vllm-openai-xpu:qwen38-fp8-mtp2-state-slot-probe-r176 IMAGE_ID_OVERRIDE=sha256:85c287a73cff8ed0cdebd1f93777ba88b2bb26b89b8a753b96fb3bcc52c08616 \
  ROOT=$out/qwen38-fp8-r156-mtp2-phantom-state-slot-async-off-20260903-r181 bash $S/run-20260902-qwen38-fp8-triton-rmsnorm-r152.sh
