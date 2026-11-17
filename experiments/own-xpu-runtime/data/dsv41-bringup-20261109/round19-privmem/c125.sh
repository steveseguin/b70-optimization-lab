#!/bin/bash
# c125 (2026-11-16): gate of tp125 = tp124 + ropedev-1 exact by construction (OWN_ROPE_DEV=1: the rope window refills
# computed on the card; at load every window compared with the host's tables, the few differing floats written by
# fix-ups). Cases with OWN_ROPE_DEV=1 against references made with the host's tables: x95k, x200k, x700k (704,773 rows),
# and the 1M prompt against ck1m's x1m_a (993,166 rows: the two known fix-ups lie at 887,541 and 889,359), all with
# OWN_KV_SHARD=1 where the reference had it; kvdedup-1 (OWN_KV_DEDUP=1, if the build is from 3c77277c87): check mode at 3K
# (two tails) and 95K (every staged row compared with the full mirror), 194K against R200, and the 1M case. Also: the attach trace (faults/attachtrace-20261116-d.txt) for ROPECOPY lines
# (none expected). Stable mode, preflight, first fault / difference = STOP. c124 was: tp124 gate.
set -u
W=/home/steve/dsv41-work; L=/home/steve/b70-optimization-lab; B=$W/own_run_v41_tp125
TS=$(date +%Y%m%dT%H%M); D=$W/runs/c125-$TS; mkdir -p $D
sum=$D/summary.txt; marks=$D/marks.txt
say() { echo "$*" >> $sum; sync -f $sum 2>/dev/null || sync; }
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib ZES_ENABLE_SYSMAN=1
g=$(cat $W/six.active 2>/dev/null); case "$g" in ""|c125) ;; *) say "STOP six.active held by $g"; exit 1;; esac
ls $W/locks/ | grep -q . && { say "STOP a lock is held: $(ls $W/locks)"; exit 1; }
echo c125 > $W/six.active; sync
pgrep -f "^/home/steve/dsv41-work/own_run_v41" > /dev/null && { say "STOP engine running"; exit 1; }
journalctl -k -f -o short-precise > $D/kernel-follow.txt 2>&1 & JF=$!
( while true; do sleep 5; sync -f $D/kernel-follow.txt $D/mem.txt $D/mem2.txt 2>/dev/null; done ) & SY=$!
( while true; do echo "$(date +%T.%N | cut -c1-10) $(awk '/MemAvailable/ {print int($2/1024)}' /proc/meminfo)"; sleep 0.5; done >> $D/mem.txt ) & MS=$!
# host detail every 0.5 s (mem2.txt): MiB of MemFree, Cached, AnonPages, Mapped, Shmem, Unevictable, Dirty, Writeback,
# PageTables, SUnreclaim; the engine's VmRSS (MiB); stall-time totals (us) from /proc/pressure: memory some/full, io
# some/full, cpu some - their growth between lines is the time tasks were held up on memory reclaim, disk or CPU
( while true; do
    e=$(pgrep -f "^/home/steve/dsv41-work/own_run_v41" | head -1)
    r=$([ -n "$e" ] && awk '/VmRSS/ {print int($2/1024)}' /proc/$e/status 2>/dev/null)
    echo "$(date +%T.%N | cut -c1-10) $(awk '/^(MemFree|Cached|AnonPages|Mapped|Shmem|Unevictable|Dirty|Writeback|PageTables|SUnreclaim):/ {printf "%s %d ", $1, $2/1024}' /proc/meminfo)rss ${r:-0} $(awk '{for (i=1;i<=NF;i++) if ($i ~ /^total=/) {sub("total=","",$i); printf "%s ", $i}}' /proc/pressure/memory /proc/pressure/io /proc/pressure/cpu)"
    sleep 0.5; done >> $D/mem2.txt ) & MS2=$!
trap 'kill $JF $SY $MS $MS2 2>/dev/null; rm -f $W/six.active; sync' EXIT
source $W/stable/stable.env
say "c125 start $(date '+%F %T') source $(grep "source commit" $W/build-tp125.log | tail -1) boot $(cut -c1-8 /proc/sys/kernel/random/boot_id) binary $(sha256sum $B | cut -c1-16)"
say "smt active $(cat /sys/devices/system/cpu/smt/active), cpus $(nproc), bios $(cat /sys/class/dmi/id/bios_version)"
J='fault response|cat error|engine reset|coredump has been created|gt reset|timedout job|exec queue reset|suspend fence|vm worker error|reset started|PCIe Bus Error|AER:|Hardware Error|Machine check|watchdog: BUG|rcu_sched self-detected|AMD-Vi: Event|wedged|inaccessible|GuC'
stop() { say "STOP $*"; say "STOPPED $(date '+%F %T')"; exit 1; }
pre() { local o; o=$($W/stable/preflight.sh 2>&1) || stop "preflight: $o"; }
G="OWN_MT_EU=6 OWN_MT_TGU=2 OWN_MT_RIDE=1 OWN_MT_RWG=128 OWN_MT_RFUSE=1 OWN_HC_FIN=1"
PL="OWN_TP=6 OWN_PROMPT_BLOCK=64 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G OWN_HOST_FLOOR_MIB=2048"
P5="OWN_PROMPT_BLOCK=512 OWN_PX=1 OWN_PX_BIG=1"
VOC="OWN_DR_VOCAB=$W/draft/vocab/cand-c32k-dict.txt OWN_DR_VOCAB_N=60000"
DSP=/mnt/fast-ai/llm-models/DeepSeek-V4.1-Flash-1017-GGUF/dspark-DeepSeek-V4.1-Flash-1017-Q8_0.gguf
SPEC="OWN_MT_TGM=1:1,2:1,3:3,4:2,5:3,6:3 OWN_SPEC=5 OWN_SPEC_KMIN=0 OWN_MT_TGR=2:4,3:4,4:4,5:4,6:4 OWN_MT_TGR_ROWS=4096 OWN_DSPARK=$DSP"
PP=$L/experiments/own-xpu-runtime/data/dsv41-bringup-20261109/spec-prompts
P1=$L/experiments/own-xpu-runtime/data/dsv41-bringup-20261109/prompt1-ids.txt
memwait() { local i=0; until [ $(awk '/MemAvailable/ {print int($2/1048576)}' /proc/meminfo) -ge 7 ] || [ $i -ge 120 ]; do sleep 5; i=$((i+1)); done; }
mx() { echo $(( ( $(wc -l < $1) + $2 + 1023 ) / 1024 * 1024 )); }
n=0
# run NAME PROMPT NTOK MAXCTX REF REFN [env...] (REF "-": no reference compare here)
run() { local name=$1 pr=$2 nt=$3 m=$4 ref=$5 rn=$6; shift 6; local t0 rc f
  pre; memwait; n=$((n+1)); t0=$(date '+%F %T')
  echo "$name start $(date '+%T.%N' | cut -c1-12)" >> $marks; sync -f $marks
  env "$@" OWN_PROMPT=$pr OWN_EOS=-1 $B - $nt $D/$name-ids.txt $m > $D/$name.log 2>&1; rc=$?
  echo "$name end $(date '+%T.%N' | cut -c1-12) rc $rc" >> $marks; sync -f $marks
  journalctl -k --since "$t0" -o short-precise > $D/$name-kernel.txt 2>&1
  grep -h "OWN_IDX_DTOPK\|OWN_IDX_RP\|malloc_trim\|OWN_IDX_ROWS\|OWN_ROPE_WIN\|prompt:\|decode:\|spec decode\|tile 2 card.*free after load\|rror\|timed out\|exceeds\|MISMATCH\|DIFFER\|BAD:" $D/$name.log | sed "s/^/$name: /" >> $sum
  grep -h "^tpd" $D/$name.log | head -12 | cut -c1-700 | sed "s/^/$name: /" >> $sum
  say "$name exit $rc (case $n)"
  f=$(grep -iE "$J" $D/$name-kernel.txt | head -3); [ -n "$f" ] && stop "$name kernel: $f"
  [ $rc -eq 0 ] || stop "$name exit $rc"
  grep -qE "MISMATCH|DIFFERS from|DIFFERENT FROM|BAD:" $D/$name.log && stop "$name: a check line reports a difference"
  [ "$ref" = - ] && return 0
  cmp -s <(head -$rn $D/$name-ids.txt) <(head -$rn $ref) && say "$name IDS${rn}_SAME" || stop "$name IDS${rn}_DIFFER vs $ref"; }
spec() { local name=$1 pn=$2; shift 2
  run $name $PP/$pn-ids.txt 512 4096 $W/runs/e57/${pn}_plain-ids.txt 511 $PL $SPEC OWN_SPEC_TAU=0.5 $VOC OWN_SPEC_LOG=$D/$name-spec.txt OWN_VERIFY_REF=$W/runs/e57/${pn}_plain-ids.txt "$@"
  grep -q "SAME AS the plain" $D/$name.log || stop "$name: no SAME AS the plain line"
  cmp -s <(awk '{print $1,$2,$3,$4,$5,$6,$7}' $D/$name-spec.txt) <(awk '{print $1,$2,$3,$4,$5,$6,$7}' $W/runs/tg105v/${pn}_v1-spec.txt) && say "$name GLOG_SAME" || stop "$name GLOG_DIFFER"; }
# soft NAME PROMPT NTOK MAXCTX REF REFN [env...]: like run, but a non-zero exit or a difference is recorded, not a stop
# (a kernel fault line still stops everything)
soft() { local name=$1 pr=$2 nt=$3 m=$4 ref=$5 rn=$6; shift 6; local t0 rc f
  pre; memwait; n=$((n+1)); t0=$(date '+%F %T')
  echo "$name start $(date '+%T.%N' | cut -c1-12)" >> $marks; sync -f $marks
  env "$@" OWN_PROMPT=$pr OWN_EOS=-1 $B - $nt $D/$name-ids.txt $m > $D/$name.log 2>&1; rc=$?
  echo "$name end $(date '+%T.%N' | cut -c1-12) rc $rc" >> $marks; sync -f $marks
  journalctl -k --since "$t0" -o short-precise > $D/$name-kernel.txt 2>&1
  grep -h "prompt:\|decode:\|spec decode\|tile 2 card.*free after load\|rror\|fatal\|timed out\|MISMATCH\|DIFFER" $D/$name.log | cut -c1-1500 | sed "s/^/$name: /" >> $sum
  grep -h "^tpd" $D/$name.log | head -40 | cut -c1-700 | sed "s/^/$name: /" >> $sum
  say "$name exit $rc (case $n)"
  f=$(grep -iE "$J" $D/$name-kernel.txt | head -3); [ -n "$f" ] && stop "$name kernel: $f"
  [ $rc -eq 0 ] && { cmp -s <(head -$rn $D/$name-ids.txt) <(head -$rn $ref) && say "$name IDS${rn}_SAME" || say "$name IDS${rn}_DIFFER"; }
  grep -q "SAME AS the plain" $D/$name.log && say "$name SAME_AS_PLAIN" || say "$name no SAME AS the plain line"; }
RD="OWN_ROPE_DEV=1"
AT=/home/steve/dsv41-work/faults/attachtrace-20261116-d.txt; AT0=$(wc -l < $AT 2>/dev/null || echo 0)
DDC=3c77277c87; DD=""; grep -q "source commit $DDC" $W/build-tp125.log && DD="OWN_KV_DEDUP=1"
[ -n "$DD" ] && say "kvdedup-1 cases on (build from $DDC)" || say "kvdedup-1 cases skipped (build: $(grep 'source commit' $W/build-tp125.log | tail -1))"
allsame() { grep -q "OWN_KV_SHARD=2 check: ALL SAME" $D/$1.log || stop "$1: no ALL SAME line ($(grep -h 'OWN_KV_SHARD=2 check' $D/$1.log | tail -1 | cut -c1-200))"; say "$1 ALL_SAME"; }
ddrep() { grep -q "OWN_KV_DEDUP=1: prompt halves" $D/$1.log || stop "$1: no kvdedup-1 start line"
  grep -h "OWN_KV_DEDUP=1: card\|OWN_KV_PUSH: card 0\|halves pushed: .*distinct" $D/$1.log | head -8 | cut -c1-300 | sed "s/^/$1: /" >> $sum; }
P3=$W/prompts/p3k-ids.txt; R3=$W/runs/e52/p3kplain-ids.txt
if [ -n "$DD" ]; then
  # check mode (every staged row compared with the full mirror through the slot lists): 3K default tail, then 3K
  # with real pushes from all six owners (tail 1024, chunks of 32 rows: kvdedup-1 needs R % 32 == 0)
  run p3k_dd $P3 256 4096 $R3 256 $PL $P5 OWN_KV_SHARD=2 $DD; allsame p3k_dd; ddrep p3k_dd
  run p3k_dd32 $P3 256 4096 $R3 256 $PL $P5 OWN_KV_SHARD=2 OWN_KV_TAIL=1024 OWN_KV_SHARD_R=32 $DD; allsame p3k_dd32; ddrep p3k_dd32
fi
x95=$W/prompts/xl/x95k-ids.txt; R95=$W/runs/e82/x95k_plain-ids.txt
run x95k_rd $x95 256 $(mx $x95 256) $R95 256 $PL $P5 $RD
grep -h "OWN_ROPE_DEV" $D/x95k_rd.log | head -4 | sed "s/^/x95k_rd: /" >> $sum
grep -q "OWN_ROPE_DEV: every rope window" $D/x95k_rd.log || stop "x95k_rd: no ropedev-1 load line"
[ -n "$DD" ] && { run x95k_dd $x95 256 $(mx $x95 256) $R95 256 $PL $P5 OWN_KV_SHARD=2 $DD; allsame x95k_dd; ddrep x95k_dd; }
x200=$W/prompts/lc/x200k-ids.txt; R200=$W/runs/lc1-20261115T1936/x200k_def-ids.txt
run x200k_rd $x200 1024 $(mx $x200 1024) $R200 1024 $PL $P5 $RD
# kvshard + kvdedup-1 at 194K (ckvs2 x200k_dt, the push form without it: 563.3 tok/s reading)
[ -n "$DD" ] && { run x200k_dd $x200 1024 $(mx $x200 1024) $R200 1024 $PL $P5 OWN_KV_SHARD=1 $DD OWN_HOST_FLOOR_MIB=1600; ddrep x200k_dd; }
x700=$W/prompts/lc/x700k-ids.txt
run x700k_rd $x700 1024 $(mx $x700 1024) /home/steve/dsv41-work/runs/c118p-20261116T1117/x700k_def-ids.txt 1024 $PL $P5 $RD
grep -h "OWN_ROPE_DEV" $D/x700k_rd.log | head -4 | sed "s/^/x700k_rd: /" >> $sum
x1m=$W/prompts/lc/x1m-ids.txt; A=$(ls -td $W/runs/ck1m-*/ | head -1)x1m_a-ids.txt
run x1m_rd $x1m 1024 $(mx $x1m 1024) $A 1024 $PL $P5 OWN_KV_SHARD=1 $RD $DD OWN_HOST_FLOOR_MIB=1600  # (owner-approved 1.6 GiB guard; 2048 failed in a kvshard upload at 22:00)
grep -h "OWN_ROPE_DEV" $D/x1m_rd.log | head -4 | sed "s/^/x1m_rd: /" >> $sum
[ -n "$DD" ] && ddrep x1m_rd
[ -s $AT ] && say "attach trace during c125: $(tail -n +$((AT0+1)) $AT | awk '$2=="ROPECOPY"' | wc -l) rope copies from host memory, $(tail -n +$((AT0+1)) $AT | awk '$2=="ATTACH"' | wc -l) dma-buf attaches (all, incl. the starts)"
say "ALLDONE $(date '+%F %T'): $n fresh starts identical to their references"
