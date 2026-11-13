#!/bin/bash
# tau0: guessing with every guess checked (OWN_SPEC_TAU=0: no confidence cut) on all five prompts, tp105 + FL3 + NOPAIR
# + draft vocabulary: full acceptance data for an offline cost-aware selection policy (Codex suggestion, 2026-11-12).
W=/home/steve/dsv41-work; L=/home/steve/b70-optimization-lab; D=$W/runs/tau0; mkdir -p $D; sum=$D/summary.txt
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib ZES_ENABLE_SYSMAN=1
until [ ! -e $W/six.active ]; do sleep 5; done
touch $W/six.active; trap 'rm -f $W/six.active' EXIT
while [ -n "$(ls -A $W/locks 2>/dev/null)" ] || pgrep -f "^/home/steve/dsv41-work/own_run_v41" > /dev/null || pgrep -x icpx > /dev/null || pgrep -x ocloc > /dev/null; do sleep 10; done
memwait() { local i=0; until [ $(awk '/MemAvailable/ {print int($2/1048576)}' /proc/meminfo) -ge 7 ] || [ $i -ge 120 ]; do sleep 5; i=$((i+1)); done; }
G="OWN_MT_EU=6 OWN_MT_TGU=2 OWN_MT_RIDE=1 OWN_MT_RWG=128 OWN_MT_RFUSE=1 OWN_HC_FIN=1 OWN_FL=3 OWN_U3_NOPAIR=1"
PL="OWN_TP=6 OWN_PROMPT_BLOCK=64 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G"
DSP=/mnt/fast-ai/llm-models/DeepSeek-V4.1-Flash-1017-GGUF/dspark-DeepSeek-V4.1-Flash-1017-Q8_0.gguf
SPEC="OWN_MT_TGM=1:1,2:1,3:3,4:2,5:3,6:3 OWN_SPEC=5 OWN_SPEC_KMIN=0 OWN_MT_TGR=2:4,3:4,4:4,5:4,6:4 OWN_MT_TGR_ROWS=4096 OWN_DSPARK=$DSP"
VOC="OWN_DR_VOCAB=$W/draft/vocab/cand-c32k-dict.txt OWN_DR_VOCAB_N=60000"
PP=$L/experiments/own-xpu-runtime/data/dsv41-bringup-20261109/spec-prompts
for n in code analysis prose docs ops; do
  memwait; t0=$(date '+%Y-%m-%d %H:%M:%S')
  env $PL $SPEC OWN_SPEC_TAU=0 $VOC OWN_PROMPT=$PP/$n-ids.txt OWN_EOS=1 OWN_SPEC_LOG=$D/${n}_t0-spec.txt OWN_VERIFY_REF=$W/runs/e57/${n}_plain-ids.txt $W/own_run_v41_tp105 - 512 $D/${n}_t0-ids.txt 4096 > $D/${n}_t0.log 2>&1
  echo "${n}_t0 exit $?" >> $sum; grep -h "spec decode\|rror" $D/${n}_t0.log | sed "s/^/${n}_t0: /" >> $sum
  journalctl -k --since "$t0" -o cat | grep -iE "fault response|cat error|engine reset|gt reset|timedout job|Hardware Error" | head -3 >> $sum
done
echo DONE >> $sum
