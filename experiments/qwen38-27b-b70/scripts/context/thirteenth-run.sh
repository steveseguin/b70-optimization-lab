#!/usr/bin/env bash
# MU_RUN_SCRIPT wrapper after the 23:08 guard kill: the retention run, then the scaling run, then the ledger cells
# the eleventh run did not reach. Each part keeps its own STOP handling.
cd "$(dirname "$0")" || exit 2
TOP=$OUT_DIR
bash ./retention-run.sh
bash ./twelfth-run.sh
run() { sub=$1; shift; [ -e "$TOP/STOP" ] && { echo "stopped by STOP file"; exit 0; }; echo "### [$sub] $*"; mkdir -p "$TOP/$sub"
        [ -e "$TOP/STOP" ] && touch "$TOP/$sub/STOP"; env "$@" OUT_DIR="$TOP/$sub" SUBSET=core ./second-comparison.sh || echo "### block ended rc=$?"; }
export SPARSE_ARGS="--density 3 --words" READ_REASONS=0
run led120 ARMS="Aw" KINDS=ledger SEEDS="1" SIZES=120000
run rd120 ARMS="E32r Ar" KINDS=sparse SEEDS="1" SIZES=120000
run rd480 ARMS="B32ir" KINDS=sparse SEEDS="1" SIZES=480000
bash ./leftover2-run.sh
