#!/usr/bin/env bash
# Per-kernel GPU time per decoded token (card 1; Gemma on card 0, restored at the end). llama-bench -p 0 -n 16 and
# -n 48 under the PTI shim (tools/ktime_shim.cpp); the difference / 32 is one decoded token. Timing only.
#   FUSE_ENV="..." TAG=kt1 ktime.sh      (SUDO_ASKPASS set; under systemd-run --user)
set -uo pipefail
LAB=/home/steve/b70-optimization-lab
BUILD_DIR=${BUILD_DIR:-/home/steve/src/llama.cpp-lfm25-work/build-lfm25}
MODEL_DIR=/mnt/fast-ai/llm-models/lfm25-24b-a2b-q8-gguf
SHIM=${SHIM:-/mnt/fast-ai/bench-results/lfm25-24b-a2b/libktime.so}
FUSE_ENV=${FUSE_ENV:-}
TAG=${TAG:?}
OUT=/mnt/fast-ai/bench-results/lfm25-24b-a2b/fusion/$TAG
mkdir -p "$OUT"
log() { echo "### $(date +%T) $*"; }
START=$(date '+%Y-%m-%d %H:%M:%S')
restore() {
  log "restoring Gemma's two-card throughput recipe"
  "$LAB/scripts/gemma4-26b-two-b70-recipe.sh" throughput 2>&1 | grep -v "JSONDecode\|raise " | tail -3
  journalctl -k --since "$START" --no-pager -o cat | grep -iE 'xe .*(fault|reset|error)|GT[0-9]*: .*reset' | head -5 || true
  log done
}
trap restore EXIT
log "moving Gemma to card 0"
"$LAB/scripts/gemma4-26b-two-b70-recipe.sh" throughput-card0 2>&1 | grep -v "JSONDecode\|raise " | tail -1

set +u; source /opt/intel/oneapi/setvars.sh --force >/dev/null; set -u
env_args=()
read -ra env_args <<< "$FUSE_ENV"
for n in 16 48; do
  env ONEAPI_DEVICE_SELECTOR=level_zero:1 ZES_ENABLE_SYSMAN=1 UR_L0_ENABLE_RELAXED_ALLOCATION_LIMITS=1 \
    GGML_SYCL_DNNL_DETERMINISTIC=1 GGML_SYCL_DISABLE_OPT=0 GGML_SYCL_PRIORITIZE_DMMV=1 \
    LLAMA_SYCL_DMMV_Q8_0_REORDER_EXACT=4 LLAMA_SYCL_MUL_MAT_ID_Q8_0_REORDER=1 LLAMA_SYCL_MMVQ_ID_XOR_REDUCE=1 \
    "${env_args[@]}" ZE_ENABLE_TRACING_LAYER=1 KT_OUT="$OUT/ktime-n$n.tsv" LD_PRELOAD="$SHIM" \
    "$BUILD_DIR/bin/llama-bench" -m "$MODEL_DIR/LFM2.5-24B-A2B-Q8_0.gguf" -ngl 99 -fa 1 -ctk f16 -ctv f16 \
    -b 2048 -ub 512 -t 8 --poll 50 -p 0 -n $n -r 1 -o json > "$OUT/ktime-bench-n$n.json" 2> "$OUT/ktime-bench-n$n.err"
  echo "ktime n=$n rc=$? kernels=$(wc -l < "$OUT/ktime-n$n.tsv" 2>/dev/null)"
done
python3 "$LAB/experiments/lfm25-24b-a2b-b70/scripts/ktime_parse.py" "$OUT/ktime-n16.tsv" 16 "$OUT/ktime-n48.tsv" 48 \
  | tee "$OUT/ktime.txt"
