#!/bin/bash
# chainq119c (2026-11-16, replaces chainq119b before it started anything; + the tp118q build and its short gate
# c118q first). chainq119b was: the kvshard gate waits for the push form
# (prompt halves read peers' rows in kvshard-1: the reset class); this builds only the benches. Was: queue after chainq118p (pr6 + c118p; its tm1p..ab2p skip on locks/hold-tp119): build tp119 (+ the two
# kvshard benches) -> kvb1 (benches, one card) -> ckvs1 (kvshard gate, up to 200K) -> tm1p -> ct1p -> lp1p -> ab2p.
# ckvs1 runs only when every bench passed. A step's failed preflight or a kernel fault line that is not our own
# out-of-card-memory stops the queue.
W=/home/steve/dsv41-work; log=$W/chainq118.txt
say() { echo "$(date '+%F %T') $*" >> $log; sync -f $log; }
while systemctl --user is-active -q chainq118p; do sleep 20; done
rm -f $W/locks/hold-tp119
say "chainq119c: building tp118q"
bash $W/build118q.sh
grep -q "tp118q build exit 0" $W/build-tp118q.log && say "tp118q built" || say "tp118q build failed: $(grep -E 'error' $W/build-tp118q.log | head -3 | tr '\n' ' ' | cut -c1-300)"
python3 -I $W/privmem_check.py $W/own_run_v41_tp118q 2>&1 | head -2 >> $log; sync -f $log
say "chainq119c: building the kvshard benches"
bash $W/bench119.sh
say "benches: $(grep -c 'bench .* built' $W/build-bench119.log) of 2 built"
chk() { local s=$1 st=$2
  if grep -qE "^STOP .*preflight" $s 2>/dev/null; then say "preflight stop in $st: queue stopped"; exit 1; fi
  if grep -qE "^STOP .*kernel:" $s 2>/dev/null && ! grep -q "VM worker error: -12" $s; then say "kernel fault line in $st: queue stopped"; exit 1; fi; }
steps="tm1p ct1p lp1p ab2p"; [ -x $W/own_run_v41_tp118q ] && grep -q "tp118q build exit 0" $W/build-tp118q.log && steps="c118q $steps"
if [ -x $W/test_topk_shard ] && [ -x $W/bench_attn_a1_kvs ]; then
  sleep 10; say "starting kvb1"; bash $W/kvb1.sh
  s=$(ls -td $W/runs/kvb1-*/ | head -1)summary.txt; say "kvb1 ended: $(grep -c ' PASS$' $s) PASS, $(grep -c 'NOT PASS' $s) not; $(tail -1 $s | cut -c1-150)"
  chk $s kvb1
  [ $(grep -c ' PASS$' $s) -eq 4 ] || say "kvb1: not every bench passed"
else say "benches missing: kvb1 skipped"; fi
for step in $steps; do
  sleep 10; say "starting $step"; bash $W/$step.sh
  s=$(ls -td $W/runs/$step-*/ 2>/dev/null | head -1)summary.txt
  say "$step ended: $(tail -1 $s 2>/dev/null | cut -c1-200)"; chk $s $step
done
say "queue done"
