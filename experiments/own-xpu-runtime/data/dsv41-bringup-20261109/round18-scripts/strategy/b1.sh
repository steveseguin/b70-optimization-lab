#!/bin/bash
# b1: step budget data. tp82 (committed defaults). Per card 0..5: answer-step profile (prompt 1, 48 tokens,
# OWN_GPROF=2 OWN_GPROF_DECODE=1) and the 3K prompt read profile (OWN_GPROF=2, one answer token, so every kernel
# is the prompt's); one unprofiled 128-token run for the real step time. SHORT runs only.
set -u
W=/home/steve/dsv41-work
D=$W/runs/b1; mkdir -p $D
sum=$D/summary.txt
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib ZES_ENABLE_SYSMAN=1
J='fault response|cat error|engine reset|coredump has been created|gt reset|timedout job|exec queue reset|suspend fence|vm worker error|reset started|PCIe Bus Error|AER:|Hardware Error|Machine check'
fcheck() { local f; f=$(journalctl -k --since "$1" -o cat | grep -iE "$J"); [ -z "$f" ] && return 0
  echo "$f" | head -3 | sed 's/^/FAULT: /' >> $sum; echo STOP_FAULT >> $sum; exit 1; }
python3 -I $W/tools/gpu_sampler.py $D/telemetry.smp 0.05 & SP=$!
trap 'kill $SP 2>/dev/null' EXIT
G="OWN_MT_EU=6 OWN_MT_TGU=2 OWN_MT_RIDE=1 OWN_MT_RWG=128 OWN_MT_RFUSE=1 OWN_HC_FIN=1"
PL="OWN_TP=6 OWN_PROMPT_BLOCK=16 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G"
P1=/home/steve/b70-optimization-lab/experiments/own-xpu-runtime/data/dsv41-bringup-20261109/prompt1-ids.txt
P3=$W/prompts/p3k-ids.txt
B=$W/own_run_v41_tp82
run() { local name=$1 pr=$2 nt=$3; shift 3; local t0; t0=$(date '+%Y-%m-%d %H:%M:%S')
  env "$@" OWN_PROMPT=$pr OWN_EOS=-1 $B - $nt $D/$name-ids.txt 4096 > $D/$name.log 2>&1
  local rc=$?; echo "$name exit $rc" >> $sum
  grep -h "prompt:\|decode:\|rror\|timed out" $D/$name.log | sed "s/^/$name: /" >> $sum
  fcheck "$t0"; [ $rc -eq 0 ] || { echo STOP_EXIT >> $sum; exit 1; }; }
run plain $P1 128 $PL
for c in 0 1 2 3 4 5; do
  run dec_c$c $P1 48 $PL OWN_GPROF=2 OWN_GPROF_DECODE=1 OWN_GPROF_CARD=$c
  run pre_c$c $P3 1 $PL OWN_GPROF=2 OWN_GPROF_CARD=$c
done
echo ALLDONE >> $sum
