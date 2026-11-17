#!/bin/bash
# lp1p (2026-11-16): lp1 on tp118p (= tp118 + privmem-1 + tpd-2; c118p its gate), else unchanged.
# lp1 (2026-11-15): where writing time grows with context. tp117 (after c117 passes), card 2's kernel profile per
# answer step (OWN_GPROF=2 OWN_GPROF_DECODE=1 OWN_GPROF_CARD=2: answer steps only) at 95,497 and 388,251 tokens,
# 128 answers each, both checked against their references (profiling changes no bits). Unprofiled speeds for the
# same sizes: c115 x95k 91.69 tok/s, lc2 x400k 76.90. Diagnostic configuration, preflight, synced logs, first
# fault / non-zero exit / mismatch = STOP (no retry / reset / reboot).
{ [ -e /home/steve/dsv41-work/defer-120c ] || [ -e /home/steve/dsv41-work/defer-122 ]; } && { echo "$(date '+%F %T') $(basename $0) deferred (defer-120c / defer-122: a later queue runs it)" >> /home/steve/dsv41-work/chainq118.txt; exit 0; }
set -u
W=/home/steve/dsv41-work; L=/home/steve/b70-optimization-lab
B=$W/own_run_v41_tp118p
# (2026-11-16 12:3x) tp120 (+ privmem-2, eng-gate-1: one card's host thread held up ~1.3-1.7 s stopped c118 x200k,
# c118p x700k_off and tlx1 x400k) when it built and its gate c120 passed; else tp118p as before
c120s=$(ls -td $W/runs/c120-*/ 2>/dev/null | head -1)
if [ -x $W/own_run_v41_tp120 ] && grep -q "tp120 build exit 0" $W/build-tp120.log 2>/dev/null && [ -n "$c120s" ] && grep -q "^ALLDONE" ${c120s}summary.txt; then B=$W/own_run_v41_tp120; fi
c126s=$(ls -td $W/runs/c126-*/ 2>/dev/null | head -1)  # (2026-11-16 23:0x: the newest gated engine when there is one)
if [ -x $W/own_run_v41_tp126 ] && [ -n "$c126s" ] && grep -q "^ALLDONE" ${c126s}summary.txt; then B=$W/own_run_v41_tp126; fi
c127s=$(ls -td $W/runs/c127-*/ 2>/dev/null | head -1)
if [ -x $W/own_run_v41_tp127 ] && [ -n "$c127s" ] && grep -q "^ALLDONE" ${c127s}summary.txt; then B=$W/own_run_v41_tp127; fi
TS=$(date +%Y%m%dT%H%M); D=$W/runs/lp1p-$TS; mkdir -p $D
sum=$D/summary.txt; marks=$D/marks.txt
say() { echo "$*" >> $sum; sync -f $sum 2>/dev/null || sync; }
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib ZES_ENABLE_SYSMAN=1
g=$(cat $W/six.active 2>/dev/null); case "$g" in ""|lp1p) ;; *) say "STOP six.active held by $g"; exit 1;; esac
ls $W/locks/ | grep -q . && { say "STOP a lock is held: $(ls $W/locks)"; exit 1; }
echo lp1p > $W/six.active; sync
pgrep -f "^/home/steve/dsv41-work/own_run_v41" > /dev/null && { say "STOP engine running"; exit 1; }
journalctl -k -f -o short-precise > $D/kernel-follow.txt 2>&1 & JF=$!
( while true; do sleep 5; sync -f $D/kernel-follow.txt $D/mem.txt 2>/dev/null; done ) & SY=$!
( while true; do echo "$(date +%T.%N | cut -c1-10) $(awk '/MemAvailable/ {print int($2/1024)}' /proc/meminfo)"; sleep 0.5; done >> $D/mem.txt ) & MS=$!
trap 'kill $JF $SY $MS 2>/dev/null; rm -f $W/six.active; sync' EXIT
source $W/stable/stable.env
say "lp1p start $(date '+%F %T') boot $(cut -c1-8 /proc/sys/kernel/random/boot_id) binary $(basename $B) $(sha256sum $B | cut -c1-16)"
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
  say "$name exit $rc (case $n)"
  f=$(grep -iE "$J" $D/$name-kernel.txt | head -3); [ -n "$f" ] && stop "$name kernel: $f"
  [ $rc -eq 0 ] || stop "$name exit $rc"
  grep -qE "MISMATCH|DIFFERS from|DIFFERENT FROM|BAD:" $D/$name.log && stop "$name: a check line reports a difference"
  [ "$ref" = - ] && return 0
  cmp -s <(head -$rn $D/$name-ids.txt) <(head -$rn $ref) && say "$name IDS${rn}_SAME" || stop "$name IDS${rn}_DIFFER vs $ref"; }
x95=$W/prompts/xl/x95k-ids.txt
run g95k $x95 128 $(mx $x95 256) $W/runs/e82/x95k_plain-ids.txt 128 $PL $P5 OWN_GPROF=2 OWN_GPROF_DECODE=1 OWN_GPROF_CARD=2
x400=$W/prompts/lc/x400k-ids.txt
run g400k $x400 128 $(mx $x400 1024) $W/runs/lc2-20261115T1948/x400k_def-ids.txt 128 $PL $P5 OWN_GPROF=2 OWN_GPROF_DECODE=1 OWN_GPROF_CARD=2
# (2026-11-17 02:2x) guessing cycles profiled (OWN_GPROF=2: kernel time per cycle, draft + check, card 2): code (3K-class
# short prompt) and 194K, with dtopk-2 when c127 passed its check (DKM): what a check still pays at long context
DKM=""; [ -n "$c127s" ] && grep -q "dtopk-2 check at 194K: PASS" ${c127s}summary.txt && [ "$B" = $W/own_run_v41_tp127 ] && DKM="OWN_IDX_DTOPK_M=1"
say "guessing profiles with: ${DKM:-no dtopk-2}"
run gscode $PP/code-ids.txt 256 4096 $W/runs/e57/code_plain-ids.txt 255 $PL $SPEC OWN_SPEC_TAU=0.5 $VOC OWN_SPEC_LOG=$D/gscode-spec.txt OWN_VERIFY_REF=$W/runs/e57/code_plain-ids.txt OWN_GPROF=2 OWN_GPROF_CARD=2
x200=$W/prompts/lc/x200k-ids.txt; R200=$W/runs/lc1-20261115T1936/x200k_def-ids.txt
run gs200k $x200 256 $(mx $x200 1024) $R200 256 $PL $P5 $SPEC OWN_SPEC_TAU=0.5 $VOC OWN_KV_SHARD=1 OWN_HOST_FLOOR_MIB=1600 OWN_SPEC_LOG=$D/gs200k-spec.txt OWN_VERIFY_REF=$R200 OWN_GPROF=2 OWN_GPROF_CARD=2 $DKM
say "ALLDONE $(date '+%F %T'): $n fresh starts, exits 0, identical, no fault line"
