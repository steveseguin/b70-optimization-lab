#!/usr/bin/env bash
# R278 (2026-09-06): why is the c32 ladder step ~225 ms when the profiled uniform step is ~110 ms? A/B on one headline server
# (V1, INT4 head, graphs to 320, GDN spec group 64, max-num-seqs 64): 32 concurrent 128-token requests as (a) plain
# non-streaming completions, (b) streaming, (c) streaming with logprobs=1 and return_token_ids (the ladder harness shape),
# (d) plain again. Reports aggregate tok/s per shape. Waits for pid $1 and for no qwen38 container.
set -uo pipefail
while docker ps --format "{{.Names}}" | grep -q qwen38; do sleep 30; done
[[ -n "${1:-}" ]] && while kill -0 "$1" 2>/dev/null; do sleep 30; done
DEPTH=${DEPTH:-4}; RUN=${RUN:-r278}
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
  -e VLLM_XPU_GEMMA_RMSNORM_TRITON=0 -e VLLM_XPU_RMSNORM_TRITON=0 \
  -e PYTORCH_ALLOC_CONF=expandable_segments:True -e CCL_ATL_TRANSPORT=ofi -e FI_PROVIDER=tcp -e FI_TCP_IFACE=lo -e CCL_ZE_IPC_EXCHANGE=pidfd -e CCL_SEND=direct -e CCL_RECV=direct -e CCL_TOPO_P2P_ACCESS=1 \
  -e CCL_SYCL_ALLREDUCE_SIMPLE_THRESHOLD=4294967296 -e CCL_SYCL_ALLGATHERV_SIMPLE_THRESHOLD=4294967296 -e CCL_SYCL_REDUCE_SCATTER_SIMPLE_THRESHOLD=4294967296 \
  "$img" --model /model --served-model-name "$RUN" --host 0.0.0.0 --port 8000 --tensor-parallel-size 2 --dtype float16 --quantization gptq --kv-cache-dtype auto --gpu-memory-utilization 0.95 --max-model-len 1024 --block-size 64 --max-num-seqs 64 --max-num-batched-tokens 512 --no-enable-prefix-caching --enable-prompt-tokens-details --language-model-only ${ASYNC:+--async-scheduling} "${spec[@]}" --compilation-config "$CC" >"$out/docker-run.stdout" 2>&1
log() { echo "[$RUN $(date +%T)] $*" | tee -a "$out/campaign.log"; }
log "launched depth $DEPTH"
deadline=$(( $(date +%s) + 2700 )); ok=0
while (( $(date +%s) < deadline )); do curl -fsS "http://127.0.0.1:$port/health" >/dev/null 2>&1 && { ok=1; break; }; docker ps --format '{{.Names}}' | grep -q "^$name$" || break; sleep 15; done
if (( ok )); then
  log "healthy"
  suite=/home/steve/b70-optimization-lab/experiments/qwen38-27b-b70/data/2026-08-25-qwen38-q4km-tp2-http-smallctx-suite.json
  python3 - "$out" "$RUN" "$port" "$suite" <<'PY' 2>&1 | tee -a "$out/campaign.log"
import json,sys,time,threading,urllib.request
out,model,port,suite=sys.argv[1:5]; base=json.load(open(suite)); base=base.get("prompts") or base
prompts=[(p["prompt"]+f" Variant {i//len(base)}.") for i,p in enumerate(base*4)][:32]
def one(i,shape,res):
    body={"model":model,"prompt":prompts[i],"max_tokens":128,"temperature":0,"ignore_eos":True}
    ep="completions"
    if shape.startswith("stream"): body.update({"stream":True,"stream_options":{"include_usage":True},"return_token_ids":True,"seed":42,"top_p":1})
    if shape=="stream_chat": ep="chat/completions"; body["messages"]=[{"role":"user","content":body.pop("prompt")}]
    if shape=="stream_logprobs": body["logprobs"]=1
    req=urllib.request.Request(f"http://127.0.0.1:{port}/v1/{ep}",data=json.dumps(body).encode(),headers={"Content-Type":"application/json"})
    t0=time.perf_counter(); n=0
    with urllib.request.urlopen(req,timeout=600) as r:
        if body.get("stream"):
            for line in r:
                if line.startswith(b"data: ") and b"[DONE]" not in line:
                    d=json.loads(line[6:]); u=d.get("usage")
                    if u: n=u["completion_tokens"]
        else:
            d=json.load(r); n=d["usage"]["completion_tokens"]
    res[i]=(time.perf_counter()-t0,n)
for rep in (1,2):
  for shape in ("plain","stream","stream_chat","stream_logprobs","plain"):
    res={}; ths=[threading.Thread(target=one,args=(i,shape,res)) for i in range(32)]
    t0=time.perf_counter(); [t.start() for t in ths]; [t.join() for t in ths]; wall=time.perf_counter()-t0
    toks=sum(v[1] for v in res.values()); print(f"[{model} {time.strftime('%H:%M:%S')}] rep{rep} c32 {shape:16s} wall {wall:6.2f}s tokens {toks} aggregate {toks/wall:7.1f} tok/s")
PY
else log "ABORT: server did not become healthy"; fi
docker logs "$name" >"$out/server.log" 2>&1 || true; docker stop -t 120 "$name" >/dev/null 2>&1 || true
log "campaign complete"
