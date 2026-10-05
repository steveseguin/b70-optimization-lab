#!/usr/bin/env bash
# MU_RUN_SCRIPT wrapper: the stream larger than the model's whole window (480K tokens of input, 262K window), then
# the cells still missing. Each size gets its own task directory, because second-comparison.sh generates a task
# directory once (the 480K blocks of third-run.sh found no tasks for that reason).
# `touch $OUT_DIR/STOP` ends it cleanly between trials.
cd "$(dirname "$0")" || exit 2
TOP=$OUT_DIR
run() { sub=$1; shift; [ -e "$TOP/STOP" ] && { echo "stopped by STOP file"; exit 0; }; echo "### [$sub] $*"; mkdir -p "$TOP/$sub"
        [ -e "$TOP/STOP" ] && touch "$TOP/$sub/STOP"; env "$@" OUT_DIR="$TOP/$sub" SUBSET=core ./second-comparison.sh || echo "### block ended rc=$?"; }
run big480 ARMS="B32i" KINDS=ledger SEEDS="0" SIZES=480000
run big480 ARMS="E32 D32" KINDS=ledger SEEDS="0" SIZES=480000
run kv120 ARMS="E32 A B32i" KINDS=kv SEEDS="0" SIZES=120000
run big480 ARMS="B131i" KINDS=ledger SEEDS="0" SIZES=480000
run led120 ARMS="E32t C32" KINDS=ledger SEEDS="0 1" SIZES=120000
