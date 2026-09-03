#!/usr/bin/env bash
# R180 (2026-09-03): R178 + MambaManager recording of new block ids (the half R178 lacked). Same 64-prompt depth-2 pass,
# async scheduling on. Waits for the R176 rerun (pid $1) to exit first so one lane holds the devices at a time.
set -uo pipefail
out=/mnt/fast-ai/bench-results; S=/home/steve/b70-optimization-lab/experiments/qwen38-27b-b70/scripts
while kill -0 "${1:?r176 pid}" 2>/dev/null; do sleep 30; done
env XPU_OPS_SHA256_OVERRIDE=6a7761930cd8b9e3f67902648ba5aaaf708567cebf70fcedda595d698f26b064 LAYERNORM_SHA256_OVERRIDE=50cf5f4f9c72f679e4318cd3e3e021a844f59ac188a891d9a4f9638188f4bce8 \
  GEMMA_TRITON=0 RMSNORM_TRITON=0 GDN_SPLIT_MIXED=1 QUERY_ONLY=1 QUERY_KINDS=mtp1 QUERY_LAUNCH="256 64 512" \
  QUERY_SCRIPT=$S/repro-qwen38-fp8-mtp2-phantom-first-token.py SPECULATIVE_CONFIG='{"method":"qwen3_next_mtp","num_speculative_tokens":2}' \
  IMAGE_OVERRIDE=neural-download/vllm-openai-xpu:qwen38-fp8-mtp2-zero-mamba-pages-r180 IMAGE_ID_OVERRIDE=sha256:d343727316453d7f51fe1662e409090d63d5efcab08215aa6c93b3c30bddfbca \
  ROOT=$out/qwen38-fp8-r156-mtp2-zero-mamba-pages-20260903-r180 bash $S/run-20260902-qwen38-fp8-triton-rmsnorm-r152.sh
