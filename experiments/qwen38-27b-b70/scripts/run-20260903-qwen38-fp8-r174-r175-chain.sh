#!/usr/bin/env bash
# R174 (blocking H2D copies, depth-2 64-prompt pass) then R175 (depth-1 ladders with async scheduling off) on the R156 lane.
set -uo pipefail
out=/mnt/fast-ai/bench-results; S=/home/steve/b70-optimization-lab/experiments/qwen38-27b-b70/scripts
common=(XPU_OPS_SHA256_OVERRIDE=6a7761930cd8b9e3f67902648ba5aaaf708567cebf70fcedda595d698f26b064 LAYERNORM_SHA256_OVERRIDE=50cf5f4f9c72f679e4318cd3e3e021a844f59ac188a891d9a4f9638188f4bce8 GEMMA_TRITON=0 RMSNORM_TRITON=0 GDN_SPLIT_MIXED=1)
env "${common[@]}" IMAGE_OVERRIDE=neural-download/vllm-openai-xpu:qwen38-fp8-mtp2-blocking-h2d-r174 IMAGE_ID_OVERRIDE=sha256:59621bffbe666bcf666baaf82244acae2da517e0eca2a88fef86b319ba606022 \
  ROOT=$out/qwen38-fp8-r156-mtp2-phantom-blocking-h2d-20260903-r174 QUERY_ONLY=1 QUERY_KINDS=mtp1 QUERY_LAUNCH="256 64 512" \
  QUERY_SCRIPT=$S/repro-qwen38-fp8-mtp2-phantom-first-token.py SPECULATIVE_CONFIG='{"method":"qwen3_next_mtp","num_speculative_tokens":2}' \
  bash $S/run-20260902-qwen38-fp8-triton-rmsnorm-r152.sh
env "${common[@]}" IMAGE_OVERRIDE=neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-gdn-split-mixed-r156 IMAGE_ID_OVERRIDE=sha256:173660ec18c6e98a14b9a4f573922abe9d3414999056f07ab5c3c14b55d6ceb0 \
  EXTRA_SERVE_ARGS=--no-async-scheduling ROOT=$out/qwen38-fp8-r156-mtp1-async-off-ladder-20260903-r175 LADDERS_ONLY=1 \
  bash $S/run-20260902-qwen38-fp8-triton-rmsnorm-r152.sh
