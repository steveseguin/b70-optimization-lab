#!/bin/bash
# pp97: (2026-11-11, tp97 defaults: ATT, CK, RUX) kernel profiles of the 3K prompt read (tp97 defaults) on card 2 (16 heads) and card 0 (8 heads)
# at prompt blocks of 64 and 256 (OWN_GPROF=2 counts the prompt blocks; 2 answer tokens), to see which kernels
# keep their cost per token when the block grows (tp97: 3K read 6.80 s at 64).
set -u
W=/home/steve/dsv41-work
D=$W/runs/pp97; mkdir -p $D; sum=$D/summary.txt
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib ZES_ENABLE_SYSMAN=1
grep -q "tp97 build exit 0" $W/build-tp97.log || { echo "STOP no tp97" >> $sum; exit 1; }
until [ ! -e $W/six.active ]; do sleep 5; done
touch $W/six.active; trap 'rm -f $W/six.active' EXIT
while [ -n "$(ls -A $W/locks 2>/dev/null)" ] || pgrep -f "^/home/steve/dsv41-work/own_run_v41" > /dev/null; do sleep 10; done
J='fault response|cat error|engine reset|coredump has been created|gt reset|timedout job|exec queue reset|suspend fence|vm worker error|reset started|PCIe Bus Error|AER:|Hardware Error|Machine check'
G="OWN_MT_EU=6 OWN_MT_TGU=2 OWN_MT_RIDE=1 OWN_MT_RWG=128 OWN_MT_RFUSE=1 OWN_HC_FIN=1"
PL="OWN_TP=6 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G"
p=$W/prompts/p3k-ids.txt
for k in "c2_b64|2|64" "c2_b256|2|256" "c0_b64|0|64" "c0_b256|0|256" "c2_b128|2|128"; do
  IFS='|' read -r nm c b <<< "$k"; t0=$(date '+%Y-%m-%d %H:%M:%S')
  env $PL OWN_PROMPT_BLOCK=$b OWN_GPROF=2 OWN_GPROF_CARD=$c OWN_PROMPT=$p OWN_EOS=-1 $W/own_run_v41_tp97 - 2 $D/$nm-ids.txt 4096 > $D/$nm.log 2>&1
  echo "$nm exit $?" >> $sum; grep -h "prompt:\|rror" $D/$nm.log | sed "s/^/$nm: /" >> $sum
  f=$(journalctl -k --since "$t0" -o cat | grep -iE "$J" | head -3); [ -n "$f" ] && { echo "FAULT: $f" >> $sum; echo STOP_FAULT >> $sum; exit 1; }
done
echo ALLDONE >> $sum
