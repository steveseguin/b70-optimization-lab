#!/bin/bash
# chainq144 (2026-11-17): after chainq143 (tp131 -> c131): build tp132 (0c13b65e7e: obpad-1 + ifldiag-1c, the obpad
# bench) -> c132. A c131 fault line or failed preflight stops the queue; a c131 difference / other STOP does not.
W=/home/steve/dsv41-work; log=$W/chainq118.txt
say() { echo "$(date '+%F %T') $*" >> $log; sync -f $log; }
while systemctl --user is-active -q chainq143; do sleep 30; done
s=$(ls -td $W/runs/c131-*/ 2>/dev/null | head -1)summary.txt
say "chainq144: chainq143 ended; c131: $(tail -1 $s 2>/dev/null | cut -c1-200)"
grep -qE "^STOP .*(kernel|preflight)" $s 2>/dev/null && { say "queue stopped: c131 fault / preflight"; exit 1; }
while [ -e $W/six.active ]; do sleep 20; done
say "chainq144: building tp132 (obpad-1 + ifldiag-1c)"
bash $W/build132.sh
say "tp132 built: $(grep 'source commit' $W/build-tp132.log | tr '\n' ' ' | cut -c1-120); $(grep '^tp132 build exit\|^obpad bench build' $W/build-tp132.log | tr '\n' ' ')"
grep -q "^tp132 build exit 0" $W/build-tp132.log || { say "chainq144: tp132 did not build: queue stopped for a fix"; exit 1; }
sleep 10; say "starting c132"; bash $W/c132.sh
s=$(ls -td $W/runs/c132-*/ | head -1)summary.txt
say "c132 ended: $(tail -1 $s | cut -c1-200)"
say "chainq144 done"
