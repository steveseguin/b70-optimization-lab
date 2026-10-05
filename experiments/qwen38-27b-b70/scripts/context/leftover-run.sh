#!/usr/bin/env bash
# MU_RUN_SCRIPT wrapper (or called by another wrapper): ledger cells still missing after the reading run.
# One arm per block; own task directory per block. `touch $OUT_DIR/STOP` ends it cleanly between trials.
cd "$(dirname "$0")" || exit 2
TOP=$OUT_DIR
run() { sub=$1; shift; [ -e "$TOP/STOP" ] && { echo "stopped by STOP file"; exit 0; }; echo "### [$sub] $*"; mkdir -p "$TOP/$sub"
        [ -e "$TOP/STOP" ] && touch "$TOP/$sub/STOP"; env "$@" OUT_DIR="$TOP/$sub" SUBSET=core ./second-comparison.sh || echo "### block ended rc=$?"; }
run big480 ARMS="B32in" KINDS=ledger SEEDS="0" SIZES=480000
run led120 ARMS="E32o" KINDS=ledger SEEDS="0 1" SIZES=120000
run led120 ARMS="B32io" KINDS=ledger SEEDS="0 1" SIZES=120000
run led120 ARMS="E32 D32" KINDS=ledger SEEDS="1" SIZES=120000
run led120 ARMS="B32i" KINDS=ledger SEEDS="0 1" SIZES=120000
run led120 ARMS="C32" KINDS=ledger SEEDS="1" SIZES=120000
run kv120 ARMS="B32in" KINDS=kv SEEDS="0" SIZES=120000
