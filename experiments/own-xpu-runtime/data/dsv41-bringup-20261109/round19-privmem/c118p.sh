#!/bin/bash
# c118p (2026-11-16): gate of tp118p = tp118 + privmem-1 (index kernels' per-token tables in card memory) + tpd-2 (engram
# time split in reports); c118 itself stopped at x200k (card 1's engram rows took 1.56 s at 157,696: exchange time-out).
# tp118 = tp117 + turns-1 (OWN_TURNS, runner only) + topk-m (OWN_TOPK_M, opt-in, off here)
# + tpd-1 (per-card host timing per step: "tpd:" lines for slow blocks, timings in exchange time-out errors). Same
# cases as c117 up to x200k (all bit-identical to their references), then the 704,773-token capacity case in both modes
# (c117 never reached it). Guessing at 194K is left out: its intermittent exchange time-out is card memory running out
# after load (pr4 q300: "VM worker error: -12" at 0.71 GiB free; pr5 measures the post-load growth).
# Diagnostic configuration (SMT off, Gen4 x16, OWN_PX_SERIAL=1, default power, BIOS 11.02): preflight before each
# start, never changed here. First fault / non-zero exit / mismatch = STOP, no retry / reset / reboot. Synced logs.
set -u
W=/home/steve/dsv41-work; L=/home/steve/b70-optimization-lab; B=$W/own_run_v41_tp118p
TS=$(date +%Y%m%dT%H%M); D=$W/runs/c118p-$TS; mkdir -p $D
sum=$D/summary.txt; marks=$D/marks.txt
say() { echo "$*" >> $sum; sync -f $sum 2>/dev/null || sync; }
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib ZES_ENABLE_SYSMAN=1
g=$(cat $W/six.active 2>/dev/null); case "$g" in ""|c118p) ;; *) say "STOP six.active held by $g"; exit 1;; esac
ls $W/locks/ | grep -q . && { say "STOP a lock is held: $(ls $W/locks)"; exit 1; }
echo c118p > $W/six.active; sync
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
say "c118p start $(date '+%F %T') source $(grep "source commit" $W/build-tp118p.log | tail -1) boot $(cut -c1-8 /proc/sys/kernel/random/boot_id) binary $(sha256sum $B | cut -c1-16)"
say "smt active $(cat /sys/devices/system/cpu/smt/active), cpus $(nproc), bios $(cat /sys/class/dmi/id/bios_version)"
J='fault response|cat error|engine reset|coredump has been created|gt reset|timedout job|exec queue reset|suspend fence|vm worker error|reset started|PCIe Bus Error|AER:|Hardware Error|Machine check|watchdog: BUG|rcu_sched self-detected|AMD-Vi: Event|wedged|inaccessible|GuC'
stop() { say "STOP $*"; say "STOPPED $(date '+%F %T')"; exit 1; }
pre() { local o; o=$($W/stable/preflight.sh 2>&1) || stop "preflight: $o"; }
G="OWN_MT_EU=6 OWN_MT_TGU=2 OWN_MT_RIDE=1 OWN_MT_RWG=128 OWN_MT_RFUSE=1 OWN_HC_FIN=1"
PL="OWN_TP=6 OWN_PROMPT_BLOCK=64 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G OWN_HOST_FLOOR_MIB=2560"
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
  grep -h "OWN_IDX_ROWS\|OWN_ROPE_WIN\|prompt:\|decode:\|spec decode\|tile 2 card.*free after load\|rror\|timed out\|exceeds\|MISMATCH\|DIFFER\|BAD:" $D/$name.log | sed "s/^/$name: /" >> $sum
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
# (1) exactness against the references (the layout is on in every prompt mode: blocks / halves split, small tails whole)
run p3k $W/prompts/p3k-ids.txt 256 4096 $W/runs/e52/p3kplain-ids.txt 256 $PL $P5
grep -q "OWN_IDX_ROWS: block index score rows" $D/p3k.log || stop "p3k: the compact layout is not on"
run p10k $W/prompts/p10k-ids.txt 64 16384 $W/runs/tg107/p10k_bcs-ids.txt 64 $PL $P5
run plain $P1 128 4096 $W/runs/ab1/base-speed-ids.txt 128 $PL
spec code code
spec analysis analysis
x95=$W/prompts/xl/x95k-ids.txt; run x95k $x95 256 $(mx $x95 256) $W/runs/e82/x95k_plain-ids.txt 256 $PL $P5
x200=$W/prompts/lc/x200k-ids.txt; run x200k $x200 1024 $(mx $x200 1024) $W/runs/lc1-20261115T1936/x200k_def-ids.txt 1024 $PL $P5
grep -q "OWN_ROPE_WIN: rope tables as a" $D/x95k.log || stop "x95k: the rope window is not on"
say "GATE_PASSED $(date '+%F %T'): $n starts identical to their references"
# (3, before the capacity runs) guessing at 194K twice, soft: the intermittent exchange time-out of tp115-tp118 in this
# case (3 of 8) came with card memory running short after load; privmem-1 frees ~0.94 GiB per card of it
R2=$W/runs/lc1-20261115T1936/x200k_def-ids.txt
for k in 1 2; do soft s200k_$k $x200 1024 $(mx $x200 1024) $R2 1024 $PL $P5 $SPEC OWN_SPEC_TAU=0.5 $VOC OWN_SPEC_LOG=$D/s200k_$k-spec.txt OWN_VERIFY_REF=$R2; done
# (2) capacity: 704,773 tokens, production mode and tp115's switches off; the two must agree
x700=$W/prompts/lc/x700k-ids.txt
run x700k_def $x700 1024 $(mx $x700 1024) - 0 $PL $P5
run x700k_off $x700 1024 $(mx $x700 1024) - 0 $PL $P5 OWN_SKIP39=0 OWN_IDX_DSPLIT=0
cmp -s $D/x700k_def-ids.txt $D/x700k_off-ids.txt && say "x700k_off IDS1024_SAME as x700k_def" || stop "x700k_off IDS_DIFFER from x700k_def"
say "ALLDONE $(date '+%F %T'): $n fresh starts; gate + capacity exits 0 and identical; no fault line"
