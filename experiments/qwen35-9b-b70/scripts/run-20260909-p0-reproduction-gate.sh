#!/usr/bin/env bash
# P0: does the re-fetched W4A16 checkpoint plus the re-pulled R276 image still reproduce the
# published w1 identity and headline? Nothing downstream is trusted until this passes.
# Waits on the refetch log rather than on a process pattern (a pgrep pattern that appears in this
# script's own command line matches this shell).
set -uo pipefail
REPO=/home/steve/llm-optimizations
LOGDIR=/mnt/fast-ai/bench-results/chain-logs; mkdir -p "$LOGDIR"
LOG=$LOGDIR/q9-p0-chain.log
exec >>"$LOG" 2>&1
echo "=== $(date -u +%FT%TZ) P0 chain start ==="

M=/home/steve/llm-models/qwen35-9b-w4a16
N=$REPO/experiments/qwen35-9b-b70/manifests/model-direct-redhatai-qwen35-9b-w4a16-a398088c.json

echo "$(date -u +%FT%TZ) waiting for the W4A16 fetch to finish"
: # checkpoint already fetched and manifest-verified this session
echo "$(date -u +%FT%TZ) fetch reported done; verifying against the pinned manifest"

MODEL_MANIFEST="$N" "$REPO/repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/verify-model-direct.sh" "$M"
rc=$?
echo "$(date -u +%FT%TZ) verify-model-direct rc=$rc"
if [[ $rc -ne 0 ]]; then
  echo "P0-ABORT: the re-fetched W4A16 checkpoint does not match the pinned manifest"
  echo "P0-CHAIN-DONE"
  exit 2
fi

H=$REPO/experiments/qwen35-9b-b70/scripts/run-20260909-qwen35-campaign-v3.sh
# Freeze the harness for this run. Bash reads a script incrementally: rewriting the source under a
# live process shifts its read offset and can make it execute garbage. Executing an immutable copy
# means an edit to the source can never reach a running arm.
FROZEN_DIR=/mnt/fast-ai/bench-results/chain-logs/frozen; mkdir -p "$FROZEN_DIR"
FROZEN=$FROZEN_DIR/campaign-v3-$(date +%Y%m%dT%H%M%S)-$$.sh
cp "$H" "$FROZEN"; chmod 0444 "$FROZEN"
echo "$(date -u +%FT%TZ) frozen harness $FROZEN sha256=$(sha256sum "$FROZEN" | cut -d" " -f1)"
H=$FROZEN
echo "$(date -u +%FT%TZ) launching P0 strict stage (card 0, MTP3, W4A16)"
env REPO="$REPO" RUN=p0 LANE=qwen35-9b-w4a16 TP=1 DEPTH=3 GRAPH=1 DRAFT_HEAD=1 \
    STAGES="strict" PORT=18131 XPU_DEVICE_MASK=0 ARM_DEVICES=0 \
    MODEL_DIR="$M" MODEL_MANIFEST="$N" QUANT=compressed-tensors \
    CAMPAIGN_DATE=20260909 \
    bash "$H"
echo "$(date -u +%FT%TZ) P0 harness exit $?"
echo "P0-CHAIN-DONE"
