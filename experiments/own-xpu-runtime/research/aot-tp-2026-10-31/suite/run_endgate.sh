#!/usr/bin/env bash
# The end gate of research/aot-tp-2026-10-31 (step 3): three chains in one unit, each its own suite.sh with its own lock set.
#  1. four cards at 65536, A/B/A/B: hspJ-r1 (JIT r1), hspA-r1 (AOT), hspJ-r2, hspA-r2; both arms --wait-seconds 300.
#  2. two cards at 65536 (cards 23 + 47): twoBJ-r1 (JIT r1), twoBA-r1 (AOT); both --wait-seconds 300.
#  3. four cards at 131072: hspA60-r1, the AOT build with the ranks' default 60 s --wait-seconds (the deadline JIT
#     server fc2-r3-c131072 of hc-split-2026-10-30 halted on), then the 121,854/512 long request.
# A chain whose servers did not all finish ends the end gate (nothing is retried). Usage: run_endgate.sh (no arguments).
set -u
D=$(cd "$(dirname "$0")" && pwd)
RJ=/home/steve/llm-optimizations/experiments/own-xpu-runtime/research/tp/hc-split-2026-10-30/results/engine-receipt-40388fc92c43.json
RA=$(dirname "$D")/results/engine-receipt-a1959e7ccf88.json
ok() { for n in "$@"; do [ "$(cat "$D/logs/STATUS-$n" 2>/dev/null)" = "done $n" ] || return 1; done; }
LOCKS="23 27 43 47" HOLD_WAIT=7200 bash "$D/suite.sh" "$RA" "hspJ-r1:65536::$RJ" "hspA-r1:65536::$RA" "hspJ-r2:65536::$RJ" "hspA-r2:65536::$RA"
ok hspJ-r1-c65536 hspA-r1-c65536 hspJ-r2-c65536 hspA-r2-c65536 || { echo "four-card chain incomplete: end gate stops" >>"$D/logs/suite.log"; exit 1; }
LOCKS="23 47" HOLD_WAIT=3600 bash "$D/suite.sh" "$RA" "twoBJ-r1:65536::$RJ" "twoBA-r1:65536::$RA"
ok twoBJ-r1-c65536 twoBA-r1-c65536 || { echo "two-card chain incomplete: end gate stops" >>"$D/logs/suite.log"; exit 1; }
LOCKS="23 27 43 47" HOLD_WAIT=3600 bash "$D/suite.sh" "$RA" "hspA60-r1:131072::$RA"
echo "end gate finished: hspA60-r1-c131072 $(cat "$D/logs/STATUS-hspA60-r1-c131072" 2>/dev/null)" >>"$D/logs/suite.log"
