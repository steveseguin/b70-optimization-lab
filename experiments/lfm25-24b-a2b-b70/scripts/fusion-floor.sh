#!/usr/bin/env bash
# Matmul floor probe (lab note, 2026-10-15). DIAGNOSTIC ONLY for the FLOOR set: every op except the matmuls,
# flash attention and ARGSORT (whose output must stay a valid expert permutation) is skipped, so outputs are wrong;
# only decode timing is read. Sets: none (x1), fused (all seven exact fusions), FLOOR. Card 1, Gemma on card 0.
#   fusion-floor.sh            (SUDO_ASKPASS set; run under systemd-run --user)
set -uo pipefail
LAB=/home/steve/b70-optimization-lab
BENCH=${BENCH:-/home/steve/src/llama.cpp-lfm25-work/build-lfm25/bin/llama-bench}
MODEL=/mnt/fast-ai/llm-models/lfm25-24b-a2b-q8-gguf/LFM2.5-24B-A2B-Q8_0.gguf
OUT=${OUT:-/mnt/fast-ai/bench-results/lfm25-24b-a2b/fusion-floor}
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
"$LAB/scripts/gemma4-26b-two-b70-recipe.sh" throughput-card0 2>&1 | grep -v "JSONDecode\|raise " | tail -2

set +u; source /opt/intel/oneapi/setvars.sh --force >/dev/null; set -u
export ONEAPI_DEVICE_SELECTOR=level_zero:1 ZES_ENABLE_SYSMAN=1 UR_L0_ENABLE_RELAXED_ALLOCATION_LIMITS=1 \
  GGML_SYCL_DNNL_DETERMINISTIC=1 GGML_SYCL_DISABLE_OPT=0 GGML_SYCL_PRIORITIZE_DMMV=1 \
  LLAMA_SYCL_DMMV_Q8_0_REORDER_EXACT=4 LLAMA_SYCL_MUL_MAT_ID_Q8_0_REORDER=1 LLAMA_SYCL_MMVQ_ID_XOR_REDUCE=1
bench() { "$BENCH" -m "$MODEL" -ngl 99 -fa 1 -ctk f16 -ctv f16 -b 2048 -ub 512 -t 8 --poll 50 -p 0 -n 128 -r 3 -o json "$@"; }


for set in none fused FLOOR; do
  tag=${set//,/+}
  if [[ $set == none ]]; then
    bench > "$OUT/tg-$tag.json" 2> "$OUT/tg-$tag.err"
  elif [[ $set == fused ]]; then
    LLAMA_SYCL_FUSE_RMS_NORM_MUL=1 LLAMA_SYCL_FUSE_ADD_RMS_NORM_MUL=1 LLAMA_SYCL_FUSE_MOE_SUM=1 \
      LLAMA_SYCL_FUSE_MOE_ROUTE=1 LLAMA_SYCL_FUSE_SHORTCONV=1 LLAMA_SYCL_FUSE_F16_SHADOW=1 LLAMA_SYCL_FUSE_Q8_SHADOW=1 \
      bench > "$OUT/tg-$tag.json" 2> "$OUT/tg-$tag.err"
  else
    LLAMA_SYCL_DIAG_SKIP_OPS=ADD,MUL,RMS_NORM,GET_ROWS,CPY,SWIGLU,SUM_ROWS,SIGMOID,DIV,CLAMP,SSM_CONV,CONCAT,SCALE,ROPE,SET_ROWS \
      bench > "$OUT/tg-$tag.json" 2> "$OUT/tg-$tag.err"
  fi
  python3 -c "
import json,sys
r=json.load(open('$OUT/tg-$tag.json'))[0]
print(f'skip $set: {r[\"avg_ts\"]:.2f} tok/s (sd {r[\"stddev_ts\"]:.2f}), {1000/r[\"avg_ts\"]:.3f} ms/token')
" || { echo "skip $set: FAILED"; tail -3 "$OUT/tg-$tag.err"; }
done
