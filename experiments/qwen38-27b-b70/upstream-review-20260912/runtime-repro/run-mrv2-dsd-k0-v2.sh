#!/usr/bin/env bash
# Upstream reproduction (2026-09-12): MRV2 (VLLM_USE_V2_MODEL_RUNNER=1) + dynamic speculative decoding with a K=0 range
# on stock vLLM XPU, one B70, Qwen3.5-9B W4A16 (RedHatAI), no lab patches or env. The lab's pinned 0.27.2rc1.dev77 build
# asserts in InputBatch.make_dummy on the K=0 range during speculator capture (cudynm1 note); upstream #51510 reports
# MRV2 ignoring dynamic K on 0.26.1rc1.dev251. Question: what does the current image do? IMG=<image> selects it.
set -uo pipefail
img=${IMG:?}; tag=${TAG:?}; out=/mnt/fast-ai/bench-results/upstream-repro-20260912/${OUTPFX:-mrv2-dsd}-$tag; mkdir -p "$out/cache"
model=/home/steve/llm-models/qwen35-9b-w4a16; port=18140; name=upstream-${OUTPFX:-mrv2-dsd}-$tag
log() { echo "[$tag $(date +%T)] $*" | tee -a "$out/campaign.log"; }
docker image inspect "$img" --format '{{.Id}}' >"$out/image-id.txt"
for arm in ${ARMS:-mrv2-dsd mrv1-dsd}; do
  v2=1; [[ $arm == mrv1-dsd ]] && v2=0
  docker run -d --name "$name-$arm" --ulimit core=0 --memory 12g --memory-swap 16g --device /dev/dri:/dev/dri --group-add render --cap-add SYS_PTRACE --security-opt label=disable --ipc=host --shm-size=8g \
    -p 127.0.0.1:$port:8000 -v "$model:/model:ro" -v "$out/cache-$arm:/root/.cache/vllm" \
    -e ZE_AFFINITY_MASK=0 -e ONEAPI_DEVICE_SELECTOR=level_zero:0 -e VLLM_TARGET_DEVICE=xpu -e VLLM_WORKER_MULTIPROC_METHOD=spawn -e VLLM_USE_V2_MODEL_RUNNER=$v2 \
    --entrypoint bash "$img" -lc 'exec vllm serve /model --served-model-name dsd --host 0.0.0.0 --port 8000 --tensor-parallel-size 1 --dtype float16 --quantization compressed-tensors --gpu-memory-utilization 0.9 --max-model-len 256 --max-num-seqs 64 --max-num-batched-tokens 512 --no-enable-prefix-caching --speculative-config '"'"'{"method":"qwen3_5_mtp","num_speculative_tokens":3,"num_speculative_tokens_per_batch_size":[[1,8,3],[9,16,1],[17,64,0]]}'"'"'' >/dev/null
  log "$arm launched (VLLM_USE_V2_MODEL_RUNNER=$v2)"; ( docker logs -f "$name-$arm" >"$out/$arm.server.live.log" 2>&1 ) &
  deadline=$(( $(date +%s) + 1500 )); ok=0
  while (( $(date +%s) < deadline )); do curl -fsS "http://127.0.0.1:$port/health" >/dev/null 2>&1 && { ok=1; break; }; docker ps --format '{{.Names}}' | grep -q "^$name-$arm$" || break; sleep 10; done
  docker logs "$name-$arm" >"$out/$arm.server.log" 2>&1 || true
  if (( ok )); then
    log "$arm healthy"
    # 64 concurrent short requests exercise the K=0 range; then 1 request exercises K=3
    python3 /home/steve/b70-optimization-lab/scripts/bench-openai-concurrency-oracle.py --base-url "http://127.0.0.1:$port" --model dsd --api-mode completions --suite /home/steve/b70-optimization-lab/experiments/qwen38-27b-b70/data/2026-08-25-qwen38-q4km-tp2-http-smallctx-suite.json --concurrency ${CONC:-1,64} --repeats 1 --max-tokens 64 --seed 42 --timeout 600 --request-extra-json '{"ignore_eos":true,"temperature":0}' --return-token-ids --out "$out/$arm.ladder.json" >"$out/$arm.harness.stdout" 2>&1; log "$arm harness exit $?"
    docker logs "$name-$arm" >"$out/$arm.server.log" 2>&1 || true
  else log "$arm did NOT become healthy (container $(docker ps -a --format '{{.Names}} {{.Status}}' | grep "$name-$arm" | cut -c1-60))"; fi
  docker stop -t 60 "$name-$arm" >/dev/null 2>&1 || true; sleep 5; docker logs "$name-$arm" >"$out/$arm.server.log" 2>&1 || true; docker rm -f "$name-$arm" >/dev/null 2>&1 || true
  grep -nE 'Traceback|AssertionError|Error|make_dummy|Dynamic speculative|Overriding cudagraph|falling back|num_spec' "$out/$arm.server.log" | grep -v 'Unknown vLLM environment' | head -12 | cut -c1-240 | tee -a "$out/campaign.log"
done
log "=== done ==="
