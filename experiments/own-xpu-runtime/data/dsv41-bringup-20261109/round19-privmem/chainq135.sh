#!/bin/bash
# chainq135 (2026-11-17 03:xx): after chainq134c (c127 -> ab2p -> lp1p -> tm1p, skipped): build tp128 (dtopk-2 on by
# default + the batched form, opt-in) -> c128, only when c127 passed (ALLDONE, dtopk-2 check PASS at 194K). A failed
# preflight or a kernel fault line that is not our own out-of-card-memory stops the queue.
W=/home/steve/dsv41-work; log=$W/chainq118.txt
say() { echo "$(date '+%F %T') $*" >> $log; sync -f $log; }
while systemctl --user is-active -q chainq134c; do sleep 20; done
grep -qE "(preflight stop|kernel fault line) in|queue stopped|not starting" <(tail -4 $log) && { say "chainq135: an earlier queue stopped on a fault: not starting"; exit 1; }
c127s=$(ls -td $W/runs/c127-*/ | head -1)summary.txt
grep -q "^ALLDONE" $c127s && grep -q "dtopk-2 check at 194K: PASS" $c127s || { say "chainq135: c127 did not pass (no ALLDONE / dtopk-2 PASS): tp128 not built"; exit 1; }
say "chainq135: building tp128"
bash $W/build128.sh
say "tp128 built: $(grep 'source commit' $W/build-tp128.log | tail -1) $(tail -1 $W/build-tp128.log)"
[ -x $W/own_run_v41_tp128 ] && grep -q "tp128 build exit 0" $W/build-tp128.log || { say "chainq135: no tp128"; exit 1; }
sleep 10; say "starting c128"; bash $W/c128.sh
s=$(ls -td $W/runs/c128-*/ | head -1)summary.txt
say "c128 ended: $(tail -1 $s | cut -c1-200)"
say "chainq135 done"
