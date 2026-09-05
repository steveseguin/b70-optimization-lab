#!/usr/bin/env bash
# R223 (2026-09-05): depth-1 strict pairs (vs the R222 depth-4 campaign MTP0 oracle) and ladders for TP2 and TP1 on the R221 image; the R222 chain ran its "full" stage at depth 4. Arg 1: pid to wait for.
# (VLLM_XPU_W4A16_DETERMINISM_PAD=0): the fixed-K kernel is run-to-run and batch invariant by itself.
# NOTE: the 2026-09-05 11:21 run of this chain had `DEPTH=1 env ...` on one line, so ${DEPTH:-4} expanded before the
# assignment and the 'depth-1 full' roots (tp*-mtp1-full) actually ran at DEPTH 4; R223 adds depth 1. Fixed here.
# Reads IMAGE/IMAGE_ID from /mnt/fast-ai/bench-results/r221-image.env (written by the R221 rebuild). Arg 1: pid to wait for.
set -uo pipefail
out=/mnt/fast-ai/bench-results; S=/home/steve/b70-optimization-lab/experiments/qwen38-27b-b70/scripts; R=/home/steve/b70-optimization-lab/repro
[[ -n "${1:-}" ]] && while kill -0 "$1" 2>/dev/null; do sleep 30; done
source $out/r221-image.env; [[ -n "${IMAGE:-}" && -n "${IMAGE_ID:-}" ]] || { echo "no r221 image env"; exit 2; }
for TP in 2 1; do  # R223: depth 1 only, vs the R222 oracle
  if [[ $TP == 1 ]]; then tpenv=(TENSOR_PARALLEL_SIZE=1 XPU_DEVICE_MASK=0 GPU_MEMORY_UTILIZATION=0.96); else tpenv=(); fi
  oracle=$out/qwen38-int4-fixed-k-tp${TP}-mtp1-full-20260905-r222
  :
  for DEPTH in 1; do
    STRICT_MTP1_ONLY=1 ORACLE_ROOT=$oracle env "${tpenv[@]}" XPU_EXTENSION_SHA256_OVERRIDE=${XPU_EXTENSION_SHA256} VLLM_XPU_DRAFT_LM_HEAD_INT4=0 VLLM_XPU_W4A16_DETERMINISM_PAD=0 VLLM_XPU_W4A16_DETERMINISM_PAD_HIGH=0 MODEL_DIR=/mnt/fast-ai/llm-models/qwen3.8-27b-int4-autoround-gptq-relabel MODEL_MANIFEST=$R/qwen38-27b-autoround-int4-b70/manifests/model-gptq-relabel-r212.json QUANTIZATION=${QUANTIZATION:-gptq} VLLM_XPU_FP8_BLOCK_W8A16=0   XPU_OPS_SHA256_OVERRIDE=6a7761930cd8b9e3f67902648ba5aaaf708567cebf70fcedda595d698f26b064 LAYERNORM_SHA256_OVERRIDE=50cf5f4f9c72f679e4318cd3e3e021a844f59ac188a891d9a4f9638188f4bce8 GEMMA_TRITON=0 RMSNORM_TRITON=0 GDN_SPLIT_MIXED=1   COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE","cudagraph_capture_sizes":[1],"max_cudagraph_capture_size":1,"splitting_ops":[],"inductor_compile_config":{"combo_kernels":false,"benchmark_combo_kernel":false,"deterministic":true,"triton.autotune_pointwise":false,"benchmark_epilogue_fusion":false}}' IMAGE_OVERRIDE=${IMAGE} IMAGE_ID_OVERRIDE=${IMAGE_ID}   SPECULATIVE_CONFIG="{\"method\":\"qwen3_next_mtp\",\"num_speculative_tokens\":${DEPTH:-4}}" ROOT=$out/qwen38-int4-fixed-k-tp${TP}-mtp${DEPTH}-strict-20260905-r223 bash $S/run-20260902-qwen38-fp8-triton-rmsnorm-r152.sh
    LADDERS_ONLY=1 env "${tpenv[@]}" XPU_EXTENSION_SHA256_OVERRIDE=${XPU_EXTENSION_SHA256} VLLM_XPU_DRAFT_LM_HEAD_INT4=0 VLLM_XPU_W4A16_DETERMINISM_PAD=0 VLLM_XPU_W4A16_DETERMINISM_PAD_HIGH=0 MODEL_DIR=/mnt/fast-ai/llm-models/qwen3.8-27b-int4-autoround-gptq-relabel MODEL_MANIFEST=$R/qwen38-27b-autoround-int4-b70/manifests/model-gptq-relabel-r212.json QUANTIZATION=${QUANTIZATION:-gptq} VLLM_XPU_FP8_BLOCK_W8A16=0   XPU_OPS_SHA256_OVERRIDE=6a7761930cd8b9e3f67902648ba5aaaf708567cebf70fcedda595d698f26b064 LAYERNORM_SHA256_OVERRIDE=50cf5f4f9c72f679e4318cd3e3e021a844f59ac188a891d9a4f9638188f4bce8 GEMMA_TRITON=0 RMSNORM_TRITON=0 GDN_SPLIT_MIXED=1   COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE","cudagraph_capture_sizes":[1],"max_cudagraph_capture_size":1,"splitting_ops":[],"inductor_compile_config":{"combo_kernels":false,"benchmark_combo_kernel":false,"deterministic":true,"triton.autotune_pointwise":false,"benchmark_epilogue_fusion":false}}' IMAGE_OVERRIDE=${IMAGE} IMAGE_ID_OVERRIDE=${IMAGE_ID}   SPECULATIVE_CONFIG="{\"method\":\"qwen3_next_mtp\",\"num_speculative_tokens\":${DEPTH:-4}}" ROOT=$out/qwen38-int4-fixed-k-tp${TP}-mtp${DEPTH}-ladders-20260905-r223 bash $S/run-20260902-qwen38-fp8-triton-rmsnorm-r152.sh
  done
done
