#!/usr/bin/env bash
# Round 3 (2026-10-11): seed 1 at the 32K cap (W32 P32 B32ir B32ira) on the 240K sparse stream with probes.
# Two-card Qwen3.8-27B FP8 server on port 18196 (window 65,536). One arm at a time. Expected ~1 h.
set -uo pipefail
cd /home/steve/b70-optimization-lab/experiments/qwen38-27b-b70/scripts/context || exit 2
export OUT_DIR=${OUT_DIR:-/mnt/fast-ai/bench-results/context-longrun-20261010/client}
export API_BASE=${API_BASE:-http://127.0.0.1:18196/v1}
export MODEL_NAME=${MODEL_NAME:-qwen38-27b-fp8}
export SPARSE_ARGS="--density 3 --words --probes-every 25 --probes-k 3"
export MU_RUN_TIMEOUT=${MU_RUN_TIMEOUT:-7200}
export MAX_TOKENS=${MAX_TOKENS:-8192}
rm -f "$OUT_DIR/STOP"; mkdir -p "$OUT_DIR"
SZ=240000
echo "### round3 start $(date +%F' '%T) MemAvailable $(awk '/^MemAvailable:/ {printf "%d", $2/1024}' /proc/meminfo) MiB"
for arm in ${ARMS_ALL:-W32 P32 B32ir B32ira}; do
  [ -e "$OUT_DIR/STOP" ] && { echo "### stopped by STOP"; break; }
  echo "### [$arm s1] start $(date +%H:%M)"
  t0=$SECONDS
  ARMS="$arm" KINDS=sparse SEEDS=1 SIZES="$SZ" SUBSET=core ./second-comparison.sh > "$OUT_DIR/arm-$arm-s1.out" 2>&1
  echo "### [$arm s1] done rc=$? in $(( (SECONDS-t0)/60 )) min $(date +%H:%M)"
  grep -h 'ledger score\|^!!!' "$OUT_DIR/arm-$arm-s1.out" | head -2 | cut -c1-160
  curl -sf -m 10 "$API_BASE/models" >/dev/null || { echo "### server gone"; break; }
done
echo "### [analysis] $(date +%H:%M)"
/mnt/fast-ai/venvs/clm/bin/python ./probe_analysis.py "$OUT_DIR" --json "$OUT_DIR/probe-analysis-round3.json" > "$OUT_DIR/probe-analysis-round3.txt" 2>&1 || echo "### analysis rc=$?"
head -40 "$OUT_DIR/probe-analysis-round3.txt"
echo "### round3 complete $(date +%F' '%T)"
