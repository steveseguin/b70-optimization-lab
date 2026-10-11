#!/usr/bin/env bash
# 16K live-cap baseline campaign (fast scale), 2026-10-10. One-card Qwen3.8-27B FP8 server on port 18196 (max-num-seqs 1,
# so arms run one at a time). History 240K tokens (15x the cap), probes every 25 batches, seed 0.
# Arms: W16 sliding window (lossy), D16 compaction that stubs tool output + strips thinking (lossy),
#       B16ir improved self-editing read mode, B16ira = B16ir + archive-on-drop + recall.
set -uo pipefail
cd /home/steve/b70-optimization-lab/experiments/qwen38-27b-b70/scripts/context || exit 2
export OUT_DIR=${OUT_DIR:-/mnt/fast-ai/bench-results/context-longrun-20261010/client}
export API_BASE=${API_BASE:-http://127.0.0.1:18196/v1}
export MODEL_NAME=${MODEL_NAME:-qwen38-27b-fp8}
export SPARSE_ARGS="--density 3 --words --probes-every 25 --probes-k 3"
export MU_RUN_TIMEOUT=${MU_RUN_TIMEOUT:-7200}
export MAX_TOKENS=${MAX_TOKENS:-8192}   # 16K cap + 8K answer fits the one-card 26,624 window
rm -f "$OUT_DIR/STOP"; mkdir -p "$OUT_DIR"
ARMS_ALL=${ARMS_ALL:-"W16 D16 B16ir B16ira"}
SZ=${SIZES:-240000}; SD=${SEEDS:-0}
echo "### start $(date +%F' '%T) arms=$ARMS_ALL size=$SZ seed=$SD MemAvailable $(awk '/^MemAvailable:/ {printf "%d", $2/1024}' /proc/meminfo) MiB"
echo "### [generate] $(date +%H:%M)"
DRY_RUN=1 ARMS=W16 KINDS=sparse SEEDS="$SD" SIZES="$SZ" SUBSET=core ./second-comparison.sh > "$OUT_DIR/generate.out" 2>&1 || { echo "### generation failed"; tail -5 "$OUT_DIR/generate.out"; exit 2; }
grep -E 'stream_tokens|n_probes|n_items' "$OUT_DIR"/tasks/sparse-memory/sparse-memory-t$((SZ/1000))k-s$SD/task.toml | tr '\n' ' '; echo
for arm in $ARMS_ALL; do
  [ -e "$OUT_DIR/STOP" ] && { echo "### stopped by STOP"; break; }
  echo "### [$arm] start $(date +%H:%M)"
  t0=$SECONDS
  ARMS="$arm" KINDS=sparse SEEDS="$SD" SIZES="$SZ" SUBSET=core ./second-comparison.sh > "$OUT_DIR/arm-$arm.out" 2>&1
  echo "### [$arm] done rc=$? in $(( (SECONDS-t0)/60 )) min $(date +%H:%M)"
  grep -h '^!!!\|score' "$OUT_DIR/arm-$arm.out" | tail -3 | cut -c1-160
  curl -sf -m 10 "$API_BASE/models" >/dev/null || { echo "### server gone"; break; }
done
echo "### [analysis] $(date +%H:%M)"
/mnt/fast-ai/venvs/clm/bin/python ./probe_analysis.py "$OUT_DIR" --json "$OUT_DIR/probe-analysis.json" > "$OUT_DIR/probe-analysis.txt" 2>&1 || echo "### analysis rc=$?"
head -60 "$OUT_DIR/probe-analysis.txt"
echo "### complete $(date +%F' '%T)"
