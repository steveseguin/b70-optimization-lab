#!/bin/bash
# chainq124 (2026-11-16, replaces chainq123 before it started anything): after chainq122 (build tp122 -> dtb1 -> c122;
# its ckvs2 / tm1p..ab2p skip on defer-122): tlp2 (reading timelines) -> ckvs2 (kvshard push gate, tp122 if c122
# passed) -> ck1m (first ~1M context, only if ckvs2 passed) -> tm1p -> ct1p -> lp1p -> ab2p. A failed preflight or a
# kernel fault line that is not our own out-of-card-memory stops the queue.
W=/home/steve/dsv41-work; log=$W/chainq118.txt
say() { echo "$(date '+%F %T') $*" >> $log; sync -f $log; }
chk() { local s=$1 st=$2
  if grep -qE "^STOP .*preflight" $s 2>/dev/null; then say "preflight stop in $st: queue stopped"; exit 1; fi
  if grep -qE "^STOP .*kernel:" $s 2>/dev/null && ! grep -q "VM worker error: -12" $s; then say "kernel fault line in $st: queue stopped"; exit 1; fi; }
step() { sleep 10; say "starting $1"; bash $W/$1.sh; local s=$(ls -td $W/runs/$1-*/ 2>/dev/null | head -1)summary.txt
  say "$1 ended: $(tail -1 $s 2>/dev/null | cut -c1-200)"; chk $s $1; }
while systemctl --user is-active -q chainq122 || systemctl --user is-active -q chainq120c; do sleep 20; done
rm -f $W/defer-122
step tlp2
step ckvs2
s=$(ls -td $W/runs/ckvs2-*/ 2>/dev/null | head -1)summary.txt
if grep -q "^ALLDONE" $s 2>/dev/null; then step ck1m; else say "ck1m skipped: ckvs2 did not pass"; fi
for st in tm1p ct1p lp1p ab2p; do step $st; done
say "queue done"
