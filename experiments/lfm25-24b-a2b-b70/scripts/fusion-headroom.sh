#!/usr/bin/env bash
# Fusion headroom probe (registered in notes/2026-10-14-lfm25-24b-a2b-bringup.md, 2026-10-15 08:43). DIAGNOSTIC ONLY:
# LLAMA_SYCL_DIAG_SKIP_OPS skips op types, so outputs are wrong; only decode timing is read. Card 1, Gemma on card 0.
#   fusion-headroom.sh            (SUDO_ASKPASS set; run under systemd-run --user)
set -uo pipefail
LAB=/home/steve/b70-optimization-lab
BENCH=${BENCH:-/home/steve/src/llama.cpp-lfm25-work/build-lfm25/bin/llama-bench}
MODEL=/mnt/fast-ai/llm-models/lfm25-24b-a2b-q8-gguf/LFM2.5-24B-A2B-Q8_0.gguf
OUT=${OUT:-/mnt/fast-ai/bench-results/lfm25-24b-a2b/fusion-headroom}
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

log "node profile pass (kernel counts per op type)"
GGML_SYCL_NODE_PROFILE=1 GGML_SYCL_NODE_PROFILE_EVERY=64 GGML_SYCL_NODE_PROFILE_TOP=5000 \
  "$BENCH" -m "$MODEL" -ngl 99 -fa 1 -ctk f16 -ctv f16 -t 8 --poll 50 -p 0 -n 64 -r 1 -o json \
  > "$OUT/profile.json" 2> "$OUT/profile.err"
echo "profile rc=$?"

for set in none MUL ADD RMS_NORM MUL,ADD,RMS_NORM GLU,SWIGLU SSM_CONV,CONCAT,CPY GET_ROWS,SUM_ROWS,DIV; do
  tag=${set//,/+}
  if [[ $set == none ]]; then
    bench > "$OUT/tg-$tag.json" 2> "$OUT/tg-$tag.err"
  else
    LLAMA_SYCL_DIAG_SKIP_OPS=$set bench > "$OUT/tg-$tag.json" 2> "$OUT/tg-$tag.err"
  fi
  python3 -c "
import json,sys
r=json.load(open('$OUT/tg-$tag.json'))[0]
print(f'skip $set: {r[\"avg_ts\"]:.2f} tok/s (sd {r[\"stddev_ts\"]:.2f}), {1000/r[\"avg_ts\"]:.3f} ms/token')
" || { echo "skip $set: FAILED"; tail -3 "$OUT/tg-$tag.err"; }
done
