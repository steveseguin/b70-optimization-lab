#!/usr/bin/env bash
# 2026-09-03: R186n-b = the final-norm-only probe image with --no-async-scheduling (clean control for the R186n phantom
# run, same image, so the final-norm row of request 33 can be compared exactly), then the R187 full campaign.
set -uo pipefail
out=/mnt/fast-ai/bench-results; S=/home/steve/b70-optimization-lab/experiments/qwen38-27b-b70/scripts
while kill -0 "${1:?pid to wait for}" 2>/dev/null; do sleep 20; done
env GEMMA_TRITON=0 RMSNORM_TRITON=0 GDN_SPLIT_MIXED=1 QUERY_ONLY=1 QUERY_KINDS=mtp1 QUERY_LAUNCH="256 64 512" EXTRA_SERVE_ARGS=--no-async-scheduling   QUERY_SCRIPT=$S/repro-qwen38-fp8-mtp2-phantom-first-token.py SPECULATIVE_CONFIG='{"method":"qwen3_next_mtp","num_speculative_tokens":2}'   LAYERNORM_SHA256_OVERRIDE=50cf5f4f9c72f679e4318cd3e3e021a844f59ac188a891d9a4f9638188f4bce8 XPU_OPS_SHA256_OVERRIDE=4a996f86f560e22de424b86af1f5f5ab5559fd7718011dd520100d662ce18cd1   IMAGE_OVERRIDE=neural-download/vllm-openai-xpu:qwen38-fp8-mtp2-final-trace-r186n IMAGE_ID_OVERRIDE=sha256:e7aeadbbdfcd5b35ab32fba7541691d4ef69fbe907f426226718566615d3450d   ROOT=$out/qwen38-fp8-r156-mtp2-phantom-final-op-async-off-20260903-r186nb bash $S/run-20260902-qwen38-fp8-triton-rmsnorm-r152.sh
# (R187 already running as pid 47866 at 20:02; this rerun only does R186n-b)
