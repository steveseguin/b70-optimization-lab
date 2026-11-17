#!/bin/bash
# chainq137 (2026-11-17 05:0x; replaces chainq136, which only waited): after chainq135b (c128): build tp129 (the
# filter bench first, then the engine) -> c128b (tp128: idxbc-2 R4 at 194K, then 1M + guessing with c128's exact
# winners) -> c129 (tp129: the filter's bench, dump, check mode, speed). A failed preflight or a kernel fault line
# stops the queue.
W=/home/steve/dsv41-work; log=$W/chainq118.txt
say() { echo "$(date '+%F %T') $*" >> $log; sync -f $log; }
while systemctl --user is-active -q chainq135b; do sleep 20; done
grep -qE "(preflight stop|kernel fault line) in|queue stopped|not starting" <(tail -4 $log) && { say "chainq137: an earlier queue stopped on a fault: not starting"; exit 1; }
say "chainq137: building tp129"
bash $W/build129.sh
say "tp129 built: $(grep 'source commit' $W/build-tp129.log | tail -1) $(grep -c 'bench test_idxfilt_tp129 built' $W/build-tp129.log) bench; $(tail -1 $W/build-tp129.log)"
s=$(ls -td $W/runs/c128-*/ | head -1)summary.txt
if grep -q "^ALLDONE" $s; then
  sleep 10; say "starting c128b"; bash $W/c128b.sh
  s=$(ls -td $W/runs/c128b-*/ | head -1)summary.txt
  say "c128b ended: $(tail -1 $s | cut -c1-200)"
  grep -qE "^STOP .*(kernel|preflight)" $s && { say "queue stopped: c128b fault"; exit 1; }
else
  say "chainq137: c128 did not end ALLDONE: c128b not started"
fi
[ -x $W/own_run_v41_tp129 ] && grep -q "tp129 build exit 0" $W/build-tp129.log || { say "chainq137: no tp129"; exit 1; }
sleep 10; say "starting c129"; bash $W/c129.sh
s=$(ls -td $W/runs/c129-*/ | head -1)summary.txt
say "c129 ended: $(tail -1 $s | cut -c1-200)"
say "chainq137 done"
