#!/bin/bash
# tsx1 (2026-11-16): tp123 bench test_index_score_px (idxrp-1: the prompt halves' index score variants, bit for bit
# against IndexerScoreBM + times; PASS (10 cases)) and test_dtopk rebuilt (PASS (441 cases)). dtb1 was: tp122 bench test_dtopk. kvb2 was: tp120 benches, one card: test_kv_push (push layout vs full rows and KvGather; PASS (54 cases)) +
# the kvshard-1 benches rebuilt from tp120. kvb1 was: kvshard step 0, one card (level_zero:1): test_topk_shard (owner-split index top-k vs TopKSelP,
# bitwise) and bench_attn_a1_kvs KVS=1 (attention over KvGather staging vs the full rows, bitwise) at R 64 (default),
# R 8, R 2048 + TT 4096. Each must end PASS. Kernel fault line = STOP. Stable mode, preflight first.
set -u
W=/home/steve/dsv41-work; TS=$(date +%Y%m%dT%H%M); D=$W/runs/tsx1-$TS; mkdir -p $D
sum=$D/summary.txt; say() { echo "$*" >> $sum; sync -f $sum; }
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib
g=$(cat $W/six.active 2>/dev/null); case "$g" in ""|tsx1) ;; *) say "STOP six.active held by $g"; exit 1;; esac
ls $W/locks/ | grep -q . && { say "STOP a lock is held: $(ls $W/locks)"; exit 1; }
echo tsx1 > $W/six.active; sync; trap 'rm -f $W/six.active; sync' EXIT
source $W/stable/stable.env
o=$($W/stable/preflight.sh 2>&1) || { say "STOP preflight: $o"; exit 1; }
J='fault response|cat error|engine reset|coredump has been created|gt reset|timedout job|exec queue reset|suspend fence|vm worker error|reset started|PCIe Bus Error|AER:|Hardware Error|Machine check|watchdog: BUG|AMD-Vi: Event|wedged|GuC'
say "tsx1 start $(date '+%F %T') boot $(cut -c1-8 /proc/sys/kernel/random/boot_id) $(grep "source commit" $W/build-tp123.log | tail -1)"
# b NAME BINARY [VAR=value ...]
b() { local name=$1 bin=$2; shift 2; local t0; t0=$(date '+%F %T')
  env "$@" ONEAPI_DEVICE_SELECTOR=level_zero:1 timeout 1200 $bin > $D/$name.log 2>&1; local rc=$?
  journalctl -k --since "$t0" -o short-precise > $D/$name-kernel.txt 2>&1
  say "$name exit $rc; last: $(tail -1 $D/$name.log | cut -c1-200)"
  grep -h "NO\b\|FAIL\|differ\|MISMATCH" $D/$name.log | head -8 | cut -c1-300 | sed "s/^/$name: /" >> $sum
  f=$(grep -iE "$J" $D/$name-kernel.txt | head -3); [ -n "$f" ] && { say "STOP $name kernel: $f"; exit 1; }
  tail -3 $D/$name.log | grep -q PASS && say "$name PASS" || say "$name NOT PASS"; }
b idxpx $W/test_index_score_px
b dtopk $W/test_dtopk
say "ALLDONE $(date '+%F %T')"
