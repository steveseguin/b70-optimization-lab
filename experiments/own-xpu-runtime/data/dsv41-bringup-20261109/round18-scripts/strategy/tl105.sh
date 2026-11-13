#!/bin/bash
# tl105: check + one-token timelines on tp105 with the new defaults-to-be (OWN_FL=3 OWN_U3_NOPAIR=1) + draft vocabulary,
# for the per-extra-token budget (ck_by_m) and the one-token budget. Single queue: timelines are fine for per-kernel time.
W=/home/steve/dsv41-work; L=/home/steve/b70-optimization-lab; D=$W/runs/tl105; mkdir -p $D; sum=$D/summary.txt
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
BEST="$PL $SPEC OWN_SPEC_TAU=0.5 $VOC"
PP=$L/experiments/own-xpu-runtime/data/dsv41-bringup-20261109/spec-prompts
P1=$L/experiments/own-xpu-runtime/data/dsv41-bringup-20261109/prompt1-ids.txt
memwait; env $BEST OWN_PROMPT=$PP/code-ids.txt OWN_EOS=1 OWN_SPEC_LOG=$D/tl_ck-spec.txt OWN_TIMELINE=$D/tl_ck.txt OWN_TIMELINE_CHECKS=20-119 OWN_VERIFY_REF=$W/runs/e57/code_plain-ids.txt $W/own_run_v41_tp105 - 512 $D/tl_ck-ids.txt 4096 > $D/tl_ck.log 2>&1
echo "tl_ck exit $?" >> $sum; grep -h "spec decode\|rror" $D/tl_ck.log >> $sum
memwait; env $PL OWN_PROMPT=$P1 OWN_EOS=-1 OWN_TIMELINE=$D/tl_one.txt $W/own_run_v41_tp105 - 64 $D/tl_one-ids.txt 4096 > $D/tl_one.log 2>&1
echo "tl_one exit $?" >> $sum; grep -h "decode:\|rror" $D/tl_one.log >> $sum
journalctl -k --since "-10 min" -o cat | grep -iE "fault response|cat error|engine reset|gt reset|timedout job|Hardware Error" | head -3 >> $sum
echo DONE >> $sum
