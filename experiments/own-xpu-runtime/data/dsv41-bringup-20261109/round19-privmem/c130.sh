#!/bin/bash
# c130 (2026-11-17): tp130 = tp129 + idxmem-1 (the filter's per-token buffers for 43 tokens: 128 -> 21 MiB per card at
# 1M) + allocmap-1 (OWN_ALLOC_LOG=1). 1. rux9 bench on card 1 (prompt expert kernels, x staged once in local memory:
# small shape, bitwise exactness at 16 / 64 / 256 / 512 tokens, timing; a failure is recorded and the bench lane
# closes, the engine cases go on); 2. identity at 3K / plain / guessing (GLOG); 3. the card-memory map at 1M size (3K
# prompt, max context of the 1M prompt, guessing + every 1M lever, OWN_ALLOC_LOG=1); 4. 1M + guessing with the
# filters, drlast-1, c128b's levers and (if c129 passed it) OWN_TP_WEIGHTS=30,29,29,30,29,29 against x1m_a
# (c127 s1m_dk: read 562.9 tok/s, writing 130.66 tok/s). Stable mode, preflight, first fault / difference = STOP.
set -u
W=/home/steve/dsv41-work; L=/home/steve/b70-optimization-lab; B=$W/own_run_v41_tp130
TS=$(date +%Y%m%dT%H%M); D=$W/runs/c130-$TS; mkdir -p $D
sum=$D/summary.txt; marks=$D/marks.txt
say() { echo "$*" >> $sum; sync -f $sum 2>/dev/null || sync; }
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib ZES_ENABLE_SYSMAN=1
g=$(cat $W/six.active 2>/dev/null); case "$g" in ""|c130) ;; *) say "STOP six.active held by $g"; exit 1;; esac
ls $W/locks/ | grep -q . && { say "STOP a lock is held: $(ls $W/locks)"; exit 1; }
echo c130 > $W/six.active; sync
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
systemd-run --user --unit=vram-c130-$TS $W/vramlog.sh $D/vram.txt 8 >/dev/null 2>&1
trap 'touch $D/vram.txt.stop; kill $JF $SY $MS $MS2 2>/dev/null; rm -f $W/six.active; sync' EXIT
source $W/stable/stable.env
say "c130 start $(date '+%F %T') source $(grep "source commit" $W/build-tp130.log | tail -1) boot $(cut -c1-8 /proc/sys/kernel/random/boot_id) binary $(sha256sum $B | cut -c1-16)"
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
nice -n 10 python3 -I $W/privmem_check.py $B 2>&1 | head -1 | sed "s/^/privmem: /" >> $sum
GS="$SPEC OWN_SPEC_TAU=0.5 $VOC OWN_KV_SHARD=1 OWN_HOST_FLOOR_MIB=1600"
E=$(grep -h "s1m_all levers:" $W/chainq118.txt 2>/dev/null | tail -1 | sed 's/.*s1m_all levers://; s/ none//')
C9=$(ls -td $W/runs/c129-*/ 2>/dev/null | head -1)summary.txt
TW=""; grep -q "^tpw identity at 3K / plain / guessing: PASS" $C9 2>/dev/null && ! grep -q "^s200k_w GLOG_DIFFER\|^s200k_w IDS1024_DIFFER" $C9 && TW="OWN_TP_WEIGHTS=30,29,29,30,29,29"
say "c128b's 1M levers:${E:- none}; tpw from c129: ${TW:-not passed / not run}"
# 1. rux9 bench (README gate), card 1
RX=$W/rux9; RP="env LD_LIBRARY_PATH=$LD_LIBRARY_PATH ONEAPI_DEVICE_SELECTOR=level_zero:1 ZES_ENABLE_SYSMAN=1 ONLY=s20 RUX_IDS=$W/runs/u84/p3k-ids-per-layer.txt"
rxj() { local f; f=$(journalctl -k --since "$1" -o cat | grep -iE "$J" | head -3); [ -n "$f" ] && stop "rux9 bench kernel: $f"; return 0; }
if grep -q "^rux9 bench build exit 0" $W/build-tp130.log && grep -q "rux9 sendcheck: .*PASS" $W/build-tp130.log; then
  grep "^rux9 isa" $W/build-tp130.log | cut -c1-200 | sed "s/^/rux9 /" >> $sum
  pre; t0=$(date '+%F %T')
  (cd $RX && timeout 900 $RP CHECKM=16 CHECK1=1 NOTPE=1 NOTIME=1 ./bench_rux9 > $D/rux9-small.log 2>&1); r1=$?; rxj "$t0"
  say "rux9 small: exit $r1, $(tail -1 $D/rux9-small.log | cut -c1-200)"
  if [ $r1 -eq 0 ]; then
    t0=$(date '+%F %T'); (cd $RX && timeout 1800 $RP CHECKM=16,64,256,512 NOTIME=1 ./bench_rux9 > $D/rux9-exact.log 2>&1); r2=$?; rxj "$t0"
    say "rux9 exact: exit $r2, $(tail -1 $D/rux9-exact.log | cut -c1-200)"
    grep -h "bitwise\|FAIL" $D/rux9-exact.log | head -30 | cut -c1-250 | sed "s/^/rux9 exact: /" >> $sum
    if [ $r2 -eq 0 ] && tail -1 $D/rux9-exact.log | grep -q "^PASS"; then
      for k in 1 2 3; do t0=$(date '+%F %T'); (cd $RX && timeout 1800 $RP RM=256 ROUNDS=3 NOCHECK=1 ./bench_rux9 > $D/rux9-time$k.log 2>&1); rxj "$t0"
        grep -h "%" $D/rux9-time$k.log | head -20 | cut -c1-250 | sed "s/^/rux9 time$k: /" >> $sum; done
    else say "rux9: not bitwise / failed: the lane closes here (no timing)"; fi
  fi
else
  say "rux9: bench not built or the ISA check did not pass: $(grep '^rux9' $W/build-tp130.log | head -3 | tr '\n' ' ' | cut -c1-300)"
fi
# 2. identity (tp130 defaults)
run p3k $W/prompts/p3k-ids.txt 256 4096 $W/runs/e52/p3kplain-ids.txt 256 $PL $P5
run plain $P1 128 4096 $W/runs/ab1/base-speed-ids.txt 128 $PL
spec code code
spec analysis analysis
x1m=$W/prompts/lc/x1m-ids.txt; A=$(ls -td $W/runs/ck1m-*/ | head -1)x1m_a-ids.txt
LV="$E OWN_IDX_FILT=1 OWN_DR_LAST=1 $TW" # (OWN_IDX_FILT_CK off: c129 s200k_f2 check mode found 108 block-list differences)
# 3. the memory map at 1M size: the 3K prompt with the 1M prompt's max context, guessing and every 1M lever
run am1m $W/prompts/p3k-ids.txt 256 $(mx $x1m 1024) $W/runs/e52/p3kplain-ids.txt 256 $PL $P5 $GS OWN_SPEC_LOG=$D/am1m-spec.txt OWN_VERIFY_REF=$W/runs/e52/p3kplain-ids.txt $LV OWN_ALLOC_LOG=1
grep -h "^alloc\|free after load\|rows per card (mid" $D/am1m.log | cut -c1-1500 | sed "s/^/am1m: /" >> $sum
# 4. 1M + guessing with everything (c128b s1m_all stopped at its 2nd check step: cards 2 / 5 out of memory)
soft s1m_w $x1m 1024 $(mx $x1m 1024) $A 1024 $PL $P5 $GS OWN_SPEC_LOG=$D/s1m_w-spec.txt OWN_VERIFY_REF=$A $LV OWN_ALLOC_LOG=1
grep -h "^alloc after the prompt\|^tpd-mem\|OWN_IDX_FILT=1: card 0\|OWN_DR_LAST" $D/s1m_w.log | cut -c1-1500 | sed "s/^/s1m_w: /" >> $sum
grep -q "^s1m_w IDS1024_SAME" $sum && grep -q "^s1m_w SAME_AS_PLAIN" $sum || stop "s1m_w: not identical (or did not run): see its log"
say "ALLDONE $(date '+%F %T'): $n fresh starts identical to their references"
