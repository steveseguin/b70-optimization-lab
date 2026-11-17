#!/bin/bash
# chainq143 (2026-11-17): after chainq142 (tp130 + rux9 bench -> c130): build tp131 (b956f44c23: rux9-1 + idxfilt-3,
# the filter bench with TopKSelF's comparison) -> c131. A c130 fault line or failed preflight stops the queue.
W=/home/steve/dsv41-work; log=$W/chainq118.txt
say() { echo "$(date '+%F %T') $*" >> $log; sync -f $log; }
while systemctl --user is-active -q chainq142; do sleep 30; done
s=$(ls -td $W/runs/c130-*/ 2>/dev/null | head -1)summary.txt
say "chainq143: chainq142 ended; c130: $(tail -1 $s 2>/dev/null | cut -c1-200)"
grep -qE "^STOP .*(kernel|preflight)" $s 2>/dev/null && { say "queue stopped: c130 fault / preflight"; exit 1; }
while [ -e $W/six.active ]; do sleep 20; done
say "chainq143: building tp131 (rux9-1 + idxfilt-3)"
bash $W/build131.sh
say "tp131 built: $(grep 'source commit\|bench test_idxfilt' $W/build-tp131.log | tr '\n' ' ' | cut -c1-200); $(grep '^tp131 build exit' $W/build-tp131.log | tail -1)"
grep -q "^tp131 build exit 0" $W/build-tp131.log || { say "chainq143: tp131 did not build: queue stopped for a fix"; exit 1; }
sleep 10; say "starting c131"; bash $W/c131.sh
s=$(ls -td $W/runs/c131-*/ | head -1)summary.txt
say "c131 ended: $(tail -1 $s | cut -c1-200)"
say "chainq143 done"
