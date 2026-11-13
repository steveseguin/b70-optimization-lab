#!/bin/bash
# tlpx109 (2026-11-13): prompt timeline on tp109 deep in a 34K document (px-512 + copy engine, blocks 62-63), for the long-context prompt budget.
set -u
W=/home/steve/dsv41-work; L=/home/steve/b70-optimization-lab; D=$W/runs/tlpx109; mkdir -p $D; sum=$D/summary.txt
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib ZES_ENABLE_SYSMAN=1
J='fault response|cat error|engine reset|coredump has been created|gt reset|timedout job|exec queue reset|suspend fence|vm worker error|reset started|PCIe Bus Error|AER:|Hardware Error|Machine check'
sleep 200  # quiet window for one-card helpers (180 s rule)
until [ ! -e $W/six.active ]; do sleep 5; done
touch $W/six.active; trap 'rm -f $W/six.active' EXIT
while [ -n "$(ls -A $W/locks 2>/dev/null)" ] || pgrep -f "^/home/steve/dsv41-work/own_run_v41" > /dev/null || pgrep -x icpx > /dev/null || pgrep -x ocloc > /dev/null; do sleep 10; done
memwait() { local i=0; until [ $(awk '/MemAvailable/ {print int($2/1048576)}' /proc/meminfo) -ge 7 ] || [ $i -ge 120 ]; do sleep 5; i=$((i+1)); done; }
G="OWN_MT_EU=6 OWN_MT_TGU=2 OWN_MT_RIDE=1 OWN_MT_RWG=128 OWN_MT_RFUSE=1 OWN_HC_FIN=1"
PL="OWN_TP=6 OWN_PROMPT_BLOCK=64 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G"
p=$W/prompts/xl/x34k-ids.txt; mx=$(( ( $(wc -l < $p) + 256 + 1023 ) / 1024 * 1024 ))
name=tlpx_34k; t0=$(date '+%Y-%m-%d %H:%M:%S'); memwait
env $PL OWN_PROMPT_BLOCK=512 OWN_PX=1 OWN_PX_BIG=1 OWN_PROMPT=$p OWN_EOS=-1 OWN_TIMELINE=$D/$name.txt OWN_TIMELINE_PROMPT=62-63 $W/own_run_v41_tp109 - 8 $D/$name-ids.txt $mx > $D/$name.log 2>&1
echo "$name exit $?" >> $sum; grep -h "prompt:\|rror\|free after load" $D/$name.log | sed "s/^/$name: /" >> $sum
f=$(journalctl -k --since "$t0" -o cat | grep -iE "$J" | head -3); [ -n "$f" ] && { echo "FAULT: $f" >> $sum; echo STOP_FAULT >> $sum; exit 1; }
echo ALLDONE >> $sum
