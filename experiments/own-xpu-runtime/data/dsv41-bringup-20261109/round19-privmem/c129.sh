#!/bin/bash
# c129 (2026-11-17): tp129 = tp128 + idxfilt-1 (OWN_IDX_FILT, opt-in: prompt halves' split index layers by the
# matrix-engine pre-filter with a proven bound) + OWN_IDX_DUMP. 1. test_idxfilt on card 1 (the cards idle): the bound
# on every row, the rows left for exact scores, the time against IndexerScoreBM / BMS, and the selects end to end
# (prompt shape 43 tokens at 95K / 352K / 993K; checks 6 and 3 tokens at one card's 1M / 194K shares); 2. a 194K
# plain run dumping card 0's one-token index inputs (layers 2, 8, 14, 20) and the bench / analysis on them (real
# score distributions); 3. the engine's check mode (OWN_IDX_FILT=2 from 8,192 rows at 95K: every filtered layer's
# lists, block lists and marks against the unchanged path, must be ALL SAME) and identical answers; 4. speed: x95k
# default vs filter (same session), x200k with the filter against R200; 5. 1M read with the filter + kvshard against
# x1m_a (c127 s1m_dk read 562.9 tok/s). Stable mode, preflight, first fault / difference = STOP.
set -u
W=/home/steve/dsv41-work; L=/home/steve/b70-optimization-lab; B=$W/own_run_v41_tp129
TS=$(date +%Y%m%dT%H%M); D=$W/runs/c129-$TS; mkdir -p $D
sum=$D/summary.txt; marks=$D/marks.txt
say() { echo "$*" >> $sum; sync -f $sum 2>/dev/null || sync; }
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib ZES_ENABLE_SYSMAN=1
g=$(cat $W/six.active 2>/dev/null); case "$g" in ""|c129) ;; *) say "STOP six.active held by $g"; exit 1;; esac
ls $W/locks/ | grep -q . && { say "STOP a lock is held: $(ls $W/locks)"; exit 1; }
echo c129 > $W/six.active; sync
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
systemd-run --user --unit=vram-c129-$TS $W/vramlog.sh $D/vram.txt 8 >/dev/null 2>&1
trap 'touch $D/vram.txt.stop; kill $JF $SY $MS $MS2 2>/dev/null; rm -f $W/six.active; sync' EXIT
source $W/stable/stable.env
say "c129 start $(date '+%F %T') source $(grep "source commit" $W/build-tp129.log | tail -1) boot $(cut -c1-8 /proc/sys/kernel/random/boot_id) binary $(sha256sum $B | cut -c1-16)"
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
IF=0; grep -qE "source commit (a16a2b5f18|f5f7041c74)" $W/build-tp129.log && [ -x $W/test_idxfilt_tp129 ] && IF=1
IFK=0; [ $IF = 1 ] && grep -q "source commit a16a2b5f18" $W/build-tp129.log && IFK=1 # idxfilt-2c (the checks) in this build
GS="$SPEC OWN_SPEC_TAU=0.5 $VOC OWN_KV_SHARD=1 OWN_HOST_FLOOR_MIB=1600"
E=$(grep -h "s1m_all levers:" $W/chainq118.txt $(ls -td $W/runs/c128b-*/ 2>/dev/null | head -1)summary.txt 2>/dev/null | tail -1 | sed 's/.*s1m_all levers://; s/ none//')
say "idxfilt-2c in this build: $IFK; c128b's 1M levers:${E:- none}"
say "idxfilt-1 in this build: $IF"
PYN=/home/steve/.venvs/neural-worker/bin/python3
tif() { local name=$1; shift; pre; env "$@" ONEAPI_DEVICE_SELECTOR=level_zero:1 timeout 1500 $W/test_idxfilt_tp129 > $D/$name.log 2>&1
  say "$name: $(tail -1 $D/$name.log)"; grep -E "^[12] |^dump" $D/$name.log | cut -c1-400 | sed "s/^/$name: /" >> $sum
  tail -1 $D/$name.log | grep -q "^PASS"; }
if [ $IF = 1 ]; then
  tif tif_p BENCH_M=43 BENCH_LENS=95000,352000,993000 || { say "the filter bench did not pass: the engine's filter cases are skipped"; IF=0; }
  tif tif_c6 BENCH_M=6 BENCH_LENS=33000,166000 || IF=0
  tif tif_c3 BENCH_M=3 BENCH_LENS=166000 || IF=0
fi
# the defaults (tp129: the batched check launches on): 3K, plain, guessing code / analysis (GLOG)
run p3k $W/prompts/p3k-ids.txt 256 4096 $W/runs/e52/p3kplain-ids.txt 256 $PL $P5
run plain $P1 128 4096 $W/runs/ab1/base-speed-ids.txt 128 $PL
spec code code
spec analysis analysis
x95=$W/prompts/xl/x95k-ids.txt; R95=$W/runs/e82/x95k_plain-ids.txt
x200=$W/prompts/lc/x200k-ids.txt; R200=$W/runs/lc1-20261115T1936/x200k_def-ids.txt
# 2. the dump (card 0, the first one-token step past 190,000 rows; 2 tokens written), then the bench / analysis on it
run d200k $x200 2 $(mx $x200 2) $R200 2 $PL $P5 OWN_IDX_DUMP=$D/d200k OWN_IDX_DUMP_MIN=190000
grep -h "OWN_IDX_DUMP" $D/d200k.log | sed "s/^/d200k: /" >> $sum
if [ $IF = 1 ]; then
  for Lr in 2 8 14 20; do
    [ -f $D/d200k.L$Lr.bin ] && { tif tif_d$Lr BENCH_DUMP=$D/d200k.L$Lr.bin BENCH_M=1 || stop "tif_d$Lr: the bench on the dump did not pass"; }
  done
  [ -f $D/d200k.L20.bin ] && { tif tif_d20m6 BENCH_DUMP=$D/d200k.L20.bin BENCH_M=6 || stop "tif_d20m6: did not pass"; }
fi
ls $D/d200k.L*.bin > /dev/null 2>&1 && nice -n 10 $PYN -I $W/idxfilt/analyze.py $D/d200k.L*.bin > $D/dump-analysis.txt 2>&1
sed "s/^/analysis: /" $D/dump-analysis.txt | cut -c1-300 >> $sum
if [ $IF = 1 ]; then
  # 3. check mode at 95K from 8,192 rows: every filtered layer against the unchanged path
  run x95k_f2 $x95 256 $(mx $x95 256) $R95 256 $PL $P5 OWN_IDX_FILT=2 OWN_IDX_FILT_MIN=8192
  grep -h "OWN_IDX_FILT" $D/x95k_f2.log | cut -c1-260 | sed "s/^/x95k_f2: /" >> $sum
  grep -q "OWN_IDX_FILT=2 check: [1-9][0-9]* lists compared, 0 differ -> ALL SAME" $D/x95k_f2.log || stop "x95k_f2: the filter check did not end ALL SAME"
  # 3b. idxfilt-2c check mode: guessing at 194K, both filters from small sizes, every list against the exact path
  if [ $IFK = 1 ]; then
    run s200k_f2 $x200 1024 $(mx $x200 1024) $R200 1024 $PL $P5 $GS OWN_SPEC_LOG=$D/s200k_f2-spec.txt OWN_VERIFY_REF=$R200 OWN_IDX_FILT=2 OWN_IDX_FILT_MIN=8192 OWN_IDX_FILT_CK=1 OWN_IDX_FILT_CK_MIN=4096
    grep -h "OWN_IDX_FILT" $D/s200k_f2.log | cut -c1-260 | sed "s/^/s200k_f2: /" >> $sum
    grep -q "OWN_IDX_FILT=2 check: [1-9][0-9]* lists compared, 0 differ -> ALL SAME" $D/s200k_f2.log || stop "s200k_f2: the filter check did not end ALL SAME"
    grep -q "SAME AS the plain" $D/s200k_f2.log || stop "s200k_f2: no SAME AS the plain line"
  fi
  # 4. speed: default and filter at 95K (same session), filter at 194K against R200
  run x95k_b $x95 256 $(mx $x95 256) $R95 256 $PL $P5
  run x95k_f $x95 256 $(mx $x95 256) $R95 256 $PL $P5 OWN_IDX_FILT=1
  grep -h "OWN_IDX_FILT=1: card 0" $D/x95k_f.log | sed "s/^/x95k_f: /" >> $sum
  run x200k_f $x200 1024 $(mx $x200 1024) $R200 1024 $PL $P5 OWN_IDX_FILT=1
  grep -h "OWN_IDX_FILT=1: card 0" $D/x200k_f.log | sed "s/^/x200k_f: /" >> $sum
  if [ $IFK = 1 ]; then # guessing at 194K: default (c128 s200k_mb 129.95 tok/s, check 16.52 ms) vs both filters
    run s200k_b $x200 1024 $(mx $x200 1024) $R200 1024 $PL $P5 $GS OWN_SPEC_LOG=$D/s200k_b-spec.txt OWN_VERIFY_REF=$R200
    run s200k_fk $x200 1024 $(mx $x200 1024) $R200 1024 $PL $P5 $GS OWN_SPEC_LOG=$D/s200k_fk-spec.txt OWN_VERIFY_REF=$R200 OWN_IDX_FILT=1 OWN_IDX_FILT_CK=1
    grep -q "SAME AS the plain" $D/s200k_fk.log || stop "s200k_fk: no SAME AS the plain line"
  fi
  # 5. 1M read + guessing with the filters and c128b's levers (c127 s1m_dk: read 562.9 tok/s, writing 130.66 tok/s)
  x1m=$W/prompts/lc/x1m-ids.txt; A=$(ls -td $W/runs/ck1m-*/ | head -1)x1m_a-ids.txt
  FK=""; [ $IFK = 1 ] && FK="OWN_IDX_FILT_CK=1"
  soft s1m_f $x1m 1024 $(mx $x1m 1024) $A 1024 $PL $P5 $GS OWN_SPEC_LOG=$D/s1m_f-spec.txt OWN_VERIFY_REF=$A $E OWN_IDX_FILT=1 $FK
  grep -h "free after load\|OWN_IDX_FILT=1: card" $D/s1m_f.log | head -10 | cut -c1-200 | sed "s/^/s1m_f: /" >> $sum
  grep -q "^s1m_f IDS1024_SAME" $sum && grep -q "^s1m_f SAME_AS_PLAIN" $sum || stop "s1m_f: not identical (or did not run): see its log"
fi
say "ALLDONE $(date '+%F %T'): $n fresh starts identical to their references"
