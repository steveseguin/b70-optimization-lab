#!/bin/bash
# tlp109 (2026-11-13): prompt timelines on tp109 (blocks 3-4 of the 3K read): px-512 with the copy engine (production
# prompt mode) and plain blocks of 256, for the next prompt budget. Profiling on: per-kernel times, not speed numbers.
set -u
W=/home/steve/dsv41-work; L=/home/steve/b70-optimization-lab; D=$W/runs/tlp109; mkdir -p $D; sum=$D/summary.txt
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib ZES_ENABLE_SYSMAN=1
J='fault response|cat error|engine reset|coredump has been created|gt reset|timedout job|exec queue reset|suspend fence|vm worker error|reset started|PCIe Bus Error|AER:|Hardware Error|Machine check'
until [ ! -e $W/six.active ]; do sleep 5; done
touch $W/six.active; trap 'rm -f $W/six.active' EXIT
while [ -n "$(ls -A $W/locks 2>/dev/null)" ] || pgrep -f "^/home/steve/dsv41-work/own_run_v41" > /dev/null || pgrep -x icpx > /dev/null || pgrep -x ocloc > /dev/null; do sleep 10; done
memwait() { local i=0; until [ $(awk '/MemAvailable/ {print int($2/1048576)}' /proc/meminfo) -ge 7 ] || [ $i -ge 120 ]; do sleep 5; i=$((i+1)); done; }
G="OWN_MT_EU=6 OWN_MT_TGU=2 OWN_MT_RIDE=1 OWN_MT_RWG=128 OWN_MT_RFUSE=1 OWN_HC_FIN=1"
PL="OWN_TP=6 OWN_PROMPT_BLOCK=64 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G"
p=$W/prompts/p3k-ids.txt
for k in "tlp_px512|OWN_PROMPT_BLOCK=512 OWN_PX=1 OWN_PX_BIG=1" "tlp_b256|OWN_PROMPT_BLOCK=256"; do
  IFS='|' read -r name envs <<< "$k"; t0=$(date '+%Y-%m-%d %H:%M:%S'); memwait
  env $PL $envs OWN_PROMPT=$p OWN_EOS=-1 OWN_TIMELINE=$D/$name.txt OWN_TIMELINE_PROMPT=3-4 $W/own_run_v41_tp109 - 8 $D/$name-ids.txt 4096 > $D/$name.log 2>&1
  echo "$name exit $?" >> $sum; grep -h "prompt:\|rror" $D/$name.log | sed "s/^/$name: /" >> $sum
  f=$(journalctl -k --since "$t0" -o cat | grep -iE "$J" | head -3); [ -n "$f" ] && { echo "FAULT: $f" >> $sum; echo STOP_FAULT >> $sum; exit 1; }
  sleep 20
done
echo ALLDONE >> $sum
