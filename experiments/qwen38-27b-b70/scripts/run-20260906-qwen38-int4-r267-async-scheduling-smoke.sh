#!/usr/bin/env bash
# R267 (2026-09-06): smoke test of vLLM async scheduling (--async-scheduling) on the INT4 headline stack (V1 runner, draft-only
# INT4 head, graphs), then the same with the V2 runner (V2=1, FP16 head). The R262 profile showed the worker idling on the
# scheduler round trip between steps; async scheduling overlaps it with execution. Timing on three 256-token completions.
set -uo pipefail
[[ -n "${1:-}" ]] && while kill -0 "$1" 2>/dev/null; do sleep 30; done
DEPTH=${DEPTH:-4}; RUN=${RUN:-r267}
out=/mnt/fast-ai/bench-results/qwen38-int4-async-sched-smoke-20260906-${RUN}-mtp${DEPTH}; mkdir -p "$out/profile" "$out/cache"
img=${IMG:-neural-download/vllm-openai-xpu:qwen38-int4-draft-int4-head-r256}; model=/mnt/fast-ai/llm-models/qwen3.8-27b-int4-autoround-gptq-relabel; port=18135; name=qwen38-int4-${RUN}-profile
CC='{"cudagraph_mode":"FULL_DECODE_ONLY","cudagraph_capture_sizes":[1,2,3,4,5,6,8],"max_cudagraph_capture_size":8,"splitting_ops":[],"inductor_compile_config":{"combo_kernels":false,"benchmark_combo_kernel":false,"deterministic":true,"split_reductions":false,"triton.autotune_pointwise":false,"benchmark_epilogue_fusion":false}}'
spec=(); [[ "$DEPTH" == 0 ]] || spec=(--speculative-config "{\"method\":\"qwen3_next_mtp\",\"num_speculative_tokens\":${DEPTH}}")
docker run -d --rm --name "$name" --ulimit core=0 --memory 12g --memory-swap 16g --device /dev/dri:/dev/dri --group-add render --cap-add SYS_PTRACE --security-opt label=disable --ipc=host --shm-size=8g \
  -p 127.0.0.1:$port:8000 -v "$model:/model:ro" -v "$out/cache:/root/.cache/vllm" \
  -e ZE_AFFINITY_MASK=0,1 -e ONEAPI_DEVICE_SELECTOR=level_zero:0,1 -e VLLM_TARGET_DEVICE=xpu -e VLLM_WORKER_MULTIPROC_METHOD=spawn -e VLLM_XPU_ENABLE_XPU_GRAPH=1 -e VLLM_XPU_ALLREDUCE_HOST_WAIT=1 \
  -e TORCHINDUCTOR_DETERMINISTIC=1 -e VLLM_ENABLE_INDUCTOR_MAX_AUTOTUNE=0 -e VLLM_ENABLE_INDUCTOR_COORDINATE_DESCENT_TUNING=0 -e PYTHONHASHSEED=0 \
  -e VLLM_XPU_FP8_BLOCK_W8A16=1 -e VLLM_XPU_W4A16_DETERMINISM_PAD=0 -e VLLM_XPU_GDN_SPLIT_MIXED=1 -e VLLM_XPU_GDN_SPEC_GROUP=16 -e VLLM_XPU_GDN_PREFILL_GROUP=1 -e VLLM_XPU_GDN_SPEC_PERSISTENT_SCRATCH=1 -e VLLM_XPU_GDN_NATIVE_FALLBACK=1 \
  -e VLLM_XPU_FP16_LINEAR_ROWCHUNK=32 -e VLLM_BATCH_INVARIANT=0 -e VLLM_XPU_QWEN_GEMMA_RMSNORM_BATCH_INVARIANT=0 -e VLLM_XPU_QWEN_GEMMA_RMSNORM_PACKED_SERIAL_EXACT=1 \
  -e VLLM_XPU_DRAFT_LM_HEAD_INT4=${DRAFT_HEAD_INT4:-1} -e VLLM_USE_V2_MODEL_RUNNER=${V2:-0} -e VLLM_XPU_DRAFT_LM_HEAD_INT4_GROUP_SIZE=128 -e VLLM_XPU_DRAFT_LM_HEAD_INT4_SCALE_DTYPE=bf16 -e VLLM_XPU_DRAFT_LM_HEAD_INT4_CHUNK_ROWS=2048 \
  -e VLLM_XPU_GEMMA_RMSNORM_TRITON=0 -e VLLM_XPU_RMSNORM_TRITON=0 \
  -e PYTORCH_ALLOC_CONF=expandable_segments:True -e CCL_ATL_TRANSPORT=ofi -e FI_PROVIDER=tcp -e FI_TCP_IFACE=lo -e CCL_ZE_IPC_EXCHANGE=pidfd -e CCL_SEND=direct -e CCL_RECV=direct -e CCL_TOPO_P2P_ACCESS=1 \
  -e CCL_SYCL_ALLREDUCE_SIMPLE_THRESHOLD=4294967296 -e CCL_SYCL_ALLGATHERV_SIMPLE_THRESHOLD=4294967296 -e CCL_SYCL_REDUCE_SCATTER_SIMPLE_THRESHOLD=4294967296 \
  "$img" --model /model --served-model-name "$RUN" --host 0.0.0.0 --port 8000 --tensor-parallel-size 2 --dtype float16 --quantization gptq --kv-cache-dtype auto --gpu-memory-utilization 0.95 --max-model-len 1024 --block-size 64 --max-num-seqs 1 --max-num-batched-tokens 1024 --no-enable-prefix-caching --enable-prompt-tokens-details --language-model-only ${ASYNC:+--async-scheduling} "${spec[@]}" --compilation-config "$CC" >"$out/docker-run.stdout" 2>&1
log() { echo "[$RUN $(date +%T)] $*" | tee -a "$out/campaign.log"; }
log "launched depth $DEPTH"
deadline=$(( $(date +%s) + 2700 )); ok=0
while (( $(date +%s) < deadline )); do curl -fsS "http://127.0.0.1:$port/health" >/dev/null 2>&1 && { ok=1; break; }; docker ps --format '{{.Names}}' | grep -q "^$name$" || break; sleep 15; done
if (( ok )); then
  log "healthy"
  body="{\"model\":\"$RUN\",\"prompt\":\"Write a detailed, practical explanation of how a distributed cache invalidation protocol should handle partial failures, with examples.\",\"max_tokens\":256,\"temperature\":0,\"ignore_eos\":true}"
  for i in 1 2; do curl -fsS -X POST "http://127.0.0.1:$port/v1/completions" -H 'Content-Type: application/json' -d "$body" >"$out/warm$i.json" 2>&1; done
  for i in 1 2 3; do
    t0=$(date +%s.%N); curl -fsS -X POST "http://127.0.0.1:$port/v1/completions" -H 'Content-Type: application/json' -d "$body" >"$out/timed$i.json" 2>&1; t1=$(date +%s.%N)
    log "timed$i: $(python3 -c "import json,sys;d=json.load(open('$out/timed$i.json'));u=d['usage'];print(u['completion_tokens'],'tokens', round(u['completion_tokens']/($t1-$t0),2),'tok/s wall incl. prefill')")"
  done
  curl -fsS "http://127.0.0.1:$port/metrics" >"$out/metrics.txt" 2>&1
  log "spec metrics: $(grep -E 'spec_decode_num_accepted_tokens_total|spec_decode_num_draft_tokens_total|spec_decode_num_drafts_total' $out/metrics.txt | grep -v '^#' | tr '\n' ' ' | cut -c1-300)"
else log "ABORT: server did not become healthy"; fi
docker logs "$name" >"$out/server.log" 2>&1 || true; docker stop -t 120 "$name" >/dev/null 2>&1 || true
log "campaign complete"
