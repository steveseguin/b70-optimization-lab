#!/bin/bash
# chainq136 (2026-11-17 04:4x): after chainq135b (build tp128 -> c128): c128b (idxbc-2 in its fastest form at 194K, then
# 1M + guessing with every exact lever that was cheaper per check cycle), only when c128 ended ALLDONE. A failed
# preflight or a kernel fault line stops the queue.
W=/home/steve/dsv41-work; log=$W/chainq118.txt
say() { echo "$(date '+%F %T') $*" >> $log; sync -f $log; }
while systemctl --user is-active -q chainq135b; do sleep 20; done
grep -qE "(preflight stop|kernel fault line) in|queue stopped|not starting" <(tail -4 $log) && { say "chainq136: an earlier queue stopped on a fault: not starting"; exit 1; }
s=$(ls -td $W/runs/c128-*/ | head -1)summary.txt
grep -q "^ALLDONE" $s || { say "chainq136: c128 did not end ALLDONE: c128b not started"; exit 1; }
sleep 10; say "starting c128b"; bash $W/c128b.sh
s=$(ls -td $W/runs/c128b-*/ | head -1)summary.txt
say "c128b ended: $(tail -1 $s | cut -c1-200)"
say "chainq136 done"
