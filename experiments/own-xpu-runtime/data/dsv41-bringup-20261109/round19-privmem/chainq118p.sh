#!/bin/bash
# 2026-11-16 queue after the tp118p build (privmem-1 + tpd-2): pr6 (memory per block) -> c118p (gate + 194K guessing
# probes + capacity) -> tm1p -> ct1p -> lp1p -> ab2p. A later step starts unless an earlier one stopped on a failed
# preflight or a kernel fault line that is not our own out-of-card-memory.
W=/home/steve/dsv41-work; log=$W/chainq118.txt
say() { echo "$(date '+%F %T') $*" >> $log; sync -f $log; }
while systemctl --user is-active -q build118p; do sleep 20; done
grep -q "tp118p build exit 0" $W/build-tp118p.log || { say "tp118p build failed: $(tail -1 $W/build-tp118p.log)"; exit 1; }
say "tp118p built: $(tail -1 $W/build-tp118p.log)"
python3 -I $W/privmem_check.py $W/own_run_v41_tp118p >> $log 2>&1; sync -f $log
for step in pr6 c118p tm1p ct1p lp1p ab2p; do
  sleep 10
  say "starting $step"
  bash $W/$step.sh
  s=$(ls -td $W/runs/$step-*/ 2>/dev/null | head -1)summary.txt
  say "$step ended: $(tail -1 $s 2>/dev/null | cut -c1-200)"
  if grep -qE "^STOP .*preflight" $s 2>/dev/null; then say "preflight stop in $step: queue stopped"; exit 1; fi
  if grep -qE "^STOP .*kernel:" $s 2>/dev/null && ! grep -q "VM worker error: -12" $s; then say "kernel fault line in $step: queue stopped"; exit 1; fi
done
say "queue done"
