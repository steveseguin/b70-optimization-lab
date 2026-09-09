#!/usr/bin/env bash
# P1: breadth across the operator's matrix - MTP depth 0-3, concurrency 1-64, context 2K-32K.
# Four single-card arms in parallel. Identity claims only: every arm records speed, no arm's speed
# is a verdict, because three neighbours are holding cards while it runs. Timed rows are re-run
# serially in P2 on a quiet host.
# Gated on P0: if the re-fetched checkpoint did not reproduce the published identity, nothing here
# would mean anything.
set -uo pipefail
REPO=/home/steve/llm-optimizations
H=$REPO/experiments/qwen35-9b-b70/scripts/run-20260909-qwen35-campaign-v3.sh

# Freeze the harness for this run. Bash reads a script incrementally: rewriting the source under a
# live process shifts its read offset and can make it execute garbage. Executing an immutable copy
# means an edit to the source can never reach a running arm.
FROZEN_DIR=/mnt/fast-ai/bench-results/chain-logs/frozen; mkdir -p "$FROZEN_DIR"
FROZEN=$FROZEN_DIR/campaign-v3-$(date +%Y%m%dT%H%M%S)-$$.sh
cp "$H" "$FROZEN"; chmod 0444 "$FROZEN"
echo "$(date -u +%FT%TZ) frozen harness $FROZEN sha256=$(sha256sum "$FROZEN" | cut -d" " -f1)"
H=$FROZEN
LOGDIR=/mnt/fast-ai/bench-results/chain-logs; mkdir -p "$LOGDIR"
LOG=$LOGDIR/q9-p1-chain.log
exec >>"$LOG" 2>&1
echo "=== $(date -u +%FT%TZ) P1 chain start ==="

P0ROOT=/mnt/fast-ai/bench-results/qwen35-9b-w4a16-tp1-mtp3-graph1-dhint4-20260909-p0
echo "$(date -u +%FT%TZ) waiting for P0"
until grep -q P0-CHAIN-DONE "$LOGDIR/q9-p0-chain.log" 2>/dev/null; do sleep 60; done

if [[ -e "$P0ROOT/ABORTED" ]]; then
  echo "P1-ABORT: P0 aborted: $(cat "$P0ROOT/ABORTED")"; echo "P1-CHAIN-DONE"; exit 2
fi
g1=$(grep -o 'G1 mtp0-a vs mtp0-b: [0-9]*/[0-9]*' "$P0ROOT/campaign.log" 2>/dev/null | tail -1 | awk '{print $NF}')
g3=$(grep -o 'G3 mtp3-a vs mtp0-a: [0-9]*/[0-9]*' "$P0ROOT/campaign.log" 2>/dev/null | tail -1 | awk '{print $NF}')
echo "$(date -u +%FT%TZ) P0 gates: G1=${g1:-none} G3=${g3:-none}"
if [[ "$g1" != "12/12" || "$g3" != "12/12" ]]; then
  echo "P1-ABORT: P0 identity gates did not pass (G1=${g1:-none} G3=${g3:-none})"; echo "P1-CHAIN-DONE"; exit 2
fi
echo "$(date -u +%FT%TZ) P0 passed; fanning out four arms"

# arm <run> <depth> <card> <port> <stages>
arm() {
  local run=$1 depth=$2 card=$3 port=$4 stages=$5
  env RUN="$run" LANE=qwen35-9b-w4a16 TP=1 DEPTH="$depth" GRAPH=1 DRAFT_HEAD=1 \
      STAGES="$stages" PORT="$port" XPU_DEVICE_MASK="$card" ARM_DEVICES="$card" \
      MODEL_DIR=/home/steve/llm-models/qwen35-9b-w4a16 \
      MODEL_MANIFEST=$REPO/experiments/qwen35-9b-b70/manifests/model-direct-redhatai-qwen35-9b-w4a16-a398088c.json \
      QUANT=compressed-tensors CAMPAIGN_DATE=20260909 \
      bash "$H" >"$LOGDIR/q9-p1-$run.log" 2>&1
  echo "$(date -u +%FT%TZ) arm $run (depth $depth, card $card) exit $?"
}

arm d1   1 0 18131 "strict ladders" &  p_d1=$!
arm d2   2 1 18132 "strict ladders" &  p_d2=$!
arm d3   3 2 18133 "strict ladders" &  p_d3=$!
arm x32k 3 3 18134 "depth32k"       &  p_x=$!
echo "$(date -u +%FT%TZ) arms launched: d1=$p_d1 d2=$p_d2 d3=$p_d3 x32k=$p_x"

for p in $p_d1 $p_d2 $p_d3 $p_x; do wait "$p"; done
echo "$(date -u +%FT%TZ) all P1 arms finished"
echo "P1-CHAIN-DONE"
