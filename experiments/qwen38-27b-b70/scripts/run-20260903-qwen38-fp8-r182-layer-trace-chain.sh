#!/usr/bin/env bash
# R182 chain (2026-09-03): layer-trace probe image, async on (a, phantom expected) then --no-async-scheduling (b, control).
set -uo pipefail
out=/mnt/fast-ai/bench-results; S=/home/steve/b70-optimization-lab/experiments/qwen38-27b-b70/scripts
common=(XPU_OPS_SHA256_OVERRIDE=4a996f86f560e22de424b86af1f5f5ab5559fd7718011dd520100d662ce18cd1 LAYERNORM_SHA256_OVERRIDE=50cf5f4f9c72f679e4318cd3e3e021a844f59ac188a891d9a4f9638188f4bce8 GEMMA_TRITON=0 RMSNORM_TRITON=0 GDN_SPLIT_MIXED=1 QUERY_ONLY=1 QUERY_KINDS=mtp1 QUERY_LAUNCH="256 64 512" QUERY_SCRIPT=$S/repro-qwen38-fp8-mtp2-phantom-first-token.py SPECULATIVE_CONFIG='{"method":"qwen3_next_mtp","num_speculative_tokens":2}' IMAGE_OVERRIDE=neural-download/vllm-openai-xpu:qwen38-fp8-mtp2-layer-trace-r182v2 IMAGE_ID_OVERRIDE=sha256:a34e55a65b412ab98f0eaa74b00856b18f6c9de99f958568779df3b9d9d1ca90)
env "${common[@]}" ROOT=$out/qwen38-fp8-r156-mtp2-phantom-layer-trace-20260903-r182 bash $S/run-20260902-qwen38-fp8-triton-rmsnorm-r152.sh
env "${common[@]}" EXTRA_SERVE_ARGS=--no-async-scheduling ROOT=$out/qwen38-fp8-r156-mtp2-phantom-layer-trace-20260903-r182b bash $S/run-20260902-qwen38-fp8-triton-rmsnorm-r152.sh
