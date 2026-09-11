#!/usr/bin/env bash
# R295-R298 (2026-09-11): the class-consistent FP16 linear (R293 overlay on the R276 image) on the published
# 27B INT4 configuration. Background: experiments/qwen35-4b-b70/notes/2026-09-11-r293-class-consistent-fp16-linear-on-the-server.md.
# The R224 op runs every unquantized FP16 linear (lm_head 248320x5120 = 2.5 GB fp16, mtp.fc) in 32-row pieces and
# re-reads the weight per piece; on the 4B and 9B that was 25-56% of throughput above 32 rows and R293 removed it
# losslessly. On this lane depth 4 puts five rows per sequence into every decode step, so c8 is already 40 rows.
#
#   R295  TP2 depth 4, the served configuration (R276 + sizes to 320 + INT4 draft head), FULL run: G1 (fresh MTP0
#         pair), G2/G3 (depth-4 pair against its own MTP0 - the stored eager R239 oracle is a different rounding
#         class under R293 and must not be the gate), probe, then two-pass c1-c64 ladders on both profiles.
#   R296  TP2 depth 4 big-admission ladders (mns 256, mbt 4096, mml 512; rungs 32-256): the many-user ceiling
#         that R284/R290 measured at ~1085 tok/s MTP0 under R224.
#   R297  TP2 no-speculation stagger recipe: LADDERS_ONLY c64, ten passes, --launch-stagger-ms 5 (never on the 27B).
#   R298  TP1 depth 4 FULL run (the published TP1 rows: 56.9 tok/s depth 4 with graphs).
set -uo pipefail
out=/mnt/fast-ai/bench-results; S=/home/steve/b70-optimization-lab/experiments/qwen38-27b-b70/scripts; R=/home/steve/b70-optimization-lab/repro
wrap=$out/qwen38-int4-classpad-20260911-wrapper.log
log() { printf '[27b-classpad %s] %s\n' "$(date '+%m-%d %H:%M:%S')" "$*" | tee -a "$wrap"; }
echo $$ >"$out/qwen38-int4-classpad-20260911.pid"
source $out/final-int4-config.env
IMAGE=neural-download/vllm-openai-xpu:qwen38-int4-fp16-linear-classpad-cheapest-r293
IMAGE_ID=sha256:40d46730c9a24f9396cc67c0e5578dd80d11dfae7a4d23a55f97620140a0b3e6
XPU_OPS_SHA256=6ee6b8db18759873246aca28e85ca6d2ba177eb08bfd3b9b0f0feea168cee9b3
[[ "$(docker image inspect "$IMAGE" --format '{{.Id}}')" == "$IMAGE_ID" ]] || { log "image id mismatch"; exit 1; }
CC='{"cudagraph_mode":"FULL_DECODE_ONLY","cudagraph_capture_sizes":[1,2,3,4,5,6,8,10,15,16,20,25,30,32,40,50,60,64,80,100,120,160,200,240,320],"max_cudagraph_capture_size":320,"splitting_ops":[],"inductor_compile_config":{"combo_kernels":false,"benchmark_combo_kernel":false,"deterministic":true,"split_reductions":false,"triton.autotune_pointwise":false,"benchmark_epilogue_fusion":false}}'
wait_free() { while docker ps --format '{{.Names}}' | grep -qE 'qwen3[58]'; do sleep 30; done; sleep 20; while docker ps --format '{{.Names}}' | grep -qE 'qwen3[58]'; do sleep 30; done; }
verify_classpad() {
  local root=$1 d n=0 ok=1
  for d in "$root"/*/; do
    [[ -e "${d}server.log" ]] || continue; n=$((n+1))
    grep -q 'R291 classpad census.*verdict=classpad' "${d}server.log" || { log "$(basename "$root")/$(basename "$d"): no classpad census line"; ok=0; }
  done
  [[ $n -gt 0 && $ok == 1 ]] && log "$(basename "$root"): classpad verified in $n server(s): $(grep -ho 'R291 classpad census shape=[0-9x]* .*verdict=[a-z0-9-]*' "$root"/*/server.log | sort -u | head -4 | tr '\n' ';')"
  [[ $n -gt 0 && $ok == 1 ]]
}
arm() {  # label, TP, DEPTH, ROOT suffix, then extra env
  local run=$1 tp=$2 depth=$3 root=$4; shift 4
  [[ -e "$root/campaign-start.txt" || -e "$root/campaign.log" ]] && { log "$run: root already used, skipping"; return 0; }
  local tpenv=(); [[ "$tp" == 1 ]] && tpenv=(TENSOR_PARALLEL_SIZE=1 XPU_DEVICE_MASK=0 GPU_MEMORY_UTILIZATION=0.96)
  wait_free
  log "$run: starting -> $root"
  env "${tpenv[@]}" "$@" XPU_EXTENSION_SHA256_OVERRIDE=${XPU_EXTENSION_SHA256} VLLM_XPU_FA_SERIAL_SPEC_DECODE=1 VLLM_BATCH_INVARIANT=1 VLLM_XPU_DRAFT_LM_HEAD_INT4=1 \
    VLLM_XPU_W4A16_DETERMINISM_PAD=0 VLLM_XPU_W4A16_DETERMINISM_PAD_HIGH=0 VLLM_XPU_FP16_LINEAR_CLASSPAD=1 \
    MODEL_DIR=/mnt/fast-ai/llm-models/qwen3.8-27b-int4-autoround-gptq-relabel MODEL_MANIFEST=$R/qwen38-27b-autoround-int4-b70/manifests/model-gptq-relabel-r212.json \
    QUANTIZATION=gptq VLLM_XPU_FP8_BLOCK_W8A16=0 XPU_OPS_SHA256_OVERRIDE=${XPU_OPS_SHA256} VLLM_XPU_GDN_SPEC_GROUP=${GDN_SPEC_GROUP:-16} VLLM_XPU_GDN_PREFILL_GROUP=${GDN_PREFILL_GROUP:-1} \
    LAYERNORM_SHA256_OVERRIDE=50cf5f4f9c72f679e4318cd3e3e021a844f59ac188a891d9a4f9638188f4bce8 GEMMA_TRITON=0 RMSNORM_TRITON=0 GDN_SPLIT_MIXED=1 XPU_GRAPH=1 \
    COMPILATION_CONFIG="$CC" IMAGE_OVERRIDE=$IMAGE IMAGE_ID_OVERRIDE=$IMAGE_ID \
    SPECULATIVE_CONFIG="{\"method\":\"qwen3_next_mtp\",\"num_speculative_tokens\":${depth}}" ROOT=$root \
    bash $S/run-20260902-qwen38-fp8-triton-rmsnorm-r152.sh >>"$wrap" 2>&1
  log "$run: engine exit $?"
  verify_classpad "$root" || { echo "knob not applied in $run" >"$out/qwen38-int4-classpad-20260911-STOPPED"; return 1; }
  grep -qiE 'not in normal state|fault signature|did not become healthy' "$root/ABORTED" 2>/dev/null && { log "$run: HARDWARE abort -> stopping"; echo "stopped after $run" >"$out/qwen38-int4-classpad-20260911-STOPPED"; return 1; }
  return 0
}
arm r295 2 4 $out/qwen38-int4-classpad-tp2-mtp4-full-20260911-r295 LADDER_REPEATS=2 || exit 1
arm r296 2 4 $out/qwen38-int4-classpad-tp2-mtp4-bigadmission-20260911-r296 LADDERS_ONLY=1 LADDER_REPEATS=2 LADDER_CONCURRENCY=32,64,128,192,256 LADDER_MML=512 LADDER_MNS=256 LADDER_MBT=4096 || exit 1
arm r297 2 4 $out/qwen38-int4-classpad-tp2-stagger-20260911-r297 LADDERS_ONLY=1 LADDER_REPEATS=10 LADDER_CONCURRENCY=64 LADDER_EXTRA_ARGS="--launch-stagger-ms 5" || exit 1
arm r298 1 4 $out/qwen38-int4-classpad-tp1-mtp4-full-20260911-r298 LADDER_REPEATS=2 || exit 1
log "=== 27B classpad chain complete ==="; echo done >"$out/qwen38-int4-classpad-20260911-DONE"
