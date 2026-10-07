#!/usr/bin/env bash
# MU_RUN_SCRIPT wrapper: the retention test (sparse prose + hidden questions about earlier items).
# Needs retention.patch (arm B32ira, archive rule class, --surprise, FOLD_BATCHES).
#   B32ir   read-mode agent, table only (cannot answer questions about overwritten values / details)
#   B32ira  read-mode agent + archive-on-drop + `recall` (rule class "archive allowed")
#   C32     summary at 75 % (memory-only)
#   E32r    files allowed, plain agent
#   Ar      keep everything in the window + window line
#   B32iq   optional (quoted.patch): B32ira, but the model sends quoted events to `ctxfold --events` and the
#           harness keeps STATE.txt. ARMS="B32iq" (or any arm list) runs only those arms, in one block.
# SPARSE_ARGS default: the calibrated setting plus 12 retention questions. `touch $OUT_DIR/STOP` ends it.
cd "$(dirname "$0")" || exit 2
TOP=$OUT_DIR
export SPARSE_ARGS=${SPARSE_ARGS:-"--density 3 --words --surprise 12"} READ_REASONS=${READ_REASONS:-0}
run() { sub=$1; shift; [ -e "$TOP/STOP" ] && { echo "stopped by STOP file"; exit 0; }; echo "### [$sub] $*"; mkdir -p "$TOP/$sub"
        [ -e "$TOP/STOP" ] && touch "$TOP/$sub/STOP"; env "$@" OUT_DIR="$TOP/$sub" SUBSET=core ./second-comparison.sh || echo "### block ended rc=$?"; }
echo "### setting: SPARSE_ARGS=$SPARSE_ARGS"
if [ -n "${ARMS:-}" ]; then run ret120 ARMS="$ARMS" KINDS=sparse SEEDS="0" SIZES=120000; exit 0; fi
run ret120 ARMS="B32ira B32ir E32r" KINDS=sparse SEEDS="0" SIZES=120000
run ret120 ARMS="C32 Ar" KINDS=sparse SEEDS="0" SIZES=120000
