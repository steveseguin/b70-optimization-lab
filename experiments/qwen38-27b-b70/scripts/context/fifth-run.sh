#!/usr/bin/env bash
# MU_RUN_SCRIPT wrapper for the run after the verified fold and the per-call thinking switch were added (v3):
# the thinking-reduced improved agent first, then the same agent on the 480K stream, then second seeds of the baselines.
# Each block has its own task directory. `touch $OUT_DIR/STOP` ends it cleanly between trials.
cd "$(dirname "$0")" || exit 2
TOP=$OUT_DIR
run() { sub=$1; shift; [ -e "$TOP/STOP" ] && { echo "stopped by STOP file"; exit 0; }; echo "### [$sub] $*"; mkdir -p "$TOP/$sub"
        [ -e "$TOP/STOP" ] && touch "$TOP/$sub/STOP"; env "$@" OUT_DIR="$TOP/$sub" SUBSET=core ./second-comparison.sh || echo "### block ended rc=$?"; }
run led120 ARMS="B32in B32i" KINDS=ledger SEEDS="0 1" SIZES=120000
run big480 ARMS="B32in" KINDS=ledger SEEDS="0" SIZES=480000
run led120 ARMS="E32o B32io" KINDS=ledger SEEDS="0 1" SIZES=120000
run led120 ARMS="E32 D32 C32" KINDS=ledger SEEDS="1" SIZES=120000
run big480 ARMS="B32i" KINDS=ledger SEEDS="0" SIZES=480000
run kv120 ARMS="E32 B32in" KINDS=kv SEEDS="0" SIZES=120000
run led120 ARMS="B32ik" KINDS=ledger SEEDS="0 1" SIZES=120000
