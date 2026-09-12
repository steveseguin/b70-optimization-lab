#!/usr/bin/env bash
# R299-R300 (2026-09-12): the shortlisted draft-only lm_head (R294) on the 27B INT4 served configuration (TP2, depth 4,
# sizes to 320, INT4 draft head, CLASSPAD=0). The draft passes are ~6 ms of a ~27 ms single-user step here (four passes
# through a 124160x5120 INT4 shard per card); the 67k union list cuts each pass to 27% of the rows. Lossless by
# construction. R299: shortlist on, FULL run (fresh MTP0 pair, depth-4 pair against it, two-pass ladders). R300: the same
# image with no shortlist, strict only, as the in-image control (expected = R283's 112.90 / 113.00).
set -uo pipefail
out=/mnt/fast-ai/bench-results; S=/home/steve/b70-optimization-lab/experiments/qwen38-27b-b70/scripts; R=/home/steve/b70-optimization-lab/repro
wrap=$out/qwen38-int4-shortlist-20260912-wrapper.log
log() { printf '[27b-shortlist %s] %s\n' "$(date '+%m-%d %H:%M:%S')" "$*" | tee -a "$wrap"; }
until [[ -e $out/qwen35-4b-shortlist3-20260912-DONE ]]; do sleep 30; done
source $out/final-int4-config.env
IMAGE=neural-download/vllm-openai-xpu:qwen38-int4-draft-head-shortlist-r294b
IMAGE_ID=$(docker image inspect "$IMAGE" --format '{{.Id}}')
XPU_OPS_SHA256=6ee6b8db18759873246aca28e85ca6d2ba177eb08bfd3b9b0f0feea168cee9b3
CC='{"cudagraph_mode":"FULL_DECODE_ONLY","cudagraph_capture_sizes":[1,2,3,4,5,6,8,10,15,16,20,25,30,32,40,50,60,64,80,100,120,160,200,240,320],"max_cudagraph_capture_size":320,"splitting_ops":[],"inductor_compile_config":{"combo_kernels":false,"benchmark_combo_kernel":false,"deterministic":true,"split_reductions":false,"triton.autotune_pointwise":false,"benchmark_epilogue_fusion":false}}'
wait_free() { while docker ps --format '{{.Names}}' | grep -qE 'qwen3[58]'; do sleep 30; done; sleep 20; while docker ps --format '{{.Names}}' | grep -qE 'qwen3[58]'; do sleep 30; done; }
arm() {  # run, root, shortlist, extra env...
  local run=$1 root=$2 sl=$3; shift 3
  [[ -e "$root/campaign.log" ]] && { log "$run: root already used, skipping"; return 0; }
  wait_free; log "$run: starting -> $root (shortlist='$sl')"
  env "$@" XPU_EXTENSION_SHA256_OVERRIDE=${XPU_EXTENSION_SHA256} VLLM_XPU_FA_SERIAL_SPEC_DECODE=1 VLLM_BATCH_INVARIANT=1 VLLM_XPU_DRAFT_LM_HEAD_INT4=1 \
    VLLM_XPU_W4A16_DETERMINISM_PAD=0 VLLM_XPU_W4A16_DETERMINISM_PAD_HIGH=0 VLLM_XPU_FP16_LINEAR_CLASSPAD=0 VLLM_XPU_DRAFT_LM_HEAD_SHORTLIST="$sl" \
    MODEL_DIR=/mnt/fast-ai/llm-models/qwen3.8-27b-int4-autoround-gptq-relabel MODEL_MANIFEST=$R/qwen38-27b-autoround-int4-b70/manifests/model-gptq-relabel-r212.json \
    QUANTIZATION=gptq VLLM_XPU_FP8_BLOCK_W8A16=0 XPU_OPS_SHA256_OVERRIDE=${XPU_OPS_SHA256} VLLM_XPU_GDN_SPEC_GROUP=${GDN_SPEC_GROUP:-16} VLLM_XPU_GDN_PREFILL_GROUP=${GDN_PREFILL_GROUP:-1} \
    LAYERNORM_SHA256_OVERRIDE=50cf5f4f9c72f679e4318cd3e3e021a844f59ac188a891d9a4f9638188f4bce8 GEMMA_TRITON=0 RMSNORM_TRITON=0 GDN_SPLIT_MIXED=1 XPU_GRAPH=1 \
    COMPILATION_CONFIG="$CC" IMAGE_OVERRIDE=$IMAGE IMAGE_ID_OVERRIDE=$IMAGE_ID SPECULATIVE_CONFIG='{"method":"qwen3_next_mtp","num_speculative_tokens":4}' ROOT=$root \
    bash $S/run-20260902-qwen38-fp8-triton-rmsnorm-r152.sh >>"$wrap" 2>&1
  log "$run: engine exit $?"
  if [[ -n "$sl" ]]; then grep -q 'R294 draft shortlist' "$root/mtp1-a/server.log" 2>/dev/null && log "$run: shortlist verified: $(grep -ho 'R294 draft shortlist: [^,]*, [0-9]* in this shard' "$root/mtp1-a/server.log" | head -1)" || { log "$run: NO shortlist line"; echo stop >"$out/qwen38-int4-shortlist-20260912-STOPPED"; return 1; }; fi
  return 0
}
arm r299 $out/qwen38-int4-shortlist-tp2-mtp4-full-20260912-r299 /opt/draft-shortlists/shortlist-u-v1all-v2top65k.txt LADDER_REPEATS=2 || exit 1
arm r300 $out/qwen38-int4-shortlist-tp2-mtp4-control-20260912-r300 "" STRICT_MTP1_ONLY=1 ORACLE_ROOT=$out/qwen38-int4-shortlist-tp2-mtp4-full-20260912-r299 || exit 1
log "=== 27B shortlist chain complete ==="; echo done >"$out/qwen38-int4-shortlist-20260912-DONE"
