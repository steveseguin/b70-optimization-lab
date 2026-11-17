#!/bin/bash
# chainq134 (2026-11-17 01:2x): after chainq133 (ck1m3; its ab2p / lp1p / tm1p skip on defer-122): build tp127
# (af53c5d4d6: hostfloor-2 + idxbc-1 default) -> c127 (gate + 1M read) -> ab2p -> lp1p -> tm1p. A failed preflight or
# a kernel fault line that is not our own out-of-card-memory stops the queue.
W=/home/steve/dsv41-work; log=$W/chainq118.txt
say() { echo "$(date '+%F %T') $*" >> $log; sync -f $log; }
chk() { local s=$1 st=$2
  if grep -qE "^STOP .*preflight" $s 2>/dev/null; then say "preflight stop in $st: queue stopped"; exit 1; fi
  if grep -qE "^STOP .*kernel:" $s 2>/dev/null && ! grep -q "VM worker error: -12" $s; then say "kernel fault line in $st: queue stopped"; exit 1; fi; }
step() { sleep 10; say "starting $1"; local t=$(date +%s); bash $W/$1.sh; local s=$(ls -td $W/runs/$1-*/ 2>/dev/null | head -1)summary.txt
  [ $(stat -c %Y $s 2>/dev/null || echo 0) -ge $t ] || { say "$1 ended: no new summary (deferred or did not start)"; return; }
  say "$1 ended: $(tail -1 $s 2>/dev/null | cut -c1-200)"; chk $s $1; }
while systemctl --user is-active -q chainq133; do sleep 20; done
grep -qE "(preflight stop|kernel fault line) in|queue stopped|not starting" <(tail -3 $log) && { say "chainq134: an earlier queue stopped on a fault: not starting"; exit 1; }
say "chainq134: building tp127"
bash $W/build127.sh
say "tp127 built: $(grep 'source commit' $W/build-tp127.log | tail -1) $(tail -1 $W/build-tp127.log)"
[ -x $W/own_run_v41_tp127 ] && grep -q "tp127 build exit 0" $W/build-tp127.log && step c127
rm -f $W/defer-122
for st in ab2p lp1p tm1p; do step $st; done
say "chainq134 done"
