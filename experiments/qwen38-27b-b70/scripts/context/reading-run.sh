#!/usr/bin/env bash
# MU_RUN_SCRIPT wrapper: the calibrated reading task (sparse prose) with the read-mode agent and its baselines.
# Needs the read-agent patch (arms B32ir / Ar / E32r, KINDS=sparse). Set the calibrated setting first:
#   SPARSE_ARGS="--density 6 --words"  READ_REASONS=0|1   (calibrate-reading.sh prints both)
# One arm group per block, own task directory per setting; `touch $OUT_DIR/STOP` ends it between trials.
#   B32ir  read-mode improved agent (reads each report, STATE.txt name lines, ctxfold --drop name check)
#   Ar     keep everything in the window + window line (baseline)
#   E32r   files allowed, plain agent
#   B32iq  optional (quoted.patch): quoted events, the harness keeps STATE.txt. ARMS="B32iq" (or any arm
#          list) replaces the arm lists of all three blocks.
cd "$(dirname "$0")" || exit 2
TOP=$OUT_DIR
: "${SPARSE_ARGS:?set SPARSE_ARGS to the calibrated setting, e.g. SPARSE_ARGS=\"--density 6 --words\"}"
export SPARSE_ARGS READ_REASONS=${READ_REASONS:-0}
tag=$(echo "$SPARSE_ARGS" | tr -cd 'a-z0-9')
run() { sub=$1; shift; [ -e "$TOP/STOP" ] && { echo "stopped by STOP file"; exit 0; }; echo "### [$sub] $*"; mkdir -p "$TOP/$sub"
        [ -e "$TOP/STOP" ] && touch "$TOP/$sub/STOP"; env "$@" OUT_DIR="$TOP/$sub" SUBSET=core ./second-comparison.sh || echo "### block ended rc=$?"; }
echo "### setting: SPARSE_ARGS=$SPARSE_ARGS READ_REASONS=$READ_REASONS"
A120=${ARMS:-"B32ir Ar E32r"} A480=${ARMS:-B32ir}
run "rd120-$tag" ARMS="$A120" KINDS=sparse SEEDS="0" SIZES=120000
run "rd480-$tag" ARMS="$A480" KINDS=sparse SEEDS="0" SIZES=480000
run "rd120-$tag" ARMS="$A120" KINDS=sparse SEEDS="1" SIZES=120000
