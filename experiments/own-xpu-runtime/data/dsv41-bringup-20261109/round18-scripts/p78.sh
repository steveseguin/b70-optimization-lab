#!/bin/bash
# p78: where OWN_MT_W16's time went: the 3K document read in blocks of 16 by tp78 with OWN_MT_W16=1 / 0, OWN_GPROF=2 on
# card 2 (12 heads) and card 4 (8 heads); 2 answer tokens each. Short runs only.
set -u
W=/home/steve/dsv41-work; D=$W/runs/p78; mkdir -p $D; sum=$D/summary.txt
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib ZES_ENABLE_SYSMAN=1
J='fault response|cat error|engine reset|coredump has been created|gt reset|timedout job|exec queue reset|suspend fence|vm worker error|reset started|PCIe Bus Error|AER:|Hardware Error|Machine check'
G="OWN_MT_EU=6 OWN_MT_TGU=2 OWN_MT_RIDE=1 OWN_MT_RWG=128 OWN_MT_RFUSE=1 OWN_HC_FIN=1"
PL="OWN_TP=6 OWN_PROMPT_BLOCK=16 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G"
for k in "on2 1 2" "off2 0 2" "on4 1 4" "off4 0 4"; do
  set -- $k; t0=$(date '+%Y-%m-%d %H:%M:%S')
  env $PL OWN_MT_W16=$2 OWN_GPROF=2 OWN_GPROF_CARD=$3 OWN_PROMPT=$W/prompts/p3k-ids.txt OWN_EOS=-1 $W/own_run_v41_tp78 - 2 $D/$1-ids.txt 4096 > $D/$1.log 2>&1
  echo "$1 exit $?" >> $sum; grep -h "prompt:" $D/$1.log | sed "s/^/$1: /" >> $sum
  f=$(journalctl -k --since "$t0" -o cat | grep -iE "$J" | grep -vE '^\{[0-9]+\}\[Hardware Error\]'); [ -n "$f" ] && { echo "$f" | head -3 | sed 's/^/FAULT: /' >> $sum; echo STOP >> $sum; exit 1; }
done
echo ALLDONE >> $sum
