#!/bin/bash
# chainq126 (2026-11-16 20:1x): chainq124b's ckvs2 / ck1m were skipped by mistake (defer-122 was still there), so:
# after chainq125 (its lp1p / ab2p skip on defer-122): ckvs2 (tp123 if c123 passed) -> ck1m (first ~1M context, only
# if ckvs2 passed; tp123 adds idxrp-var.txt's options) -> tm1p (m400chk fixed: OWN_IDX_SPLIT=0) -> lp1p -> ab2p.
# A failed preflight or a kernel fault line that is not our own out-of-card-memory stops the queue.
W=/home/steve/dsv41-work; log=$W/chainq118.txt
say() { echo "$(date '+%F %T') $*" >> $log; sync -f $log; }
chk() { local s=$1 st=$2
  if grep -qE "^STOP .*preflight" $s 2>/dev/null; then say "preflight stop in $st: queue stopped"; exit 1; fi
  if grep -qE "^STOP .*kernel:" $s 2>/dev/null && ! grep -q "VM worker error: -12" $s; then say "kernel fault line in $st: queue stopped"; exit 1; fi; }
step() { sleep 10; say "starting $1"; local t=$(date +%s); bash $W/$1.sh; local s=$(ls -td $W/runs/$1-*/ 2>/dev/null | head -1)summary.txt
  [ $(stat -c %Y $s 2>/dev/null || echo 0) -ge $t ] || { say "$1 ended: no new summary (deferred or did not start)"; return; }
  say "$1 ended: $(tail -1 $s 2>/dev/null | cut -c1-200)"; chk $s $1; }
while systemctl --user is-active -q chainq125; do sleep 20; done
rm -f $W/defer-122
step ckvs2
s=$(ls -td $W/runs/ckvs2-*/ 2>/dev/null | head -1)summary.txt
if grep -q "^ALLDONE" $s 2>/dev/null; then step ck1m; else say "ck1m skipped: ckvs2 did not pass"; fi
for st in tm1p lp1p ab2p; do step $st; done
say "chainq126 done"
