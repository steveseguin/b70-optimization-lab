#!/usr/bin/env bash
# R262 (2026-09-06): torch-profiler trace of the INT4 headline configuration (R256 image, TP2, XPU graphs FULL_DECODE_ONLY 1-8,
# draft-only INT4 head, MTP depth ${DEPTH:-4}, strict launcher env) over a 64-token greedy completion, to split the step between
# the eager draft passes and the captured verify step. Waits for the pid in $1 (the R261 ladder wrapper) before starting.
set -uo pipefail
[[ -n "${1:-}" ]] && while kill -0 "$1" 2>/dev/null; do sleep 30; done
DEPTH=${DEPTH:-4}; RUN=${RUN:-r262}
out=/mnt/fast-ai/bench-results/qwen38-int4-headline-decode-profile-20260906-${RUN}-mtp${DEPTH}; mkdir -p "$out/profile" "$out/cache"
img=neural-download/vllm-openai-xpu:qwen38-int4-draft-int4-head-r256; model=/mnt/fast-ai/llm-models/qwen3.8-27b-int4-autoround-gptq-relabel; port=18131; name=qwen38-int4-${RUN}-profile
CC='{"cudagraph_mode":"FULL_DECODE_ONLY","cudagraph_capture_sizes":[1,2,3,4,5,6,8],"max_cudagraph_capture_size":8,"splitting_ops":[],"inductor_compile_config":{"combo_kernels":false,"benchmark_combo_kernel":false,"deterministic":true,"split_reductions":false,"triton.autotune_pointwise":false,"benchmark_epilogue_fusion":false}}'
spec=(); [[ "$DEPTH" == 0 ]] || spec=(--speculative-config "{\"method\":\"qwen3_next_mtp\",\"num_speculative_tokens\":${DEPTH}}")
docker run -d --rm --name "$name" --ulimit core=0 --memory 12g --memory-swap 16g --device /dev/dri:/dev/dri --group-add render --cap-add SYS_PTRACE --security-opt label=disable --ipc=host --shm-size=8g \
  -p 127.0.0.1:$port:8000 -v "$model:/model:ro" -v "$out/cache:/root/.cache/vllm" -v "$out/profile:/profile" \
  -e ZE_AFFINITY_MASK=0,1 -e ONEAPI_DEVICE_SELECTOR=level_zero:0,1 -e VLLM_TARGET_DEVICE=xpu -e VLLM_WORKER_MULTIPROC_METHOD=spawn -e VLLM_XPU_ENABLE_XPU_GRAPH=1 -e VLLM_XPU_ALLREDUCE_HOST_WAIT=1 \
  -e TORCHINDUCTOR_DETERMINISTIC=1 -e VLLM_ENABLE_INDUCTOR_MAX_AUTOTUNE=0 -e VLLM_ENABLE_INDUCTOR_COORDINATE_DESCENT_TUNING=0 -e PYTHONHASHSEED=0 \
  -e VLLM_XPU_FP8_BLOCK_W8A16=1 -e VLLM_XPU_W4A16_DETERMINISM_PAD=0 -e VLLM_XPU_GDN_SPLIT_MIXED=1 -e VLLM_XPU_GDN_SPEC_GROUP=16 -e VLLM_XPU_GDN_PREFILL_GROUP=1 -e VLLM_XPU_GDN_SPEC_PERSISTENT_SCRATCH=1 -e VLLM_XPU_GDN_NATIVE_FALLBACK=1 \
  -e VLLM_XPU_FP16_LINEAR_ROWCHUNK=32 -e VLLM_BATCH_INVARIANT=0 -e VLLM_XPU_QWEN_GEMMA_RMSNORM_BATCH_INVARIANT=0 -e VLLM_XPU_QWEN_GEMMA_RMSNORM_PACKED_SERIAL_EXACT=1 \
  -e VLLM_XPU_DRAFT_LM_HEAD_INT4=1 -e VLLM_XPU_DRAFT_LM_HEAD_INT4_GROUP_SIZE=128 -e VLLM_XPU_DRAFT_LM_HEAD_INT4_SCALE_DTYPE=bf16 -e VLLM_XPU_DRAFT_LM_HEAD_INT4_CHUNK_ROWS=2048 \
  -e VLLM_XPU_GEMMA_RMSNORM_TRITON=0 -e VLLM_XPU_RMSNORM_TRITON=0 \
  -e PYTORCH_ALLOC_CONF=expandable_segments:True -e CCL_ATL_TRANSPORT=ofi -e FI_PROVIDER=tcp -e FI_TCP_IFACE=lo -e CCL_ZE_IPC_EXCHANGE=pidfd -e CCL_SEND=direct -e CCL_RECV=direct -e CCL_TOPO_P2P_ACCESS=1 \
  -e CCL_SYCL_ALLREDUCE_SIMPLE_THRESHOLD=4294967296 -e CCL_SYCL_ALLGATHERV_SIMPLE_THRESHOLD=4294967296 -e CCL_SYCL_REDUCE_SCATTER_SIMPLE_THRESHOLD=4294967296 \
  "$img" --model /model --served-model-name "$RUN" --host 0.0.0.0 --port 8000 --tensor-parallel-size 2 --dtype float16 --quantization gptq --kv-cache-dtype auto --gpu-memory-utilization 0.95 --max-model-len 1024 --block-size 64 --max-num-seqs 1 --max-num-batched-tokens 1024 --no-enable-prefix-caching --enable-prompt-tokens-details --language-model-only "${spec[@]}" --compilation-config "$CC" --profiler-config '{"profiler":"torch","torch_profiler_dir":"/profile"}' >"$out/docker-run.stdout" 2>&1
log() { echo "[$RUN $(date +%T)] $*" | tee -a "$out/campaign.log"; }
log "launched depth $DEPTH"
deadline=$(( $(date +%s) + 2700 )); ok=0
while (( $(date +%s) < deadline )); do curl -fsS "http://127.0.0.1:$port/health" >/dev/null 2>&1 && { ok=1; break; }; docker ps --format '{{.Names}}' | grep -q "^$name$" || break; sleep 15; done
if (( ok )); then
  log "healthy"
  body="{\"model\":\"$RUN\",\"prompt\":\"Write a detailed, practical explanation of how a distributed cache invalidation protocol should handle partial failures, with examples.\",\"max_tokens\":64,\"temperature\":0,\"ignore_eos\":true}"
  curl -fsS -X POST "http://127.0.0.1:$port/v1/completions" -H 'Content-Type: application/json' -d "$body" >"$out/warm.json" 2>&1
  curl -fsS -X POST "http://127.0.0.1:$port/v1/completions" -H 'Content-Type: application/json' -d "$body" >"$out/warm2.json" 2>&1
  curl -fsS -X POST "http://127.0.0.1:$port/start_profile" >/dev/null 2>&1; log "profiling"
  curl -fsS -X POST "http://127.0.0.1:$port/v1/completions" -H 'Content-Type: application/json' -d "$body" >"$out/profiled.json" 2>&1
  curl -fsS -X POST "http://127.0.0.1:$port/stop_profile" >/dev/null 2>&1; sleep 240
  curl -fsS "http://127.0.0.1:$port/metrics" >"$out/metrics.txt" 2>&1
  log "trace files: $(ls $out/profile | wc -l)"
else log "ABORT: server did not become healthy"; fi
docker logs "$name" >"$out/server.log" 2>&1 || true; docker stop -t 120 "$name" >/dev/null 2>&1 || true
log "campaign complete"
