#!/usr/bin/env bash
# R176 rerun (2026-09-03 17:5x): the first post-reboot attempt aborted on IMAGE CONTRACT FAIL because the chain
# passed the R156 _xpu_ops.py hash; the probe image carries its own patched _xpu_ops.py (4a996f86...). Waits for the
# R178/R179 chain (pid given as $1) to exit, then runs the same R176 probe with the correct hash.
set -uo pipefail
out=/mnt/fast-ai/bench-results; S=/home/steve/b70-optimization-lab/experiments/qwen38-27b-b70/scripts
while kill -0 "${1:?chain pid}" 2>/dev/null; do sleep 30; done
root=$out/qwen38-fp8-r156-mtp2-phantom-state-slot-20260903-r176
[[ -f $root/ABORTED ]] && mv "$root" "$root-aborted-contract-1742"
env XPU_OPS_SHA256_OVERRIDE=4a996f86f560e22de424b86af1f5f5ab5559fd7718011dd520100d662ce18cd1 LAYERNORM_SHA256_OVERRIDE=50cf5f4f9c72f679e4318cd3e3e021a844f59ac188a891d9a4f9638188f4bce8 \
  GEMMA_TRITON=0 RMSNORM_TRITON=0 GDN_SPLIT_MIXED=1 QUERY_ONLY=1 QUERY_KINDS=mtp1 QUERY_LAUNCH="256 64 512" \
  QUERY_SCRIPT=$S/repro-qwen38-fp8-mtp2-phantom-first-token.py SPECULATIVE_CONFIG='{"method":"qwen3_next_mtp","num_speculative_tokens":2}' \
  IMAGE_OVERRIDE=neural-download/vllm-openai-xpu:qwen38-fp8-mtp2-state-slot-probe-r176 IMAGE_ID_OVERRIDE=sha256:85c287a73cff8ed0cdebd1f93777ba88b2bb26b89b8a753b96fb3bcc52c08616 \
  ROOT=$root bash $S/run-20260902-qwen38-fp8-triton-rmsnorm-r152.sh
