#!/bin/bash
# chainq131 (2026-11-16 22:1x, replaces chainq130, stopped in its build): build tp125 (3c77277c87 = ropedev-1 exact by
# construction + kvdedup-1; else 7b06b0b089) -> c125 (ropedev at 95K-1M, kvdedup check mode + 194K + 1M) -> ck1m2
# (700K with kvshard vs the reference, 1M with the task after the document, x1m_b; floor 1600) -> lp1p -> ab2p -> tm1p.
# A failed preflight or a kernel fault line that is not our own out-of-card-memory stops the queue.
W=/home/steve/dsv41-work; log=$W/chainq118.txt
say() { echo "$(date '+%F %T') $*" >> $log; sync -f $log; }
chk() { local s=$1 st=$2
  if grep -qE "^STOP .*preflight" $s 2>/dev/null; then say "preflight stop in $st: queue stopped"; exit 1; fi
  if grep -qE "^STOP .*kernel:" $s 2>/dev/null && ! grep -q "VM worker error: -12" $s; then say "kernel fault line in $st: queue stopped"; exit 1; fi; }
step() { sleep 10; say "starting $1"; local t=$(date +%s); bash $W/$1.sh; local s=$(ls -td $W/runs/$1-*/ 2>/dev/null | head -1)summary.txt
  [ $(stat -c %Y $s 2>/dev/null || echo 0) -ge $t ] || { say "$1 ended: no new summary (deferred or did not start)"; return; }
  say "$1 ended: $(tail -1 $s 2>/dev/null | cut -c1-200)"; chk $s $1; }
rm -f $W/defer-122
say "chainq131: building tp125"
until [ $(awk '/MemAvailable/ {print int($2/1048576)}' /proc/meminfo) -ge 6 ]; do sleep 10; done
bash $W/build125.sh
say "tp125 built: $(grep -E 'source commit|exit|failed' $W/build-tp125.log | tr '\n' ' ' | cut -c1-300)"
if [ -x $W/own_run_v41_tp125 ] && grep -q "tp125 build exit 0" $W/build-tp125.log; then step c125; else say "tp125 did not build: c125 skipped"; fi
for st in ck1m2 lp1p ab2p tm1p; do step $st; done
say "chainq131 done"
