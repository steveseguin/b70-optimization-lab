#!/bin/bash
# pxdbg: (1) where; (2) OWN_MT_RFUSE=0 with PX on unfixed tp102 (the fused router read the block base: pb256 helper) + its non-PX twin, twice each. where the OWN_PX 3K trace first differs (tp102, blocks of 256, PX_SERIAL: deterministic) + the 128 form
set -u
W=/home/steve/dsv41-work
D=$W/runs/pxdbg; mkdir -p $D; sum=$D/summary.txt
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib ZES_ENABLE_SYSMAN=1
J='fault response|cat error|engine reset|coredump has been created|gt reset|timedout job|exec queue reset|suspend fence|vm worker error|reset started|PCIe Bus Error|AER:|Machine check'
fcheck() { local f; f=$(journalctl -k --since "$1" -o cat | grep -iE "$J" | grep -vE '^\{[0-9]+\}\[Hardware Error\]'); [ -z "$f" ] && return 0
  echo "$f" | head -3 | sed 's/^/FAULT: /' >> $sum; echo STOP_FAULT >> $sum; exit 1; }
until [ ! -e $W/six.active ]; do sleep 5; done
touch $W/six.active; trap 'rm -f $W/six.active' EXIT
while [ -n "$(ls -A $W/locks 2>/dev/null)" ] || pgrep -f "^/home/steve/dsv41-work/own_run_v41" > /dev/null || pgrep -x icpx > /dev/null || pgrep -x ocloc > /dev/null; do sleep 10; done
until [ $(awk '/MemAvailable/ {print int($2/1048576)}' /proc/meminfo) -ge 7 ]; do sleep 5; done
G="OWN_MT_EU=6 OWN_MT_TGU=2 OWN_MT_RIDE=1 OWN_MT_RWG=128 OWN_MT_RFUSE=1 OWN_HC_FIN=1"
TB="OWN_TP=6 OWN_TP_THREADS=1 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G OWN_MT_TGR=16:4,1:4 OWN_MT_TGR_ROWS=0"
REF=$W/runs/gm64/t3k_ref
for k in "ser256|OWN_PROMPT_BLOCK=256 OWN_PX=1 OWN_PX_SERIAL=1" "rf0px|OWN_PROMPT_BLOCK=256 OWN_PX=1 OWN_MT_RFUSE=0" "rf0base|OWN_PROMPT_BLOCK=256 OWN_MT_RFUSE=0" "rf0px2|OWN_PROMPT_BLOCK=256 OWN_PX=1 OWN_MT_RFUSE=0" "rf0base2|OWN_PROMPT_BLOCK=256 OWN_MT_RFUSE=0"; do
  IFS='|' read -r nm envs <<< "$k"; t0=$(date '+%Y-%m-%d %H:%M:%S')
  env $TB $envs OWN_TRACE=$D/$nm.trc OWN_TRACE_STEPS=3 OWN_PROMPT=$W/prompts/p3k-ids.txt OWN_EOS=1 $W/own_run_v41_tp102 - 40 $D/$nm-ids.txt 4096 > $D/$nm.log 2>&1
  echo "$nm exit $?" >> $sum; fcheck "$t0"
  cmp -s $D/$nm.trc $REF.trc && echo "$nm TRACE_IDENTICAL" >> $sum || echo "$nm TRACE_DIFFERS" >> $sum
  cmp -s $D/$nm-ids.txt $REF-ids.txt && echo "$nm IDS40_SAME" >> $sum || echo "$nm IDS40_DIFFER" >> $sum
  grep -E "prompt:" $D/$nm.log | sed "s/^/$nm: /" >> $sum
  python3 -I $W/tools/trc_first.py $REF.trc $D/$nm.trc 2>&1 | head -30 | sed "s/^/$nm: /" >> $sum
done
echo ALLDONE >> $sum
