#!/bin/bash
# (1) one-token routed expert kernels on card 0: work-group sweep at the six-card shapes + the R-rows-per-
# sub-group candidate (bitwise vs production); (2) tp51 built ahead of time (tp51aot): start-up time, trace
# gate (blocks of 16 with row blocks, and blocks of 5), 128-token plain answers, HC_FIN=1
set -u
S=/tmp/claude-1000/-home-steve/6f61a0f6-fd06-49a3-b5b4-babc9645cc37/scratchpad
while systemctl --user is-active -q dsv41-e61; do sleep 3; done
D=$S/runs/e62
mkdir -p $D
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib ZES_ENABLE_SYSMAN=1
sum=$D/summary.txt
J='fault response|cat error|engine reset|coredump has been created|gt reset'
t0=$(date '+%Y-%m-%d %H:%M:%S')
$S/bench_routed_m1 0 > $D/routed_m1.log 2>&1; echo "routed_m1 exit $?" >> $sum; cat $D/routed_m1.log >> $sum
journalctl -k --since "$t0" -o cat | grep -iE "$J" | head -3 >> $sum
grep -q "fault response\|engine reset" $sum && { echo STOP >> $sum; exit 1; }
G="OWN_MT_EU=6 OWN_MT_TGU=2 OWN_MT_RIDE=1 OWN_MT_RWG=128 OWN_MT_RFUSE=1 OWN_HC_FIN=1"
ts=$(date +%s)
$S/run_exp.sh e62 tp51aot "pa1|OWN_TP=6 OWN_PROMPT_BLOCK=16 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G|speed"
echo "pa1 wall $(( $(date +%s) - ts )) s (first run of the ahead-of-time build)" >> $sum
$S/run_exp.sh e62 tp51aot "pa2|OWN_TP=6 OWN_PROMPT_BLOCK=16 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G|speed" \
  "ha16|OWN_TP=6 OWN_TP_THREADS=1 OWN_PROMPT_BLOCK=16 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G OWN_MT_TGR=16:4,1:4 OWN_MT_TGR_ROWS=0|trace" \
  "ha5|OWN_TP=6 OWN_TP_THREADS=1 OWN_PROMPT_BLOCK=5 OWN_MT_TGM=1:1,2:1,3:3,4:2,5:3 $G|trace" \
  "pa3|OWN_TP=6 OWN_PROMPT_BLOCK=16 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G|speed"
echo ALLDONE >> $sum
