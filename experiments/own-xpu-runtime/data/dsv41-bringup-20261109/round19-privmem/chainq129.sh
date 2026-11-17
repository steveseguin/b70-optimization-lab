#!/bin/bash
# chainq129 (2026-11-16 21:4x): after chainq128 (build tp124 -> tsx2 -> c124; its lp1p / ab2p / tm1p skip on
# defer-122): ck1m2 (700K with kvshard against the reference; 1M with the task after the document; x1m_b vs x1m_a) ->
# lp1p -> ab2p -> tm1p. A failed preflight or a kernel fault line that is not our own out-of-card-memory stops the queue.
W=/home/steve/dsv41-work; log=$W/chainq118.txt
say() { echo "$(date '+%F %T') $*" >> $log; sync -f $log; }
chk() { local s=$1 st=$2
  if grep -qE "^STOP .*preflight" $s 2>/dev/null; then say "preflight stop in $st: queue stopped"; exit 1; fi
  if grep -qE "^STOP .*kernel:" $s 2>/dev/null && ! grep -q "VM worker error: -12" $s; then say "kernel fault line in $st: queue stopped"; exit 1; fi; }
step() { sleep 10; say "starting $1"; local t=$(date +%s); bash $W/$1.sh; local s=$(ls -td $W/runs/$1-*/ 2>/dev/null | head -1)summary.txt
  [ $(stat -c %Y $s 2>/dev/null || echo 0) -ge $t ] || { say "$1 ended: no new summary (deferred or did not start)"; return; }
  say "$1 ended: $(tail -1 $s 2>/dev/null | cut -c1-200)"; chk $s $1; }
while systemctl --user is-active -q chainq128; do sleep 20; done
rm -f $W/defer-122
for st in ck1m2 lp1p ab2p tm1p; do step $st; done
say "chainq129 done"
