#!/bin/bash
# chainq122 (2026-11-16): after chainq120c (c120 -> ew1; its ckvs2 / tm1p..ab2p skip on defer-120c): build tp122
# (tp121 9bc805e72a: dtopk-1 + eng-warm-1 / eng-spread-1 + hostmem-1, -exclude_ir) -> kernel code compare against tp120
# -> dtb1 (test_dtopk, one card) -> c122 (dtopk gate) -> the deferred ckvs2, tm1p, ct1p, lp1p, ab2p. A failed preflight
# or a kernel fault line that is not our own out-of-card-memory stops the queue.
W=/home/steve/dsv41-work; log=$W/chainq118.txt
say() { echo "$(date '+%F %T') $*" >> $log; sync -f $log; }
chk() { local s=$1 st=$2
  if grep -qE "^STOP .*preflight" $s 2>/dev/null; then say "preflight stop in $st: queue stopped"; exit 1; fi
  if grep -qE "^STOP .*kernel:" $s 2>/dev/null && ! grep -q "VM worker error: -12" $s; then say "kernel fault line in $st: queue stopped"; exit 1; fi; }
step() { sleep 10; say "starting $1"; bash $W/$1.sh; local s=$(ls -td $W/runs/$1-*/ 2>/dev/null | head -1)summary.txt
  say "$1 ended: $(tail -1 $s 2>/dev/null | cut -c1-200)"; chk $s $1; }
while systemctl --user is-active -q chainq120c; do sleep 20; done
rm -f $W/defer-120c
say "chainq122: building tp122"
bash $W/build122.sh
if grep -q "tp122 build exit 0" $W/build-tp122.log; then
  say "tp122 built"
  python3 -I $W/privmem_check.py $W/own_run_v41_tp122 2>&1 | head -6 >> $log
  python3 -I $W/hostmem/zebin_sizes.py $W/own_run_v41_tp120 $W/own_run_v41_tp122 > $W/hostmem/zebin-tp120-tp122.txt 2>&1
  say "zebin compare tp120 -> tp122: $(tail -3 $W/hostmem/zebin-tp120-tp122.txt | tr '\n' ' ' | cut -c1-300)"
  ok=1
  if [ -x $W/test_dtopk ]; then step dtb1; s=$(ls -td $W/runs/dtb1-*/ | head -1)summary.txt; grep -q "dtopk PASS" $s || ok=0; else ok=0; say "test_dtopk missing"; fi
  if [ $ok = 1 ]; then step c122; else say "c122 skipped: the bench did not pass"; fi
else
  say "tp122 build failed: $(grep -E ' error' $W/build-tp122.log | head -3 | tr '\n' ' ' | cut -c1-400)"
fi
for st in ckvs2 tm1p ct1p lp1p ab2p; do step $st; done
say "queue done"
