#!/bin/bash
# tm1p (2026-11-16): tm1 on tp118p (= tp118 + privmem-1 + tpd-2; c118p its gate), else unchanged.
# tm1 (2026-11-15): topk-m (OWN_TOPK_M=1, in tp118 when it built from 98a7e74211): the one-token index selects past
# the register forms' reach in two launches. 388,251 tokens: ratio-2 sources 194K rows (rows form) and layer 20's
# 48.5K blocks (block form). (1) 1024 answers vs lc2's (OWN_TOPK_M=0 speed 76.90 tok/s); (2) the built-in check
# (OWN_DEV_INDEX_CHECK=1: every list and layer-20 flag against the host's, also the masked rows form, since the check
# turns the candidate-only path off), 16 answers; (3) 704,773 tokens, 1024 answers vs c117's x700k_def. Diagnostic
# configuration, preflight, synced logs, first fault / non-zero exit / mismatch = STOP (no retry / reset / reboot).
{ [ -e /home/steve/dsv41-work/defer-120c ] || [ -e /home/steve/dsv41-work/defer-122 ]; } && { echo "$(date '+%F %T') $(basename $0) deferred (defer-120c / defer-122: a later queue runs it)" >> /home/steve/dsv41-work/chainq118.txt; exit 0; }
set -u
W=/home/steve/dsv41-work; L=/home/steve/b70-optimization-lab
B=$W/own_run_v41_tp118p
# (2026-11-16 12:3x) tp120 (+ privmem-2, eng-gate-1: one card's host thread held up ~1.3-1.7 s stopped c118 x200k,
# c118p x700k_off and tlx1 x400k) when it built and its gate c120 passed; else tp118p as before
c120s=$(ls -td $W/runs/c120-*/ 2>/dev/null | head -1)
if [ -x $W/own_run_v41_tp120 ] && grep -q "tp120 build exit 0" $W/build-tp120.log 2>/dev/null && [ -n "$c120s" ] && grep -q "^ALLDONE" ${c120s}summary.txt; then B=$W/own_run_v41_tp120; fi
TS=$(date +%Y%m%dT%H%M); D=$W/runs/tm1p-$TS; mkdir -p $D
sum=$D/summary.txt; marks=$D/marks.txt
say() { echo "$*" >> $sum; sync -f $sum 2>/dev/null || sync; }
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib ZES_ENABLE_SYSMAN=1
g=$(cat $W/six.active 2>/dev/null); case "$g" in ""|tm1p) ;; *) say "STOP six.active held by $g"; exit 1;; esac
ls $W/locks/ | grep -q . && { say "STOP a lock is held: $(ls $W/locks)"; exit 1; }
echo tm1p > $W/six.active; sync
pgrep -f "^/home/steve/dsv41-work/own_run_v41" > /dev/null && { say "STOP engine running"; exit 1; }
journalctl -k -f -o short-precise > $D/kernel-follow.txt 2>&1 & JF=$!
( while true; do sleep 5; sync -f $D/kernel-follow.txt $D/mem.txt 2>/dev/null; done ) & SY=$!
( while true; do echo "$(date +%T.%N | cut -c1-10) $(awk '/MemAvailable/ {print int($2/1024)}' /proc/meminfo)"; sleep 0.5; done >> $D/mem.txt ) & MS=$!
trap 'kill $JF $SY $MS 2>/dev/null; rm -f $W/six.active; sync' EXIT
source $W/stable/stable.env
say "tm1p start $(date '+%F %T') boot $(cut -c1-8 /proc/sys/kernel/random/boot_id) binary $(basename $B) $(sha256sum $B | cut -c1-16)"
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
case $B in *tp120) grep "source commit" $W/build-tp120.log | tail -1 | grep -qE "fe2eae1ab2" || stop "tp120 is not fe2eae1ab2";;
  *) grep "source commit" $W/build-tp118p.log | tail -1 | grep -qE "5d6c2ae46a" || stop "tp118p is not the topk-m + privmem-1 build";; esac
x400=$W/prompts/lc/x400k-ids.txt
run m400k $x400 1024 $(mx $x400 1024) $W/runs/lc2-20261115T1948/x400k_def-ids.txt 1024 $PL $P5 OWN_TOPK_M=1
grep -h "dev_index check" $D/m400k.log | tail -1 >> $sum
# m400chk dropped 2026-11-16 20:52: OWN_DEV_INDEX_CHECK=1 refuses OWN_PX and OWN_IDX_SPLIT (the production modes); m400k is the exact check
# run m400chk $x400 16 $(mx $x400 1024) $W/runs/lc2-20261115T1948/x400k_def-ids.txt 16 $PL $P5 OWN_TOPK_M=1 OWN_DEV_INDEX_CHECK=1 OWN_IDX_SPLIT=0
# grep -h "dev_index check" $D/m400chk.log | tail -2 | sed "s/^/m400chk: /" >> $sum; sync -f $sum
# grep "dev_index check: .* lists" $D/m400chk.log | tail -1 | grep -q " 0 mismatches" || stop "m400chk: the index check reports mismatches (or no line)"
c7=$(ls -td $W/runs/c118p-*/ | head -1)
x700=$W/prompts/lc/x700k-ids.txt
[ -s ${c7}x700k_def-ids.txt ] || stop "no c118p x700k_def reference"
run m700k $x700 1024 $(mx $x700 1024) ${c7}x700k_def-ids.txt 1024 $PL $P5 OWN_TOPK_M=1
say "ALLDONE $(date '+%F %T'): $n fresh starts, exits 0, identical, no fault line"
