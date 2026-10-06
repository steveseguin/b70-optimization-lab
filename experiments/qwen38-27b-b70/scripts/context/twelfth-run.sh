#!/usr/bin/env bash
# MU_RUN_SCRIPT wrapper: how the reading result scales. Harder reading (6 and 12 changes per batch, numbers as words),
# a stream four times the window (1M tokens), and the files-allowed baseline on the 480K narrative stream.
cd "$(dirname "$0")" || exit 2
TOP=$OUT_DIR
run() { sub=$1; shift; [ -e "$TOP/STOP" ] && { echo "stopped by STOP file"; exit 0; }; echo "### [$sub] $*"; mkdir -p "$TOP/$sub"
        [ -e "$TOP/STOP" ] && touch "$TOP/$sub/STOP"; env "$@" OUT_DIR="$TOP/$sub" SUBSET=core ./second-comparison.sh || echo "### block ended rc=$?"; }
export READ_REASONS=0
SPARSE_ARGS="--density 6 --words"  run rd120-d6  ARMS="B32ir" KINDS=sparse SEEDS="0" SIZES=120000
SPARSE_ARGS="--density 12 --words" run rd120-d12 ARMS="B32ir" KINDS=sparse SEEDS="0" SIZES=120000
SPARSE_ARGS="--density 3 --words"  run rd480-files ARMS="E32r" KINDS=sparse SEEDS="0" SIZES=480000
SPARSE_ARGS="--density 3 --words"  run rd1m ARMS="B32ir" KINDS=sparse SEEDS="0" SIZES=1000000
SPARSE_ARGS="--density 6 --words"  run rd480-d6 ARMS="B32ir" KINDS=sparse SEEDS="0" SIZES=480000
