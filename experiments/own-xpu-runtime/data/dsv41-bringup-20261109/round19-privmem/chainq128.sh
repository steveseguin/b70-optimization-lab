#!/bin/bash
# chainq128 (2026-11-16 21:1x): after chainq127 (ck1m; its lp1p / ab2p skip on defer-122): build tp124 (idxrp-1 default,
# hostfloor-1, bench test_rope_fill) -> tsx2 (rope bench, one card) -> c124 (gate) -> lp1p -> ab2p -> tm1p (m400chk
# dropped). A failed preflight or a kernel fault line that is not our own out-of-card-memory stops the queue.
W=/home/steve/dsv41-work; log=$W/chainq118.txt
say() { echo "$(date '+%F %T') $*" >> $log; sync -f $log; }
chk() { local s=$1 st=$2
  if grep -qE "^STOP .*preflight" $s 2>/dev/null; then say "preflight stop in $st: queue stopped"; exit 1; fi
  if grep -qE "^STOP .*kernel:" $s 2>/dev/null && ! grep -q "VM worker error: -12" $s; then say "kernel fault line in $st: queue stopped"; exit 1; fi; }
step() { sleep 10; say "starting $1"; local t=$(date +%s); bash $W/$1.sh; local s=$(ls -td $W/runs/$1-*/ 2>/dev/null | head -1)summary.txt
  [ $(stat -c %Y $s 2>/dev/null || echo 0) -ge $t ] || { say "$1 ended: no new summary (deferred or did not start)"; return; }
  say "$1 ended: $(tail -1 $s 2>/dev/null | cut -c1-200)"; chk $s $1; }
while systemctl --user is-active -q chainq127; do sleep 20; done
rm -f $W/defer-122
say "chainq128: building tp124"
until [ $(awk '/MemAvailable/ {print int($2/1048576)}' /proc/meminfo) -ge 6 ]; do sleep 10; done
bash $W/build124.sh
say "tp124 built: $(grep -E 'source commit|bench|exit' $W/build-tp124.log | tr '\n' ' ' | cut -c1-300)"
if [ -x $W/own_run_v41_tp124 ] && grep -q "tp124 build exit 0" $W/build-tp124.log; then
  [ -x $W/test_rope_fill ] && step tsx2
  step c124
else
  say "tp124 did not build: c124 skipped"
fi
for st in lp1p ab2p tm1p; do step $st; done
say "chainq128 done"
