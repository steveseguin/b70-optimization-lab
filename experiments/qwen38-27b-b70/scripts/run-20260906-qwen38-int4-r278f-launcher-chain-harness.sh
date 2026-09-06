#!/usr/bin/env bash
# R278f (2026-09-06): the campaign runner's launcher chain (r62 -> strict -> mtp1 launcher, same env as the R277/R279 wrappers)
# started directly from a script without the runner's preflight, then the ladder harness c16/c32 x2. Bisects the 2x c32
# step-time difference between runner-launched (235 ms/step) and script-launched (118 ms/step) servers.
set -uo pipefail
while docker ps --format "{{.Names}}" | grep -q qwen38; do sleep 30; done
out=/mnt/fast-ai/bench-results; S=/home/steve/b70-optimization-lab/experiments/qwen38-27b-b70/scripts; R=/home/steve/b70-optimization-lab/repro
source $out/final-int4-config.env; IMAGE=neural-download/vllm-openai-xpu:qwen38-int4-draft-int4-head-r256; IMAGE_ID=sha256:f7696bcaefab1bc1c93e12cbde630b6e81bed8e00e41154ca2198e246c35dea3
TP=2; tpenv=(); DEPTH=4; RUN=${RUN:-r278f5}; root=$out/qwen38-int4-c32-request-shape-ab-20260906-${RUN}-mtp4; mkdir -p $root/ladder $root/ladder-cache; port=18134
log() { echo "[$RUN $(date +%T)] $*" | tee -a "$root/campaign.log"; }
LADDERS_ONLY=1 LADDER_REPEATS=${LADDER_REPEATS:-2} LADDER_CONCURRENCY=${LADDER_CONCURRENCY:-1,2,4,8,16,32,64} XPU_GRAPH=1 env "${tpenv[@]}" XPU_EXTENSION_SHA256_OVERRIDE=${XPU_EXTENSION_SHA256} VLLM_XPU_FA_SERIAL_SPEC_DECODE=1 VLLM_BATCH_INVARIANT=1 VLLM_XPU_DRAFT_LM_HEAD_INT4=1 VLLM_XPU_W4A16_DETERMINISM_PAD=0 VLLM_XPU_W4A16_DETERMINISM_PAD_HIGH=0 MODEL_DIR=/mnt/fast-ai/llm-models/qwen3.8-27b-int4-autoround-gptq-relabel MODEL_MANIFEST=$R/qwen38-27b-autoround-int4-b70/manifests/model-gptq-relabel-r212.json QUANTIZATION=${QUANTIZATION:-gptq} VLLM_XPU_FP8_BLOCK_W8A16=0   XPU_OPS_SHA256_OVERRIDE=${XPU_OPS_SHA256} VLLM_XPU_GDN_SPEC_GROUP=${SPEC_GROUP_OVERRIDE:-${GDN_SPEC_GROUP:-16}} VLLM_XPU_GDN_PREFILL_GROUP=${GDN_PREFILL_GROUP:-1} LAYERNORM_SHA256_OVERRIDE=50cf5f4f9c72f679e4318cd3e3e021a844f59ac188a891d9a4f9638188f4bce8 GEMMA_TRITON=0 RMSNORM_TRITON=0 GDN_SPLIT_MIXED=1   COMPILATION_CONFIG='{"cudagraph_mode":"FULL_DECODE_ONLY","cudagraph_capture_sizes":[1,2,3,4,5,6,8,10,15,16,20,25,30,32,40,50,60,64,80,100,120,160,200,240,320],"max_cudagraph_capture_size":320,"splitting_ops":[],"inductor_compile_config":{"combo_kernels":false,"benchmark_combo_kernel":false,"deterministic":true,"split_reductions":false,"triton.autotune_pointwise":false,"benchmark_epilogue_fusion":false}}' IMAGE_OVERRIDE=${IMAGE} IMAGE_ID_OVERRIDE=${IMAGE_ID}   SPECULATIVE_CONFIG="{\"method\":\"qwen3_next_mtp\",\"num_speculative_tokens\":${DEPTH:-4}}" VLLM_XPU_ENABLE_XPU_GRAPH=1 VLLM_XPU_GDN_SPLIT_MIXED=${SPLIT_MIXED:-1} IMAGE="$IMAGE" EXPECTED_IMAGE_ID="$IMAGE_ID" EXPECTED_XPU_EXTENSION_SHA256="$XPU_EXTENSION_SHA256" EXPECTED_XPU_OPS_SHA256="$XPU_OPS_SHA256" EXPECTED_LAYERNORM_SHA256=50cf5f4f9c72f679e4318cd3e3e021a844f59ac188a891d9a4f9638188f4bce8 EXPECTED_XPU_COMMUNICATOR_SHA256= VLLM_CACHE_DIR="$root/ladder-cache" CONTAINER_NAME=qwen38-int4-${RUN}-ladder PORT=$port SERVED_MODEL_NAME=${RUN}-ladder MAX_MODEL_LEN=256 MAX_NUM_SEQS=64 MAX_NUM_BATCHED_TOKENS=512 \
  "$S/run-20260901-qwen38-fp8-mtp1-draft-int4-r62-server.sh" > "$root/ladder/server.log" 2>&1 &
log "launched via the r62 launcher chain"
deadline=$(( $(date +%s) + 2700 )); ok=0
while (( $(date +%s) < deadline )); do curl -fsS "http://127.0.0.1:$port/health" >/dev/null 2>&1 && { ok=1; break; }; sleep 15; done
if (( ok )); then
  log "healthy"; docker inspect qwen38-int4-${RUN}-ladder > "$root/ladder/container-inspect.json" 2>/dev/null
  python3 /home/steve/b70-optimization-lab/scripts/bench-openai-concurrency-oracle.py --base-url "http://127.0.0.1:$port" --model "${RUN}-ladder" --api-mode completions \
    --suite /home/steve/b70-optimization-lab/experiments/qwen38-27b-b70/data/2026-08-25-qwen38-q4km-tp2-http-smallctx-suite.json --concurrency 16,32 --repeats 2 --max-tokens 128 \
    --seed 42 --timeout 600 --request-extra-json '{"ignore_eos":true,"temperature":0}' --return-token-ids --require-output-identity \
    --out "$root/ladder/ladder.json" > "$root/ladder/ladder.stdout" 2>&1; log "harness exit $?"
  python3 $S/summarize-int4-ladders-repeats.py "$root" 2>&1 | tee -a "$root/campaign.log"
else log "ABORT: server did not become healthy"; fi
docker stop -t 120 qwen38-int4-${RUN}-ladder >/dev/null 2>&1 || true
log "campaign complete"
