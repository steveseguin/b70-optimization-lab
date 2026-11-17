#!/bin/bash
# chainq142 (2026-11-17): after chainq141 (tp129 build -> c129): build tp130 (13ec276571: idxmem-1 + allocmap-1) and
# the rux9 bench -> c130 (rux9 gate, identity, the 1M memory map, 1M + guessing with every lever). A c129 fault line or
# failed preflight stops the queue; a c129 difference / other STOP does not block tp130's own gates.
W=/home/steve/dsv41-work; log=$W/chainq118.txt
say() { echo "$(date '+%F %T') $*" >> $log; sync -f $log; }
while systemctl --user is-active -q chainq141; do sleep 30; done
s=$(ls -td $W/runs/c129-*/ 2>/dev/null | head -1)summary.txt
say "chainq142: chainq141 ended; c129: $(tail -1 $s 2>/dev/null | cut -c1-200)"
grep -qE "^STOP .*(kernel|preflight)" $s 2>/dev/null && { say "queue stopped: c129 fault / preflight"; exit 1; }
while [ -e $W/six.active ]; do sleep 20; done
say "chainq142: building tp130 + rux9 bench"
bash $W/build130.sh
say "tp130 built: $(grep 'source commit' $W/build-tp130.log | tail -1); $(grep '^tp130 build exit' $W/build-tp130.log | tail -1); $(grep '^rux9 bench build\|^rux9 sendcheck' $W/build-tp130.log | tr '\n' ' ')"
grep -q "^tp130 build exit 0" $W/build-tp130.log || { say "chainq142: tp130 did not build: queue stopped for a fix"; exit 1; }
sleep 10; say "starting c130"; bash $W/c130.sh
s=$(ls -td $W/runs/c130-*/ | head -1)summary.txt
say "c130 ended: $(tail -1 $s | cut -c1-200)"
say "chainq142 done"
