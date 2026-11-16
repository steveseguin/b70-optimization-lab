#!/bin/bash
# lc2 (2026-11-15): after lc1 (194,000 tokens exact, fact found), 388,251 tokens: doc2.txt (doc.txt + 175 experiments / packages READMEs, sha256 253d12f344335ffe, cut at 1,375,000 chars), a planted fact at
# 2 % (prompts/lc/mk_needle.py, ids aff7f0bc3a8f3bee), 1024 plain answer tokens, in the
# current diagnostic configuration (SMT off, Gen4 x16, OWN_PX_SERIAL=1, default power, BIOS 11.02: preflight before
# each case, never changed here). Existing tp115 binary. Case 1 = production prompt mode; case 2 = the same with
# tp115's default-on switches off (OWN_SKIP39=0 OWN_IDX_DSPLIT=0, as c115's x95k_off): its 1024 answers must equal
# case 1's. Memory: ~6.2 KB per context token per card (c115 3K..95K) -> ~0.9 GiB free after load on card 2 (lc1: 2.00 at 195,584).
# Host floor 2560 MiB (default 3072): lc1-20261115T1934 stopped at 3072 during upload (start 12,872 MiB; a normal
# upload takes ~9.6-9.8 GB of MemAvailable: c115 13,811 -> 4,014). MemAvailable sampled every 0.5 s to mem.txt.
# First fault / non-zero exit / mismatch = STOP, no retry / reset / reboot. Logs synced after every line.
set -u
W=/home/steve/dsv41-work; L=/home/steve/b70-optimization-lab
TS=$(date +%Y%m%dT%H%M); D=$W/runs/lc2-$TS; mkdir -p $D
sum=$D/summary.txt; marks=$D/marks.txt
say() { echo "$*" >> $sum; sync -f $sum 2>/dev/null || sync; }
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib ZES_ENABLE_SYSMAN=1
g=$(cat $W/six.active 2>/dev/null); case "$g" in ""|lc2) ;; *) say "STOP six.active held by $g"; exit 1;; esac
echo lc2 > $W/six.active; sync
pgrep -f "^/home/steve/dsv41-work/own_run_v41" > /dev/null && { say "STOP engine running"; exit 1; }
journalctl -k -f -o short-precise > $D/kernel-follow.txt 2>&1 & JF=$!
( while true; do sleep 5; sync -f $D/kernel-follow.txt $D/mem.txt 2>/dev/null; done ) & SY=$!
( while true; do echo "$(date +%T.%N | cut -c1-10) $(awk '/MemAvailable/ {print int($2/1024)}' /proc/meminfo)"; sleep 0.5; done >> $D/mem.txt ) & MS=$!
trap 'kill $JF $SY $MS 2>/dev/null; rm -f $W/six.active; sync' EXIT
source $W/stable/stable.env
say "lc2 start $(date '+%F %T') boot $(cut -c1-8 /proc/sys/kernel/random/boot_id) binary $(sha256sum $W/own_run_v41_tp115 | cut -c1-16)"
say "smt active $(cat /sys/devices/system/cpu/smt/active), cpus $(nproc), bios $(cat /sys/class/dmi/id/bios_version)"
J='fault response|cat error|engine reset|coredump has been created|gt reset|timedout job|exec queue reset|suspend fence|vm worker error|reset started|PCIe Bus Error|AER:|Hardware Error|Machine check|watchdog: BUG|rcu_sched self-detected|AMD-Vi: Event|wedged|inaccessible|GuC'
stop() { say "STOP $*"; say "STOPPED $(date '+%F %T')"; exit 1; }
pre() { local o; o=$($W/stable/preflight.sh 2>&1) || stop "preflight: $o"; }
G="OWN_MT_EU=6 OWN_MT_TGU=2 OWN_MT_RIDE=1 OWN_MT_RWG=128 OWN_MT_RFUSE=1 OWN_HC_FIN=1"
PL="OWN_TP=6 OWN_PROMPT_BLOCK=64 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G"
P5="OWN_PROMPT_BLOCK=512 OWN_PX=1 OWN_PX_BIG=1 OWN_HOST_FLOOR_MIB=2560"
memwait() { local i=0; until [ $(awk '/MemAvailable/ {print int($2/1048576)}' /proc/meminfo) -ge 7 ] || [ $i -ge 120 ]; do sleep 5; i=$((i+1)); done; }
n=0
run() { local name=$1 pr=$2 nt=$3 mx=$4; shift 4; local t0 rc f
  pre; memwait; n=$((n+1)); t0=$(date '+%F %T')
  echo "$name start $(date '+%T.%N' | cut -c1-12)" >> $marks; sync -f $marks
  env "$@" OWN_PROMPT=$pr OWN_EOS=-1 $W/own_run_v41_tp115 - $nt $D/$name-ids.txt $mx > $D/$name.log 2>&1; rc=$?
  echo "$name end $(date '+%T.%N' | cut -c1-12) rc $rc" >> $marks; sync -f $marks
  journalctl -k --since "$t0" -o short-precise > $D/$name-kernel.txt 2>&1
  grep -h "prompt:\|decode:\|free after load\|rror\|timed out\|exceeds\|MISMATCH\|DIFFER\|BAD:" $D/$name.log | sed "s/^/$name: /" >> $sum
  say "$name exit $rc (case $n)"
  f=$(grep -iE "$J" $D/$name-kernel.txt | head -3); [ -n "$f" ] && stop "$name kernel: $f"
  [ $rc -eq 0 ] || stop "$name exit $rc"
  grep -qE "MISMATCH|DIFFERS from|DIFFERENT FROM|BAD:" $D/$name.log && stop "$name: a check line reports a difference"; }
p=$W/prompts/lc/x400k-ids.txt; NT=1024
mx=$(( ( $(wc -l < $p) + NT + 1023 ) / 1024 * 1024 ))
say "prompt $(wc -l < $p) tokens, $NT answers, max ctx $mx"
run x400k_def $p $NT $mx $PL $P5
run x400k_off $p $NT $mx $PL $P5 OWN_SKIP39=0 OWN_IDX_DSPLIT=0
cmp -s $D/x400k_def-ids.txt $D/x400k_off-ids.txt && say "x400k_off IDS${NT}_SAME as x400k_def" || stop "x400k_off IDS_DIFFER from x400k_def"
say "ALLDONE $(date '+%F %T'): $n fresh starts, exits 0, answers identical across the two modes, no fault line"
