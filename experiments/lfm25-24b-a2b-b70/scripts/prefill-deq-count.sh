#!/usr/bin/env bash
# Diagnosis for the prefill question in notes/2026-10-14-lfm25-24b-a2b-bringup.md (2026-10-15): with
# LLAMA_SYCL_Q8_0_DEQ_COUNT=1 the build logs how many Q8_0 to-FP16 conversions ran on reordered and on plain weights
# (and their element totals) at every power-of-two call count. Old kernel throughout (the speed-relevant case).
#   1. llama-bench -p 2048 -n 128 -d 0,2048 -r 1 -v   (pp before any decode, tg, then pp at depth after the decode)
#   2. llama-server (serve.sh fast): one short reply (32 tokens), then the 2K prompt twice
#   prefill-deq-count.sh      (SUDO_ASKPASS set; under systemd-run --user; card 1, Gemma on card 0, restored)
set -uo pipefail
LAB=/home/steve/b70-optimization-lab
PKG=$LAB/repro/lfm25-24b-a2b-q8-b70
BUILD_DIR=${BUILD_DIR:-/home/steve/src/llama.cpp-lfm25-work/build-lfm25}
MODEL_DIR=/mnt/fast-ai/llm-models/lfm25-24b-a2b-q8-gguf
OUT=${OUT:-/mnt/fast-ai/bench-results/lfm25-24b-a2b/prefill-reorder}
PROBE=/mnt/fast-ai/bench-results/lfm25-24b-a2b/probe
PORT=18110
UNIT=lfm25-prefill-srv
log() { echo "### $(date +%T) $*"; }
START=$(date '+%Y-%m-%d %H:%M:%S')
restore() {
  systemctl --user stop $UNIT 2>/dev/null
  log "restoring Gemma's two-card throughput recipe"
  "$LAB/scripts/gemma4-26b-two-b70-recipe.sh" throughput 2>&1 | grep -v "JSONDecode\|raise " | tail -3
  journalctl -k --since "$START" --no-pager -o cat | grep -iE 'xe .*(fault|reset|error)|GT[0-9]*: .*reset' | head -5 || true
  log done
}
trap restore EXIT
log "moving Gemma to card 0 (throughput-card0)"
"$LAB/scripts/gemma4-26b-two-b70-recipe.sh" throughput-card0 2>&1 | grep -v "JSONDecode\|raise " | tail -2

log "1. llama-bench with counters"
(
  set +u; source /opt/intel/oneapi/setvars.sh --force >/dev/null; set -u
  env ONEAPI_DEVICE_SELECTOR=level_zero:1 ZES_ENABLE_SYSMAN=1 UR_L0_ENABLE_RELAXED_ALLOCATION_LIMITS=1 \
    GGML_SYCL_DNNL_DETERMINISTIC=1 GGML_SYCL_DISABLE_OPT=0 GGML_SYCL_PRIORITIZE_DMMV=1 \
    LLAMA_SYCL_DMMV_Q8_0_REORDER_EXACT=4 LLAMA_SYCL_MUL_MAT_ID_Q8_0_REORDER=1 LLAMA_SYCL_MMVQ_ID_XOR_REDUCE=1 \
    LLAMA_SYCL_FUSE_RMS_NORM_MUL=1 LLAMA_SYCL_FUSE_ADD_RMS_NORM_MUL=1 LLAMA_SYCL_FUSE_MOE_SUM=1 \
    LLAMA_SYCL_FUSE_MOE_ROUTE=1 LLAMA_SYCL_FUSE_SHORTCONV=1 LLAMA_SYCL_FUSE_F16_SHADOW=1 LLAMA_SYCL_FUSE_Q8_SHADOW=1 \
    LLAMA_SYCL_FUSE_MOE_GATE_UP=1 LLAMA_SYCL_FUSE_NORM_ROPE=1 LLAMA_SYCL_FUSE_NORM_Q8=1 LLAMA_SYCL_FUSE_MOE_DOWN_SUM=1 \
    LLAMA_SYCL_FUSE_CONV_STATE_ROWS=1 LLAMA_SYCL_Q8_0_DEQ_COUNT=1 \
    timeout 900 "$BUILD_DIR/bin/llama-bench" -m "$MODEL_DIR/LFM2.5-24B-A2B-Q8_0.gguf" -ngl 99 -fa 1 -ctk f16 -ctv f16 \
    -b 2048 -ub 512 -t 8 --poll 50 -p 2048 -n 128 -d 0,2048 -r 1 -v > "$OUT/count-bench.out" 2> "$OUT/count-bench.err"
  echo "llama-bench rc=$?"
)
grep -a "Q8_0_DEQ_COUNT\|^| " "$OUT/count-bench.err" "$OUT/count-bench.out" | sed 's/^[^:]*://' | tail -40

log "2. server with counters"
systemctl --user reset-failed $UNIT 2>/dev/null
systemd-run --user --unit=$UNIT --collect -p WorkingDirectory=$LAB -E BUILD_DIR="$BUILD_DIR" -E MODEL_DIR="$MODEL_DIR" \
  -E GPU=1 -E PORT=$PORT -E LLAMA_SYCL_Q8_0_DEQ_COUNT=1 \
  bash -c "exec $PKG/serve.sh fast > $OUT/server-count.log 2>&1" >/dev/null
for i in $(seq 1 240); do
  curl -fsS -m 2 "http://127.0.0.1:$PORT/v1/models" >/dev/null 2>&1 && { log "server ready after ${i}s"; break; }
  sleep 1
done
python3 - "$PROBE/long-prompts.json" "http://127.0.0.1:$PORT" <<'EOF'
import json, sys, urllib.request
prompts, base = json.load(open(sys.argv[1]))["prompts"], sys.argv[2]
def post(body):
    req = urllib.request.Request(base + "/completion", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=900))
p2k = [p for p in prompts if p["id"] == "long-2k"][0]["prompt"]
w = post({"prompt": "Write a short paragraph about rivers.", "n_predict": 32, "temperature": 0, "cache_prompt": False})
print("reply", w["timings"]["prompt_n"], "prompt tokens,", w["timings"]["predicted_n"], "generated", flush=True)
for rep in (1, 2):
    t = post({"prompt": p2k, "n_predict": 1, "temperature": 0, "cache_prompt": False})["timings"]
    print(f'2k rep {rep}: {t["prompt_n"]} tokens, {t["prompt_per_second"]:.1f} tok/s', flush=True)
EOF
systemctl --user stop $UNIT
grep -a "Q8_0_DEQ_COUNT\|prompt eval time" "$OUT/server-count.log" | sed 's/.*Q8_0_DEQ_COUNT/Q8_0_DEQ_COUNT/' | tail -40
