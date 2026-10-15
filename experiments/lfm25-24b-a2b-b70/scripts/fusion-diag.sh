#!/usr/bin/env bash
# Short diagnostic session on card 1 (Gemma on card 0, restored at the end):
#   1. a server with FUSE_ENV + LLAMA_SYCL_FUSE_DEBUG=1, one short request, then the FUSE_DEBUG lines
#   2. a kernel census: llama-bench -p 0 -n N under sycl-trace --ur.call, kernel launches counted by name
#   FUSE_ENV="..." TAG=diag1 fusion-diag.sh      (SUDO_ASKPASS set; under systemd-run --user)
set -uo pipefail
LAB=/home/steve/b70-optimization-lab
PKG=$LAB/repro/lfm25-24b-a2b-q8-b70
BUILD_DIR=${BUILD_DIR:-/home/steve/src/llama.cpp-lfm25-work/build-lfm25}
MODEL_DIR=/mnt/fast-ai/llm-models/lfm25-24b-a2b-q8-gguf
FUSE_ENV=${FUSE_ENV:-}
TAG=${TAG:?}
OUT=/mnt/fast-ai/bench-results/lfm25-24b-a2b/fusion/$TAG
PORT=18110
UNIT=lfm25-fuse-srv
mkdir -p "$OUT"
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

log "moving Gemma to card 0"
"$LAB/scripts/gemma4-26b-two-b70-recipe.sh" throughput-card0 2>&1 | grep -v "JSONDecode\|raise " | tail -1

if [[ ${SKIP_SERVER:-0} != 1 ]]; then
  for _ in $(seq 1 120); do [[ -z $(ss -Htan "( sport = :$PORT or dport = :$PORT )") ]] && break; sleep 1; done
  systemctl --user reset-failed $UNIT 2>/dev/null
  envs=(-E BUILD_DIR="$BUILD_DIR" -E MODEL_DIR="$MODEL_DIR" -E GPU=1 -E PORT=$PORT -E LLAMA_SYCL_FUSE_DEBUG=1)
  for kv in $FUSE_ENV; do envs+=(-E "$kv"); done
  systemd-run --user --unit=$UNIT --collect -p WorkingDirectory=$LAB "${envs[@]}" \
    bash -c "exec $PKG/serve.sh fast > $OUT/server-debug.log 2>&1" >/dev/null
  for _ in $(seq 1 240); do curl -fsS -m 2 "http://127.0.0.1:$PORT/v1/models" >/dev/null 2>&1 && break; sleep 1; done
  curl -s -m 60 "http://127.0.0.1:$PORT/completion" -d '{"prompt":"Hello, my name is","n_predict":8,"temperature":0}' \
    | python3 -c "import json,sys; print('reply:', repr(json.load(sys.stdin)['content']))"
  systemctl --user stop $UNIT
  log "FUSE_DEBUG lines"
  grep "FUSE_DEBUG" "$OUT/server-debug.log" | head -20
fi

log "kernel census: llama-bench -p 0 -n 16 and -n 48 under sycl-trace (difference / 32 = per token)"
set +u; source /opt/intel/oneapi/setvars.sh --force >/dev/null; set -u
env_args=()
read -ra env_args <<< "$FUSE_ENV"
for n in 16 48; do
  env ONEAPI_DEVICE_SELECTOR=level_zero:1 ZES_ENABLE_SYSMAN=1 UR_L0_ENABLE_RELAXED_ALLOCATION_LIMITS=1 \
    GGML_SYCL_DNNL_DETERMINISTIC=1 GGML_SYCL_DISABLE_OPT=0 GGML_SYCL_PRIORITIZE_DMMV=1 \
    LLAMA_SYCL_DMMV_Q8_0_REORDER_EXACT=4 LLAMA_SYCL_MUL_MAT_ID_Q8_0_REORDER=1 LLAMA_SYCL_MMVQ_ID_XOR_REDUCE=1 \
    "${env_args[@]}" /opt/intel/oneapi/compiler/latest/bin/sycl-trace --ur.call --print-format=compact \
    "$BUILD_DIR/bin/llama-bench" -m "$MODEL_DIR/LFM2.5-24B-A2B-Q8_0.gguf" -ngl 99 -fa 1 -ctk f16 -ctv f16 \
    -b 2048 -ub 512 -t 8 --poll 50 -p 0 -n $n -r 1 -o json > "$OUT/census-trace-n$n.txt" 2>&1
  echo "census n=$n rc=$? lines=$(wc -l < "$OUT/census-trace-n$n.txt")"
done
