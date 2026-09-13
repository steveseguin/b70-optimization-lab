#!/usr/bin/env bash
# Rebase onto vLLM v0.29.0 (2026-09-12 evening): 27B INT4 lane strict pair on the stage-B1 image (TP2, depth 4, draft INT4
# head + 67k shortlist, served configuration as run-20260912-qwen38-int4-r299-draft-shortlist-chain.sh), queued behind the
# single-card 4B chains (identity DONE file; first attempt rb1 failed on the R62 server script hardcoding the kernel head, fixed). Image identities are the stage-B1 file digests; the recipe contract is skipped (loud) because the image
# is a candidate, not a published runtime; V1 model runner pinned (v0.29.0 defaults XPU to V2, which has no draft INT4 head).
set -uo pipefail
out=/mnt/fast-ai/bench-results; S=/home/steve/b70-optimization-lab/experiments/qwen38-27b-b70/scripts; R=/home/steve/b70-optimization-lab/repro
wrap=$out/qwen38-int4-rebase-v0290-20260912-wrapper.log
log() { printf '[27b-rebase %s] %s\n' "$(date '+%m-%d %H:%M:%S')" "$*" | tee -a "$wrap"; }
until [[ -e $out/rebase-v0290-identity2-20260912-DONE ]]; do sleep 30; done
source $out/final-int4-config.env
IMAGE=${IMAGE:-rebase/vllm-xpu:v0290-stage-b1}; IMAGE_ID=$(docker image inspect "$IMAGE" --format '{{.Id}}')
export SKIP_IMAGE_CONTRACT=${SKIP_IMAGE_CONTRACT:-1} EXPECTED_KERNEL_HEAD=6d92b1bfbf32767ecda8e819613eb151e70030ad VLLM_USE_V2_MODEL_RUNNER=0
CC='{"cudagraph_mode":"FULL_DECODE_ONLY","cudagraph_capture_sizes":[1,2,3,4,5,6,8,10,15,16,20,25,30,32,40,50,60,64,80,100,120,160,200,240,320],"max_cudagraph_capture_size":320,"splitting_ops":[],"inductor_compile_config":{"combo_kernels":false,"benchmark_combo_kernel":false,"deterministic":true,"split_reductions":false,"triton.autotune_pointwise":false,"benchmark_epilogue_fusion":false}}'
wait_free() { while docker ps --format '{{.Names}}' | grep -qE 'qwen3[58]|rebase-'; do sleep 30; done; sleep 20; }
root=$out/qwen38-int4-rebase-v0290-${RB:-rb2}-20260912
[[ -e "$root/campaign.log" ]] && { log "${RB:-rb2}: root already used"; exit 0; }
wait_free; log "${RB:-rb2}: starting -> $root"
env XPU_EXTENSION_SHA256_OVERRIDE=bbce7295fb8a58bad456675cfac7cdf3d1e29fe7a9dd5c0970741b130616c932 VLLM_XPU_FA_SERIAL_SPEC_DECODE=1 VLLM_BATCH_INVARIANT=1 VLLM_XPU_DRAFT_LM_HEAD_INT4=1 \
  VLLM_XPU_W4A16_DETERMINISM_PAD=0 VLLM_XPU_W4A16_DETERMINISM_PAD_HIGH=0 VLLM_XPU_FP16_LINEAR_CLASSPAD=0 VLLM_XPU_DRAFT_LM_HEAD_SHORTLIST=/opt/draft-shortlists/shortlist-u-v1all-v2top65k.txt \
  MODEL_DIR=/mnt/fast-ai/llm-models/qwen3.8-27b-int4-autoround-gptq-relabel MODEL_MANIFEST=$R/qwen38-27b-autoround-int4-b70/manifests/model-gptq-relabel-r212.json \
  QUANTIZATION=gptq VLLM_XPU_FP8_BLOCK_W8A16=0 XPU_OPS_SHA256_OVERRIDE=6ee6b8db18759873246aca28e85ca6d2ba177eb08bfd3b9b0f0feea168cee9b3 VLLM_XPU_GDN_SPEC_GROUP=16 VLLM_XPU_GDN_PREFILL_GROUP=1 \
  LAYERNORM_SHA256_OVERRIDE=3f949e537ccc52744d7eba52ed2034b20ee3fbaeaabbfab4e672f1dc9767602c GEMMA_TRITON=0 RMSNORM_TRITON=0 GDN_SPLIT_MIXED=1 XPU_GRAPH=1 \
  COMPILATION_CONFIG="$CC" IMAGE_OVERRIDE=$IMAGE IMAGE_ID_OVERRIDE=$IMAGE_ID SPECULATIVE_CONFIG='{"method":"qwen3_next_mtp","num_speculative_tokens":4}' ROOT=$root \
  bash $S/run-20260902-qwen38-fp8-triton-rmsnorm-r152.sh >>"$wrap" 2>&1
log "${RB:-rb2}: engine exit $?"
grep -q 'R294 draft shortlist' "$root/mtp1-a/server.log" 2>/dev/null && log "${RB:-rb2}: shortlist verified" || log "${RB:-rb2}: NO shortlist line"
grep -q 'Using V1 Model Runner' "$root/mtp1-a/server.log" 2>/dev/null && log "${RB:-rb2}: V1 runner verified" || log "${RB:-rb2}: V1 runner line MISSING"
log "=== 27B rebase strict complete ==="; echo done > $out/qwen38-int4-rebase-v0290-20260912-DONE
