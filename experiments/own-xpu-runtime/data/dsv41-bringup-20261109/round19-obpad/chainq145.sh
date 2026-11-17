#!/bin/bash
# chainq145 (2026-11-17): after chainq144 (tp132 -> c132): build tp133s (c518f25807 klazy-1, split per kernel) -> c133.
# A c132 fault line or failed preflight stops the queue; a c132 difference / other STOP does not.
W=/home/steve/dsv41-work; log=$W/chainq118.txt
say() { echo "$(date '+%F %T') $*" >> $log; sync -f $log; }
while systemctl --user is-active -q chainq144; do sleep 30; done
s=$(ls -td $W/runs/c132-*/ 2>/dev/null | head -1)summary.txt
say "chainq145: chainq144 ended; c132: $(tail -1 $s 2>/dev/null | cut -c1-200)"
grep -qE "^STOP .*(kernel|preflight)" $s 2>/dev/null && { say "queue stopped: c132 fault / preflight"; exit 1; }
while [ -e $W/six.active ]; do sleep 20; done
say "chainq145: building tp133s (klazy-1, split per kernel)"
bash $W/build133.sh
say "tp133s built: $(grep '^tp133 build exit\|^tp133s:' $W/build-tp133.log | tr '\n' ' ' | cut -c1-250)"
grep -q "^tp133 build exit 0" $W/build-tp133.log || { say "chainq145: tp133s did not build: queue stopped for a fix"; exit 1; }
sleep 10; say "starting c133"; bash $W/c133.sh
s=$(ls -td $W/runs/c133-*/ | head -1)summary.txt
say "c133 ended: $(tail -1 $s | cut -c1-200)"
say "chainq145 done"
