#!/bin/bash
# chainq130 (2026-11-16 22:1x, replaces chainq129 before it started anything): after chainq128 (build tp124 -> tsx2 ->
# c124; its lp1p / ab2p / tm1p skip on defer-122): ck1m2 (700K with kvshard vs the reference; 1M with the task after the
# document; x1m_b vs x1m_a) -> build tp125 (ropedev-1 exact by construction) -> c125 (OWN_ROPE_DEV=1 at 95K / 200K /
# 700K / 1M vs references) -> lp1p -> ab2p -> tm1p. A failed preflight or a kernel fault line that is not our own
# out-of-card-memory stops the queue.
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
step ck1m2
say "chainq130: building tp125"
until [ $(awk '/MemAvailable/ {print int($2/1048576)}' /proc/meminfo) -ge 6 ]; do sleep 10; done
bash $W/build125.sh
say "tp125 built: $(grep -E 'source commit|exit' $W/build-tp125.log | tr '\n' ' ' | cut -c1-300)"
if [ -x $W/own_run_v41_tp125 ] && grep -q "tp125 build exit 0" $W/build-tp125.log; then step c125; else say "tp125 did not build: c125 skipped"; fi
for st in lp1p ab2p tm1p; do step $st; done
say "chainq130 done"
