#!/bin/bash
# chainq120b (2026-11-16; replaces chainq120 before it started anything; + tlx1 first: long-context writing timelines)
# chainq120 was: after chainq118p (pr6 + c118p; its tm1p..ab2p
# skip on locks/hold-tp119): build tp120 (privmem-1/2 + kvshard-1 + push form; + 3 benches) -> kvb2 (benches, one card)
# -> c120 (shard off: identity + guessing speeds) -> ckvs2 (push-form gate up to 200K, when kvb2 all PASS and c120
# passed) -> tm1p -> ct1p -> lp1p -> ab2p. If tp120 does not build: tp118q + c118q instead. A failed preflight or a
# kernel fault line that is not our own out-of-card-memory stops the queue.
W=/home/steve/dsv41-work; log=$W/chainq118.txt
say() { echo "$(date '+%F %T') $*" >> $log; sync -f $log; }
chk() { local s=$1 st=$2
  if grep -qE "^STOP .*preflight" $s 2>/dev/null; then say "preflight stop in $st: queue stopped"; exit 1; fi
  if grep -qE "^STOP .*kernel:" $s 2>/dev/null && ! grep -q "VM worker error: -12" $s; then say "kernel fault line in $st: queue stopped"; exit 1; fi; }
step() { sleep 10; say "starting $1"; bash $W/$1.sh; local s=$(ls -td $W/runs/$1-*/ 2>/dev/null | head -1)summary.txt
  say "$1 ended: $(tail -1 $s 2>/dev/null | cut -c1-200)"; chk $s $1; }
while systemctl --user is-active -q chainq118p; do sleep 20; done
rm -f $W/locks/hold-tp119
step tlx1
say "chainq120: building tp120"
bash $W/build120.sh
if grep -q "tp120 build exit 0" $W/build-tp120.log; then
  say "tp120 built; $(grep -c 'bench .* built' $W/build-tp120.log) of 3 benches"
  python3 -I $W/privmem_check.py $W/own_run_v41_tp120 2>&1 | head -4 >> $log; sync -f $log
  kv=0
  if [ -x $W/test_kv_push ] && [ -x $W/bench_attn_a1_kvs120 ] && [ -x $W/test_topk_shard120 ]; then
    step kvb2; s=$(ls -td $W/runs/kvb2-*/ | head -1)summary.txt
    say "kvb2: $(grep -c ' PASS$' $s) of 5 PASS"; [ $(grep -c ' PASS$' $s) -eq 5 ] && kv=1
  else say "tp120 benches missing: kvb2 skipped"; fi
  step c120; s=$(ls -td $W/runs/c120-*/ | head -1)summary.txt
  if [ $kv = 1 ] && grep -q "^ALLDONE" $s; then step ckvs2; else say "ckvs2 skipped (kvb2 $kv, c120 $(tail -1 $s | cut -c1-80))"; fi
else
  say "tp120 build failed: $(grep -E ' error' $W/build-tp120.log | head -3 | tr '\n' ' ' | cut -c1-400); building tp118q"
  bash $W/build118q.sh
  grep -q "tp118q build exit 0" $W/build-tp118q.log && { say "tp118q built"; step c118q; } || say "tp118q build failed too"
fi
for st in tm1p ct1p lp1p ab2p; do step $st; done
say "queue done"
