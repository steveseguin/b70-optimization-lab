#!/usr/bin/env bash
# MU_RUN_SCRIPT wrapper for the run after the improved agent was written: the improved self-editing arm first, then a
# stream larger than the model's whole window, then the cells the first block did not reach. Same OUT_DIR as the
# second comparison, so finished trials are skipped. `touch $OUT_DIR/STOP` ends it cleanly between trials.
cd "$(dirname "$0")" || exit 2
run() { [ -e "$OUT_DIR/STOP" ] && { echo "stopped by STOP file"; exit 0; }; echo "### $*"; env "$@" SUBSET=core ./second-comparison.sh || echo "### block ended rc=$?"; }
run ARMS="B32i" KINDS=ledger SEEDS="0 1" SIZES=120000
run ARMS="B32i" KINDS=ledger SEEDS="0" SIZES=480000
run ARMS="A" KINDS=ledger SEEDS="1" SIZES=120000
run ARMS="A B32i E32" KINDS=kv SEEDS="0" SIZES=120000
run ARMS="B131i" KINDS=ledger SEEDS="0" SIZES=480000
run ARMS="E32t B32t C32" KINDS=ledger SEEDS="0 1" SIZES=120000
