#!/bin/bash
# packet 90: audio adaLN fusion (five fused sites, bitwise-equal swap verified
# in notes/lossless-floor-and-audio-adaln.md; the warm+endure oracle gates it
# end to end). Same arms as 88: warm, settle, 120-prompt endurance, which also
# keeps the wrong-clip reproduction hunt running. The explicit full-device
# `sync` per arm is dropped (kernel fsyncs git objects itself; forced flushes
# add NVMe burst pressure inside the freeze window). Rest + settle retained.
set -u
R=/mnt/fast-ai/bench-results/ltx25-baseline-20260913
P=$R/prepared-encoder-sentry-90
RUN=$R/encoder-server-sentry-90
LANE=/home/steve/llm-optimizations/experiments/ltx25-b70
REPO=/home/steve/llm-optimizations
PY=/home/steve/.venvs/ltx25-baseline/bin/python
OUT=$LANE/data/sentry-90
mkdir -p "$OUT"
step() { echo "=== $(date -u +%FT%TZ) $*"; }
save() { ( cd $REPO && git add experiments/ltx25-b70/data/sentry-90 && git commit -q -m "LTX packet 90: $1 receipts

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>" && git push -q origin main ) >/dev/null 2>&1 && step "committed $1" || step "commit of $1 failed (continuing)"; }
arm() { # name graph-arm count index-base
  step "$1: arm $2, $3 prompts"
  $PY -B $LANE/scripts/run-throughput-fixtures.py $1 --graph $P/graphs/graph-capture-all48-$2.json \
    --arm $2 --server-run $RUN --count $3 --index-base $4 --out $OUT || { step "$1 failed"; save "$1 (failed)"; exit 1; }
  save "$1"
}
/home/steve/llm-optimizations/scripts/check-b70-runtime-pm.sh || { step "runtime PM unsafe; refusing to run"; exit 1; }
step waiting for server health
for i in $(seq 1 360); do
  [ -f $R/FAULT.json ] && { step FAULT latched; exit 1; }
  curl -sf http://127.0.0.1:8188/queue >/dev/null 2>&1 && break
  sleep 5
done
curl -sf http://127.0.0.1:8188/queue >/dev/null || { step server never answered; exit 1; }
PID=$($PY -c "import json;print(json.load(open('$RUN/server-identity.json'))['pid'])")
step server pid $PID up
# Rest after construction: the 17:26 segfault hit 14 s into warm, right after
# construction's own component loads. Give the machine a quiet minute.
step "rest 60 s after construction"
sleep 60
arm f90-warm pipe-samp2-tsh 3 202989
# Settle gap: the freezes hit at the warm->endure load step-change.
step "settle 60 s between arms"
sleep 60
arm f90-endure pipe-samp2-tsh 120 203089
step campaign complete
