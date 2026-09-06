#!/usr/bin/env bash
# R278g (2026-09-06): R278d plus the remaining 13 env vars only the launcher chain sets (empty trace-file paths, isolate/trace flags at 0): the last configuration difference between the slow (launcher-chain, 235 ms/step at c32) and fast (script, 118 ms/step) servers.
# (V1, INT4 head, graphs to 320, GDN spec group 64, max-num-seqs 64): 32 concurrent 128-token requests as (a) plain
# non-streaming completions, (b) streaming, (c) streaming with logprobs=1 and return_token_ids (the ladder harness shape),
# (d) plain again. Reports aggregate tok/s per shape. Waits for pid $1 and for no qwen38 container.
set -uo pipefail
while docker ps --format "{{.Names}}" | grep -q qwen38; do sleep 30; done
[[ -n "${1:-}" ]] && while kill -0 "$1" 2>/dev/null; do sleep 30; done
DEPTH=${DEPTH:-4}; RUN=${RUN:-r278g}
out=/mnt/fast-ai/bench-results/qwen38-int4-c32-request-shape-ab-20260906-${RUN}-mtp${DEPTH}; mkdir -p "$out/profile" "$out/cache"
img=${IMG:-neural-download/vllm-openai-xpu:qwen38-int4-draft-int4-head-r256}; model=/mnt/fast-ai/llm-models/qwen3.8-27b-int4-autoround-gptq-relabel; port=18138; name=qwen38-int4-${RUN}-profile
CC='{"cudagraph_mode":"FULL_DECODE_ONLY","cudagraph_capture_sizes":[1,2,3,4,5,6,8,10,15,16,20,25,30,32,40,50,60,64,80,100,120,160,200,240,320],"max_cudagraph_capture_size":320,"splitting_ops":[],"inductor_compile_config":{"combo_kernels":false,"benchmark_combo_kernel":false,"deterministic":true,"split_reductions":false,"triton.autotune_pointwise":false,"benchmark_epilogue_fusion":false}}'
spec=(); [[ "$DEPTH" == 0 ]] || spec=(--speculative-config "{\"method\":\"qwen3_next_mtp\",\"num_speculative_tokens\":${DEPTH}}")
docker run -d --rm --name "$name" --ulimit core=0 --memory 12g --memory-swap 16g --device /dev/dri:/dev/dri --group-add render --cap-add SYS_PTRACE --security-opt label=disable --ipc=host --shm-size=8g \
  -p 127.0.0.1:$port:8000 -v "$model:/model:ro" -v "$out/cache:/root/.cache/vllm" \
  -e ZE_AFFINITY_MASK=0,1 -e ONEAPI_DEVICE_SELECTOR=level_zero:0,1 -e VLLM_TARGET_DEVICE=xpu -e VLLM_WORKER_MULTIPROC_METHOD=spawn -e VLLM_XPU_ENABLE_XPU_GRAPH=1 -e VLLM_XPU_ALLREDUCE_HOST_WAIT=1 \
  -e TORCHINDUCTOR_DETERMINISTIC=1 -e VLLM_ENABLE_INDUCTOR_MAX_AUTOTUNE=0 -e VLLM_ENABLE_INDUCTOR_COORDINATE_DESCENT_TUNING=0 -e PYTHONHASHSEED=0 \
  -e VLLM_XPU_FP8_BLOCK_W8A16=1 -e VLLM_XPU_W4A16_DETERMINISM_PAD=0 -e VLLM_XPU_GDN_SPLIT_MIXED=1 -e VLLM_XPU_GDN_SPEC_GROUP=${SPEC_GROUP:-64} -e VLLM_XPU_GDN_PREFILL_GROUP=1 -e VLLM_XPU_GDN_SPEC_PERSISTENT_SCRATCH=1 -e VLLM_XPU_GDN_NATIVE_FALLBACK=1 \
  -e VLLM_XPU_FP16_LINEAR_ROWCHUNK=32 -e VLLM_BATCH_INVARIANT=0 -e VLLM_XPU_QWEN_GEMMA_RMSNORM_BATCH_INVARIANT=0 -e VLLM_XPU_QWEN_GEMMA_RMSNORM_PACKED_SERIAL_EXACT=1 \
  -e VLLM_XPU_DRAFT_LM_HEAD_INT4=${DRAFT_HEAD_INT4:-1} -e VLLM_USE_V2_MODEL_RUNNER=${V2:-0} -e VLLM_XPU_DRAFT_LM_HEAD_INT4_GROUP_SIZE=128 -e VLLM_XPU_DRAFT_LM_HEAD_INT4_SCALE_DTYPE=bf16 -e VLLM_XPU_DRAFT_LM_HEAD_INT4_CHUNK_ROWS=2048 \
  -e VLLM_XPU_GEMMA_RMSNORM_TRITON=0 -e VLLM_XPU_RMSNORM_TRITON=0 -e VLLM_USE_BREAKABLE_CUDAGRAPH=0 -e VLLM_XPU_COMPILE_ALLREDUCE_CUSTOM_OP=0 -e VLLM_XPU_DRAFT_LM_HEAD_INT4_APPLY_ROWS=0 -e VLLM_XPU_FA_SERIAL_SPEC_DECODE=0 -e VLLM_XPU_FA_SERIAL_SPEC_NO_CAUSAL=0 -e VLLM_XPU_FP8_PACKED_SERIAL_EXACT=0 -e VLLM_XPU_GDN_DETERMINISTIC_QKVZ_PREFILL=0 -e VLLM_XPU_GDN_NATIVE_SPEC_CONV_SERIAL_EXACT=0 -e VLLM_XPU_GDN_NATIVE_SPEC_DELTA_SERIAL_EXACT=0 -e VLLM_XPU_GDN_NATIVE_SPEC_MULTI_REQUEST_SPLIT=0 -e VLLM_XPU_GDN_NATIVE_SPEC_RECURRENT_SERIAL_EXACT=0 -e VLLM_XPU_GDN_ROW_STABLE_RMSNORM=0 -e VLLM_XPU_LM_HEAD_BATCH_INVARIANT=0 -e VLLM_XPU_LM_HEAD_BATCH_REPAIR_MARGIN=0.25 -e VLLM_XPU_LM_HEAD_BATCH_REPAIR_ROWS=0 -e VLLM_XPU_LM_HEAD_CHUNK_ROWS=0 -e VLLM_XPU_LM_HEAD_GLOBAL_BATCH_REPAIR_MARGIN=0 -e VLLM_XPU_MTP_DRAFT_EAGER=0 -e VLLM_XPU_MTP_SUPPRESS_BONUS_TOKEN=0 -e VLLM_XPU_W8A16_DECODE_PAD_ROWS=0 -e VLLM_XPU_W8A16_PAD_N_SET= -e VLLM_XPU_DECODER_BOUNDARY_TRACE_FILE= -e VLLM_XPU_GDN_ISOLATE_NORM_PREFILL_REQUESTS=0 -e VLLM_XPU_GDN_ISOLATE_OUTPUT_PREFILL_REQUESTS=0 -e VLLM_XPU_GDN_ISOLATE_PREFILL_REQUESTS=0 -e VLLM_XPU_GDN_ISOLATE_PROJECTION_PREFILL_REQUESTS=0 -e VLLM_XPU_GDN_ISOLATE_QKVZ_PREFILL_REQUESTS=0 -e VLLM_XPU_GDN_NATIVE_SPEC_EVOLVING_METADATA_TRACE=0 -e VLLM_XPU_GDN_NATIVE_SPEC_METADATA_TRACE=0 -e VLLM_XPU_GDN_PREFILL_INPUT_TRACE_FILE= -e VLLM_XPU_GDN_PREFILL_OUTPUT_TRACE_FILE= -e VLLM_XPU_GDN_PROJECTION_TRACE_FILE= -e VLLM_XPU_GDN_STATE_INPUT_TRACE_FILE= -e VLLM_XPU_ISOLATE_LAYER0_MLP_PREFILL_REQUESTS=0 ${EXTRA_ENV:-} \
  -e PYTORCH_ALLOC_CONF=expandable_segments:True -e CCL_ATL_TRANSPORT=ofi -e FI_PROVIDER=tcp -e FI_TCP_IFACE=lo -e CCL_ZE_IPC_EXCHANGE=pidfd -e CCL_SEND=direct -e CCL_RECV=direct -e CCL_TOPO_P2P_ACCESS=1 \
  -e CCL_SYCL_ALLREDUCE_SIMPLE_THRESHOLD=4294967296 -e CCL_SYCL_ALLGATHERV_SIMPLE_THRESHOLD=4294967296 -e CCL_SYCL_REDUCE_SCATTER_SIMPLE_THRESHOLD=4294967296 \
  "$img" --model /model --served-model-name "$RUN" --host 0.0.0.0 --port 8000 --tensor-parallel-size 2 --dtype float16 --quantization gptq --kv-cache-dtype auto --gpu-memory-utilization 0.95 --max-model-len ${MML:-256} --block-size 64 --max-num-seqs 64 --max-num-batched-tokens 512 --no-enable-prefix-caching --enable-prompt-tokens-details --language-model-only ${ASYNC:+--async-scheduling} "${spec[@]}" --compilation-config "$CC" >"$out/docker-run.stdout" 2>&1
log() { echo "[$RUN $(date +%T)] $*" | tee -a "$out/campaign.log"; }
log "launched depth $DEPTH"
deadline=$(( $(date +%s) + 2700 )); ok=0
while (( $(date +%s) < deadline )); do curl -fsS "http://127.0.0.1:$port/health" >/dev/null 2>&1 && { ok=1; break; }; docker ps --format '{{.Names}}' | grep -q "^$name$" || break; sleep 15; done
if (( ok )); then
  log "healthy"; docker inspect "$name" > "$out/container-inspect.json" 2>/dev/null
  suite=/home/steve/b70-optimization-lab/experiments/qwen38-27b-b70/data/2026-08-25-qwen38-q4km-tp2-http-smallctx-suite.json
  mkdir -p "$out/ladder"; log "ladder harness (runner invocation) c16,32 x2 against this server"
  python3 /home/steve/b70-optimization-lab/scripts/bench-openai-concurrency-oracle.py --base-url "http://127.0.0.1:$port" --model "$RUN" --api-mode completions \
    --suite "$suite" --concurrency 16,32 --repeats 2 --max-tokens 128 --seed 42 --timeout 600 --request-extra-json '{"ignore_eos":true,"temperature":0}' \
    --return-token-ids --require-output-identity --out "$out/ladder/ladder.json" >"$out/ladder.stdout" 2>&1; log "harness exit $?"
  python3 /home/steve/b70-optimization-lab/experiments/qwen38-27b-b70/scripts/summarize-int4-ladders-repeats.py "$out" 2>&1 | tee -a "$out/campaign.log"
else log "ABORT: server did not become healthy"; fi
docker logs "$name" >"$out/server.log" 2>&1 || true; docker stop -t 120 "$name" >/dev/null 2>&1 || true
log "campaign complete"
