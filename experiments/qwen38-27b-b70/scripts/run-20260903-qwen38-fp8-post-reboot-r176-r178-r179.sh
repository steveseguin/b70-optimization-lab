#!/usr/bin/env bash
# Post-reboot chain (2026-09-03): R176 state-slot probe, R178 zero-GDN-pages fix candidate (depth-2 64-prompt pass, async on),
# then R179 = the MTP0 ladder with --no-async-scheduling that R175 lost to the GPU fault. Run from the repo root after a clean boot.
set -uo pipefail
out=/mnt/fast-ai/bench-results; S=/home/steve/b70-optimization-lab/experiments/qwen38-27b-b70/scripts
bash "$S/run-20260903-qwen38-fp8-r176-r178-chain.sh"
env XPU_OPS_SHA256_OVERRIDE=6a7761930cd8b9e3f67902648ba5aaaf708567cebf70fcedda595d698f26b064 LAYERNORM_SHA256_OVERRIDE=50cf5f4f9c72f679e4318cd3e3e021a844f59ac188a891d9a4f9638188f4bce8 \
  GEMMA_TRITON=0 RMSNORM_TRITON=0 GDN_SPLIT_MIXED=1 IMAGE_OVERRIDE=neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-gdn-split-mixed-r156 \
  IMAGE_ID_OVERRIDE=sha256:173660ec18c6e98a14b9a4f573922abe9d3414999056f07ab5c3c14b55d6ceb0 EXTRA_SERVE_ARGS=--no-async-scheduling \
  ROOT=$out/qwen38-fp8-r156-mtp0-async-off-ladder-20260903-r179 LADDERS_ONLY=1 bash "$S/run-20260902-qwen38-fp8-triton-rmsnorm-r152.sh"
