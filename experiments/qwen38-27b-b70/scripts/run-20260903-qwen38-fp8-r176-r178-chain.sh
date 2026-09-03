#!/usr/bin/env bash
# Wait for the R174/R175 chain, then R176 (state-slot probe, 64-pass) and R178 (fix candidate, 64-pass), depth 2, async on.
set -uo pipefail
out=/mnt/fast-ai/bench-results; S=/home/steve/b70-optimization-lab/experiments/qwen38-27b-b70/scripts
while ! grep -q 'campaign complete' $out/qwen38-fp8-r156-mtp1-async-off-ladder-20260903-r175/campaign.log 2>/dev/null; do sleep 10; done
common=(XPU_OPS_SHA256_OVERRIDE=6a7761930cd8b9e3f67902648ba5aaaf708567cebf70fcedda595d698f26b064 LAYERNORM_SHA256_OVERRIDE=50cf5f4f9c72f679e4318cd3e3e021a844f59ac188a891d9a4f9638188f4bce8 GEMMA_TRITON=0 RMSNORM_TRITON=0 GDN_SPLIT_MIXED=1 QUERY_ONLY=1 QUERY_KINDS=mtp1 QUERY_LAUNCH="256 64 512" QUERY_SCRIPT=$S/repro-qwen38-fp8-mtp2-phantom-first-token.py SPECULATIVE_CONFIG='{"method":"qwen3_next_mtp","num_speculative_tokens":2}')
env "${common[@]}" IMAGE_OVERRIDE=neural-download/vllm-openai-xpu:qwen38-fp8-mtp2-state-slot-probe-r176 IMAGE_ID_OVERRIDE=sha256:85c287a73cff8ed0cdebd1f93777ba88b2bb26b89b8a753b96fb3bcc52c08616 ROOT=$out/qwen38-fp8-r156-mtp2-phantom-state-slot-20260903-r176 bash $S/run-20260902-qwen38-fp8-triton-rmsnorm-r152.sh
env "${common[@]}" IMAGE_OVERRIDE=neural-download/vllm-openai-xpu:qwen38-fp8-mtp2-zero-mamba-pages-r178 IMAGE_ID_OVERRIDE=sha256:40d3645a6f97b29dbfaefe91330f32137a699adeebed3104839ae3539637f0ac ROOT=$out/qwen38-fp8-r156-mtp2-zero-mamba-pages-20260903-r178 bash $S/run-20260902-qwen38-fp8-triton-rmsnorm-r152.sh
