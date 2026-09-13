#!/usr/bin/env bash
# 27B INT4 one-card profile on R304 (matrix row R298 on R293: TP1 depth 4 73.19/73.25, MTP0 32.58/32.50): strict pair +
# two-pass ladders, real contract. Runs after the FP8 short-prompt chain; one card.
set -uo pipefail
out=/mnt/fast-ai/bench-results; S=/home/steve/b70-optimization-lab/experiments/qwen38-27b-b70/scripts; R=/home/steve/b70-optimization-lab/repro
wrap=$out/qwen38-int4-rebase-v0290-tp1-20260913-wrapper.log
log() { printf '[27b-tp1 %s] %s\n' "$(date '+%m-%d %H:%M:%S')" "$*" | tee -a "$wrap"; }
until [[ -e /mnt/fast-ai/bench-results/rebase-v0290-20260912/alias-fp8/DONE ]]; do sleep 30; done
rebase_image=neural-download/vllm-openai-xpu:qwen38-int4-v0290-rebase-r304
source $out/final-int4-config.env
IMAGE=$rebase_image; IMAGE_ID=$(docker image inspect "$IMAGE" --format '{{.Id}}')
export SKIP_IMAGE_CONTRACT=0 EXPECTED_KERNEL_HEAD=6d92b1bfbf32767ecda8e819613eb151e70030ad VLLM_USE_V2_MODEL_RUNNER=0
CC='{"cudagraph_mode":"FULL_DECODE_ONLY","cudagraph_capture_sizes":[1,2,3,4,5,6,8,10,15,16,20,25,30,32,40,50,60,64,80,100,120,160,200,240,320],"max_cudagraph_capture_size":320,"splitting_ops":[],"inductor_compile_config":{"combo_kernels":false,"benchmark_combo_kernel":false,"deterministic":true,"split_reductions":false,"triton.autotune_pointwise":false,"benchmark_epilogue_fusion":false}}'
while docker ps --format '{{.Names}}' | grep -qE 'qwen3[58]|rebase-|upstream-'; do sleep 30; done; sleep 20
root=$out/qwen38-int4-rebase-v0290-tp1-r304-20260913
[[ -e "$root/campaign.log" ]] && { log "root used"; exit 0; }
log "starting -> $root"
env LADDER_REPEATS=2 TENSOR_PARALLEL_SIZE=1 XPU_DEVICE_MASK=0 GPU_MEMORY_UTILIZATION=0.96 XPU_EXTENSION_SHA256_OVERRIDE=bbce7295fb8a58bad456675cfac7cdf3d1e29fe7a9dd5c0970741b130616c932 VLLM_XPU_FA_SERIAL_SPEC_DECODE=1 VLLM_BATCH_INVARIANT=1 VLLM_XPU_DRAFT_LM_HEAD_INT4=1 \
  VLLM_XPU_W4A16_DETERMINISM_PAD=0 VLLM_XPU_W4A16_DETERMINISM_PAD_HIGH=0 VLLM_XPU_FP16_LINEAR_CLASSPAD=0 VLLM_XPU_DRAFT_LM_HEAD_SHORTLIST=/opt/draft-shortlists/shortlist-u-v1all-v2top65k.txt \
  MODEL_DIR=/mnt/fast-ai/llm-models/qwen3.8-27b-int4-autoround-gptq-relabel MODEL_MANIFEST=$R/qwen38-27b-autoround-int4-b70/manifests/model-gptq-relabel-r212.json \
  QUANTIZATION=gptq VLLM_XPU_FP8_BLOCK_W8A16=0 XPU_OPS_SHA256_OVERRIDE=6ee6b8db18759873246aca28e85ca6d2ba177eb08bfd3b9b0f0feea168cee9b3 VLLM_XPU_GDN_SPEC_GROUP=16 VLLM_XPU_GDN_PREFILL_GROUP=1 \
  LAYERNORM_SHA256_OVERRIDE=3f949e537ccc52744d7eba52ed2034b20ee3fbaeaabbfab4e672f1dc9767602c GEMMA_TRITON=0 RMSNORM_TRITON=0 GDN_SPLIT_MIXED=1 XPU_GRAPH=1 \
  COMPILATION_CONFIG="$CC" IMAGE_OVERRIDE=$IMAGE IMAGE_ID_OVERRIDE=$IMAGE_ID SPECULATIVE_CONFIG='{"method":"qwen3_next_mtp","num_speculative_tokens":4}' ROOT=$root \
  bash $S/run-20260902-qwen38-fp8-triton-rmsnorm-r152.sh >>"$wrap" 2>&1
log "engine exit $?"; grep -E 'G[123] |median_tok_s' "$wrap" | tail -6 | sed 's/^/    /'
log "=== 27B TP1 on R304 complete ==="; echo done > $out/qwen38-int4-rebase-v0290-tp1-20260913-DONE
