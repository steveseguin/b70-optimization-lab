#!/bin/bash
# ck1m3 (2026-11-17): guessing at ~1M. Writing at 1M is 86.5 tok/s plain; guessing gives ~1.33x at 194K (s200k
# 124.5 vs 91.8) but needs ~1.40 GiB more per card (the draft's weights), and at 1M card 2 (two attention groups) had
# 1.44 GiB free after load, ~1.20 while reading (tp125). tp126 adds idxrows-2 (~0.17 GiB per card at 1M). s1m: the
# 1M prompt with guessing, kvshard (de-dup and the card rope fill by default in tp126), against x1m_a (1024 answers,
# SAME AS the plain run). A refusal for card memory at load is recorded (soft), the free-memory lines kept.
# hl232 first: the prompt-block head split 3,3,2,3,3,2 (card 2 holds half a group fewer rows), A/B at 3K / 10K.
set -u
W=/home/steve/dsv41-work; L=/home/steve/b70-optimization-lab; B=$W/own_run_v41_tp120
c122s=$(ls -td $W/runs/c122-*/ 2>/dev/null | head -1)
[ -x $W/own_run_v41_tp122 ] && [ -n "$c122s" ] && grep -q "^ALLDONE" ${c122s}summary.txt && B=$W/own_run_v41_tp122
c123s=$(ls -td $W/runs/c123-*/ 2>/dev/null | head -1)
[ -x $W/own_run_v41_tp123 ] && [ -n "$c123s" ] && grep -q "^ALLDONE" ${c123s}summary.txt && B=$W/own_run_v41_tp123
c124s=$(ls -td $W/runs/c124-*/ 2>/dev/null | head -1)
[ -x $W/own_run_v41_tp124 ] && [ -n "$c124s" ] && grep -q "^ALLDONE" ${c124s}summary.txt && B=$W/own_run_v41_tp124
c125s=$(ls -td $W/runs/c125-*/ 2>/dev/null | head -1)
[ -x $W/own_run_v41_tp125 ] && [ -n "$c125s" ] && grep -q "^ALLDONE" ${c125s}summary.txt && B=$W/own_run_v41_tp125
c126s=$(ls -td $W/runs/c126-*/ 2>/dev/null | head -1)
[ -x $W/own_run_v41_tp126 ] && [ -n "$c126s" ] && grep -q "^ALLDONE" ${c126s}summary.txt && B=$W/own_run_v41_tp126
TS=$(date +%Y%m%dT%H%M); D=$W/runs/ck1m3-$TS; mkdir -p $D
sum=$D/summary.txt; marks=$D/marks.txt
say() { echo "$*" >> $sum; sync -f $sum 2>/dev/null || sync; }
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib ZES_ENABLE_SYSMAN=1
g=$(cat $W/six.active 2>/dev/null); case "$g" in ""|ck1m3) ;; *) say "STOP six.active held by $g"; exit 1;; esac
ls $W/locks/ | grep -q . && { say "STOP a lock is held: $(ls $W/locks)"; exit 1; }
echo ck1m3 > $W/six.active; sync
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
say "ck1m3 start $(date '+%F %T') source $(basename $B) boot $(cut -c1-8 /proc/sys/kernel/random/boot_id) binary $(sha256sum $B | cut -c1-16)"
say "smt active $(cat /sys/devices/system/cpu/smt/active), cpus $(nproc), bios $(cat /sys/class/dmi/id/bios_version)"
J='fault response|cat error|engine reset|coredump has been created|gt reset|timedout job|exec queue reset|suspend fence|vm worker error|reset started|PCIe Bus Error|AER:|Hardware Error|Machine check|watchdog: BUG|rcu_sched self-detected|AMD-Vi: Event|wedged|inaccessible|GuC'
stop() { say "STOP $*"; say "STOPPED $(date '+%F %T')"; exit 1; }
pre() { local o; o=$($W/stable/preflight.sh 2>&1) || stop "preflight: $o"; }
G="OWN_MT_EU=6 OWN_MT_TGU=2 OWN_MT_RIDE=1 OWN_MT_RWG=128 OWN_MT_RFUSE=1 OWN_HC_FIN=1"
PL="OWN_TP=6 OWN_PROMPT_BLOCK=64 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G OWN_HOST_FLOOR_MIB=1600"  # 1600 (2026-11-16 22:15): x700k_ks at 2048 fell 1 MiB under it in the upload (page tables grow ~15 MB/s while loading; kvshard ~1 GB more); 1.6 GiB = the owner-approved guard for research launches  # 2048 for the 1M starts (2026-11-16 20:39: the runtime's ~5 GB start-up dip went below 2560 before the upload at 1M)
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
  grep -h "OWN_KV_SHARD\|OWN_KV_PUSH\|OWN_IDX_DTOPK\|malloc_trim\|tpd-mem\|OWN_IDX_ROWS\|OWN_ROPE_WIN\|prompt:\|decode:\|spec decode\|tile 2 card.*free after load\|rror\|timed out\|exceeds\|MISMATCH\|DIFFER\|BAD:" $D/$name.log | sed "s/^/$name: /" >> $sum
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
  # the start race (ck1m2 x1m_b): the runtime's post-build host spike inside the upload's first seconds ends the load
  # (no card work yet; hostfloor-2 pauses instead, from tp127): once more after 30 s
  if [ $rc -ne 0 ] && grep -q "fell below the floor during upload" $D/$name.log && ! grep -q "prompt:" $D/$name.log; then
    mv $D/$name.log $D/$name-try1.log; say "$name: host floor at the upload's start (try 1 kept as $name-try1.log), once more"
    sleep 30; memwait; pre
    echo "$name start2 $(date '+%T.%N' | cut -c1-12)" >> $marks; sync -f $marks
    env "$@" OWN_PROMPT=$pr OWN_EOS=-1 $B - $nt $D/$name-ids.txt $m > $D/$name.log 2>&1; rc=$?
  fi
  echo "$name end $(date '+%T.%N' | cut -c1-12) rc $rc" >> $marks; sync -f $marks
  journalctl -k --since "$t0" -o short-precise > $D/$name-kernel.txt 2>&1
  grep -h "prompt:\|decode:\|spec decode\|tile 2 card.*free after load\|rror\|fatal\|timed out\|MISMATCH\|DIFFER" $D/$name.log | cut -c1-1500 | sed "s/^/$name: /" >> $sum
  grep -h "^tpd" $D/$name.log | head -40 | cut -c1-700 | sed "s/^/$name: /" >> $sum
  say "$name exit $rc (case $n)"
  f=$(grep -iE "$J" $D/$name-kernel.txt | head -3); [ -n "$f" ] && stop "$name kernel: $f"
  [ $rc -eq 0 ] && { cmp -s <(head -$rn $D/$name-ids.txt) <(head -$rn $ref) && say "$name IDS${rn}_SAME" || say "$name IDS${rn}_DIFFER"; }
  grep -q "SAME AS the plain" $D/$name.log && say "$name SAME_AS_PLAIN" || say "$name no SAME AS the plain line"; }
K="OWN_KV_SHARD=1"; [ "$B" = "$W/own_run_v41_tp123" ] && K="$K $(cat $W/idxrp-var.txt 2>/dev/null)"
# tp125 gated with kvdedup-1 + ropedev-1 identical at 1M (c125 x1m_rd): use them (fewer card-to-card copies, no rope host copies)
[ "$B" = "$W/own_run_v41_tp125" ] && grep -q "^x1m_rd IDS1024_SAME" ${c125s}summary.txt && grep -q "kvdedup-1 cases on" ${c125s}summary.txt && K="$K OWN_KV_DEDUP=1 OWN_ROPE_DEV=1"
say "engine $B, switches: $K"
# hl232 (2026-11-17): prompt-block heads 3,3,2,3,3,2 instead of 3,3,3,3,2,2. Cards hold the q_b / output-a rows of both
# layouts (whole groups for one-token steps, the head split for blocks of >= 16), so card 2 holds 2.5 groups today
# (heads 16-35) and 2 with this split (16-31); card 3 drops to 1.5. Same sums per head and output-a row (only which card
# computes them). A/B interleaved at 3K and 10K (identical answers required, a difference stops); s1m uses the split
# when both are identical.
H232="OWN_TP_HEADS=3,3,2,3,3,2 OWN_TP_HEADS_MIN=16"
run p3k_d $W/prompts/p3k-ids.txt 256 4096 $W/runs/e52/p3kplain-ids.txt 256 $PL $P5
run p3k_h $W/prompts/p3k-ids.txt 256 4096 $W/runs/e52/p3kplain-ids.txt 256 $PL $P5 $H232
run p10k_h $W/prompts/p10k-ids.txt 64 16384 $W/runs/tg107/p10k_bcs-ids.txt 64 $PL $P5 $K $H232
run p10k_d $W/prompts/p10k-ids.txt 64 16384 $W/runs/tg107/p10k_bcs-ids.txt 64 $PL $P5 $K
# m1 (2026-11-17): the same split for one-token steps and checks too (OWN_TP_HEADS_MIN=1: no second layout, so no
# duplicated rows: card 2 holds 8 heads instead of 20, card 5 8 instead of 16). Costs pair swaps in one-token steps
# and checks. Exactness + speed at 3K plain and in guessing (code); s1m_m1 below only if s1m is refused for card memory.
M1="OWN_TP_HEADS=3,3,2,3,3,2 OWN_TP_HEADS_MIN=1"
run p3k_m1 $W/prompts/p3k-ids.txt 256 4096 $W/runs/e52/p3kplain-ids.txt 256 $PL $P5 $M1
spec code_m1 code $M1
spec code_d code
grep -h "heads per card\|free after load" $D/p3k_h.log $D/p3k_d.log $D/p3k_m1.log | cut -c1-200 | sed "s/^/hl232: /" >> $sum
HS=""; grep -q "^p3k_h IDS256_SAME" $sum && grep -q "^p10k_h IDS64_SAME" $sum && HS="$H232"
say "s1m head split: ${HS:-default}"
x1m=$W/prompts/lc/x1m-ids.txt; A=$(ls -td $W/runs/ck1m-*/ | head -1)x1m_a-ids.txt
soft s1m $x1m 1024 $(mx $x1m 1024) $A 1024 $PL $P5 $SPEC OWN_SPEC_TAU=0.5 $VOC $K $HS OWN_SPEC_LOG=$D/s1m-spec.txt OWN_VERIFY_REF=$A
grep -h "free after load\|need .* GiB\|tpd-mem\|OWN_IDX_ROWS\|OWN_KV_DEDUP=1: card 0" $D/s1m.log | head -16 | cut -c1-220 | sed "s/^/s1m: /" >> $sum
if grep -q "not enough free card memory" $D/s1m.log && grep -q "^p3k_m1 IDS256_SAME" $sum && grep -q "^code_m1 GLOG_SAME" $sum; then
  grep -h "not enough free card memory" $D/s1m.log | cut -c1-400 | sed "s/^/s1m refused: /" >> $sum
  soft s1m_m1 $x1m 1024 $(mx $x1m 1024) $A 1024 $PL $P5 $SPEC OWN_SPEC_TAU=0.5 $VOC $K $M1 OWN_SPEC_LOG=$D/s1m_m1-spec.txt OWN_VERIFY_REF=$A
  grep -h "free after load\|not enough free card memory\|OWN_IDX_ROWS" $D/s1m_m1.log | head -10 | cut -c1-300 | sed "s/^/s1m_m1: /" >> $sum
fi
say "ALLDONE $(date '+%F %T'): $n fresh starts"
