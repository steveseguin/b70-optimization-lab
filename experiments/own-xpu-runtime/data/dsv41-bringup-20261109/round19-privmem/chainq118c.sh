#!/bin/bash
# 2026-11-16 queue after pr4's ENOMEM stop: pr5 (card memory per block) -> c118 -> tm1 -> ct1 -> lp1 -> ab2. A later step
# starts unless an earlier one stopped on a failed preflight or a kernel fault line that is not our own out-of-card-
# memory (xe "VM worker error: -12" with its exec queue resets = our software fault: recorded, the queue goes on).
W=/home/steve/dsv41-work; log=$W/chainq118.txt
say() { echo "$(date '+%F %T') $*" >> $log; sync -f $log; }
for step in pr5 c118 tm1 ct1 lp1 ab2; do
  sleep 10
  say "starting $step"
  bash $W/$step.sh
  s=$(ls -td $W/runs/$step-*/ 2>/dev/null | head -1)summary.txt
  say "$step ended: $(tail -1 $s 2>/dev/null | cut -c1-200)"
  if grep -qE "^STOP .*preflight" $s 2>/dev/null; then say "preflight stop in $step: queue stopped"; exit 1; fi
  if grep -qE "^STOP .*kernel:" $s 2>/dev/null && ! grep -q "VM worker error: -12" $s; then say "kernel fault line in $step: queue stopped"; exit 1; fi
done
say "queue done"
