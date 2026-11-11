#!/bin/bash
# bis88: which tp88 block-path option changes the trace (tg88 STOP_GATE1: h5n / h16n / h64n differ, h1n identical)
set -u
W=/home/steve/dsv41-work; sum=$W/runs/tg88/summary.txt
touch $W/six.active; trap 'rm -f $W/six.active' EXIT
while [ -n "$(ls -A $W/locks 2>/dev/null)" ] || pgrep -f "own_run_v41_" > /dev/null; do sleep 5; done
G="OWN_MT_EU=6 OWN_MT_TGU=2 OWN_MT_RIDE=1 OWN_MT_RWG=128 OWN_MT_RFUSE=1 OWN_HC_FIN=1"
T5="OWN_TP=6 OWN_TP_THREADS=1 OWN_PROMPT_BLOCK=5 OWN_MT_TGM=1:1,2:1,3:3,4:2,5:3 $G"
echo "bis88: bisect" >> $sum
for k in "h5cq|$T5 OWN_ENG_CQ=1" "h5pk|$T5 OWN_PRE_K=1" "h5am|$T5 OWN_ATT_M=1"; do
  IFS='|' read -r name envs <<< "$k"; $W/run_exp.sh tg88 tp88 "$name|$envs|trace"; sed -i '/^DONE$/d' $sum
done
echo BISDONE >> $sum
