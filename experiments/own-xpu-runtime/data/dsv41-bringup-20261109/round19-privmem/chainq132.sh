#!/bin/bash
# chainq132 (2026-11-16 23:0x): after chainq131 (c125 -> ck1m2; its lp1p / ab2p / tm1p skip on defer-122): build tp126
# (kvdedup-1 + ropedev-1 default) -> c126 -> ab2p -> lp1p -> tm1p. A failed preflight or a kernel fault line that is not
# our own out-of-card-memory stops the queue. tp126 is built only if c125 passed.
W=/home/steve/dsv41-work; log=$W/chainq118.txt
say() { echo "$(date '+%F %T') $*" >> $log; sync -f $log; }
chk() { local s=$1 st=$2
  if grep -qE "^STOP .*preflight" $s 2>/dev/null; then say "preflight stop in $st: queue stopped"; exit 1; fi
  if grep -qE "^STOP .*kernel:" $s 2>/dev/null && ! grep -q "VM worker error: -12" $s; then say "kernel fault line in $st: queue stopped"; exit 1; fi; }
step() { sleep 10; say "starting $1"; local t=$(date +%s); bash $W/$1.sh; local s=$(ls -td $W/runs/$1-*/ 2>/dev/null | head -1)summary.txt
  [ $(stat -c %Y $s 2>/dev/null || echo 0) -ge $t ] || { say "$1 ended: no new summary (deferred or did not start)"; return; }
  say "$1 ended: $(tail -1 $s 2>/dev/null | cut -c1-200)"; chk $s $1; }
while systemctl --user is-active -q chainq131; do sleep 20; done
grep -qE "(preflight stop|kernel fault line) in" <(tail -3 $log) && { say "chainq132: chainq131 stopped on a fault: not starting"; exit 1; }
rm -f $W/defer-122
c125s=$(ls -td $W/runs/c125-*/ 2>/dev/null | head -1)
if [ -n "$c125s" ] && grep -q "^ALLDONE" ${c125s}summary.txt; then
  say "chainq132: building tp126"
  until [ $(awk '/MemAvailable/ {print int($2/1048576)}' /proc/meminfo) -ge 6 ]; do sleep 10; done
  bash $W/build126.sh
  say "tp126 built: $(grep -E 'source commit|exit|failed' $W/build-tp126.log | tr '\n' ' ' | cut -c1-300)"
  if [ -x $W/own_run_v41_tp126 ] && grep -q "tp126 build exit 0" $W/build-tp126.log; then step c126; else say "tp126 did not build: c126 skipped"; fi
else say "chainq132: c125 did not pass: no tp126"; fi
for st in ab2p lp1p tm1p; do step $st; done
say "chainq132 done"
