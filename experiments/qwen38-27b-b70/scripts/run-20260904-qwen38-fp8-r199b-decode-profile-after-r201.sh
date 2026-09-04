#!/usr/bin/env bash
# R199 (2026-09-04): torch profiler capture of MTP1 decode steps on the R187 configuration (diagnostic only; no publication).
# Standalone docker run mirroring run-server.sh with VLLM_TORCH_PROFILER_DIR added; /start_profile, one 128-token completion, /stop_profile.
set -uo pipefail
while kill -0 "${1:?pid}" 2>/dev/null; do sleep 30; done
out=/mnt/fast-ai/bench-results/qwen38-fp8-r187-decode-profile-20260904-r199b; mkdir -p "$out/profile" "$out/cache"
img=neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-gdn-split-mixed-r156; model=/mnt/fast-ai/llm-models/qwen3.8-27b-fp8; port=18130; name=qwen38-fp8-r199b-profile
CC='{"cudagraph_mode":"PIECEWISE","cudagraph_capture_sizes":[1],"max_cudagraph_capture_size":1,"splitting_ops":[],"inductor_compile_config":{"combo_kernels":false,"benchmark_combo_kernel":false,"deterministic":true,"triton.autotune_pointwise":false,"benchmark_epilogue_fusion":false}}'
docker run -d --rm --name "$name" --ulimit core=0 --memory 12g --memory-swap 16g --device /dev/dri:/dev/dri --group-add render --cap-add SYS_PTRACE --security-opt label=disable --ipc=host --shm-size=8g \
  -p 127.0.0.1:$port:8000 -v "$model:/model:ro" -v "$out/cache:/root/.cache/vllm" -v "$out/profile:/profile" \
  -e ZE_AFFINITY_MASK=0,1 -e ONEAPI_DEVICE_SELECTOR=level_zero:0,1 -e VLLM_TARGET_DEVICE=xpu -e VLLM_WORKER_MULTIPROC_METHOD=spawn -e VLLM_XPU_ENABLE_XPU_GRAPH=0 \
  -e TORCHINDUCTOR_DETERMINISTIC=0 -e VLLM_ENABLE_INDUCTOR_MAX_AUTOTUNE=1 -e VLLM_ENABLE_INDUCTOR_COORDINATE_DESCENT_TUNING=1 -e VLLM_XPU_FP8_BLOCK_W8A16=1 -e VLLM_XPU_GDN_SPLIT_MIXED=1 \
  -e VLLM_XPU_GEMMA_RMSNORM_TRITON=0 -e VLLM_XPU_RMSNORM_TRITON=0 \
  -e PYTORCH_ALLOC_CONF=expandable_segments:True -e CCL_ATL_TRANSPORT=ofi -e FI_PROVIDER=tcp -e FI_TCP_IFACE=lo -e CCL_ZE_IPC_EXCHANGE=pidfd -e CCL_SEND=direct -e CCL_RECV=direct \
  -e CCL_SYCL_ALLREDUCE_SIMPLE_THRESHOLD=4294967296 -e CCL_SYCL_ALLGATHERV_SIMPLE_THRESHOLD=4294967296 -e CCL_SYCL_REDUCE_SCATTER_SIMPLE_THRESHOLD=4294967296 \
  --entrypoint bash "$img" -lc "exec vllm serve /model --served-model-name r199 --host 0.0.0.0 --port 8000 --tensor-parallel-size 2 --dtype float16 --quantization fp8 --kv-cache-dtype auto --gpu-memory-utilization 0.95 --max-model-len 1024 --block-size 64 --max-num-seqs 1 --max-num-batched-tokens 1024 --no-enable-prefix-caching --enable-prompt-tokens-details --language-model-only --speculative-config '{\"method\":\"qwen3_next_mtp\",\"num_speculative_tokens\":1}' --compilation-config '$CC' --profiler-config '{\"profiler\":\"torch\",\"torch_profiler_dir\":\"/profile\"}'" >"$out/docker-run.stdout" 2>&1
echo "[r199b $(date +%T)] launched" | tee -a "$out/campaign.log"
deadline=$(( $(date +%s) + 2700 )); ok=0
while (( $(date +%s) < deadline )); do curl -fsS "http://127.0.0.1:$port/health" >/dev/null 2>&1 && { ok=1; break; }; docker ps --format '{{.Names}}' | grep -q "^$name$" || break; sleep 15; done
if (( ok )); then
  echo "[r199b $(date +%T)] healthy" | tee -a "$out/campaign.log"
  body='{"model":"r199","prompt":"Write a detailed, practical explanation of how a distributed cache invalidation protocol should handle partial failures, with examples.","max_tokens":128,"temperature":0,"ignore_eos":true}'
  curl -fsS -X POST "http://127.0.0.1:$port/v1/completions" -H 'Content-Type: application/json' -d "$body" >"$out/warm.json" 2>&1
  curl -fsS -X POST "http://127.0.0.1:$port/start_profile" >/dev/null 2>&1; echo "[r199b $(date +%T)] profiling" | tee -a "$out/campaign.log"
  curl -fsS -X POST "http://127.0.0.1:$port/v1/completions" -H 'Content-Type: application/json' -d "$body" >"$out/profiled.json" 2>&1
  curl -fsS -X POST "http://127.0.0.1:$port/stop_profile" >/dev/null 2>&1; sleep 90
  echo "[r199b $(date +%T)] trace files: $(ls -la $out/profile | wc -l)" | tee -a "$out/campaign.log"
else echo "[r199b $(date +%T)] ABORT: server did not become healthy" | tee -a "$out/campaign.log"; fi
docker logs "$name" >"$out/server.log" 2>&1 || true; docker stop -t 120 "$name" >/dev/null 2>&1 || true
echo "[r199b $(date +%T)] campaign complete" | tee -a "$out/campaign.log"
