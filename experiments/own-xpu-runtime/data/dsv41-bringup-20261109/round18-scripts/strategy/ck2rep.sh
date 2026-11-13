#!/bin/bash
# ck2rep (2026-11-12): is the ops guess-log difference with OWN_CK2=1 (tg106, cycle 55) repeatable? 3 x CK2, 1 x FORMS=1, 1 x FORMS=2, 1 x off.
set -u
W=/home/steve/dsv41-work; L=/home/steve/b70-optimization-lab; D=$W/runs/ck2rep; mkdir -p $D; sum=$D/summary.txt
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib ZES_ENABLE_SYSMAN=1
J='fault response|cat error|engine reset|coredump has been created|gt reset|timedout job|exec queue reset|suspend fence|vm worker error|reset started|PCIe Bus Error|AER:|Hardware Error|Machine check'
until [ ! -e $W/six.active ]; do sleep 5; done
touch $W/six.active; trap 'rm -f $W/six.active' EXIT
while [ -n "$(ls -A $W/locks 2>/dev/null)" ] || pgrep -f "^/home/steve/dsv41-work/own_run_v41" > /dev/null || pgrep -x icpx > /dev/null || pgrep -x ocloc > /dev/null; do sleep 10; done
memwait() { local i=0; until [ $(awk '/MemAvailable/ {print int($2/1048576)}' /proc/meminfo) -ge 7 ] || [ $i -ge 120 ]; do sleep 5; i=$((i+1)); done; }
G="OWN_MT_EU=6 OWN_MT_TGU=2 OWN_MT_RIDE=1 OWN_MT_RWG=128 OWN_MT_RFUSE=1 OWN_HC_FIN=1"
PL="OWN_TP=6 OWN_PROMPT_BLOCK=64 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G"
DSP=/mnt/fast-ai/llm-models/DeepSeek-V4.1-Flash-1017-GGUF/dspark-DeepSeek-V4.1-Flash-1017-Q8_0.gguf
SPEC="OWN_MT_TGM=1:1,2:1,3:3,4:2,5:3,6:3 OWN_SPEC=5 OWN_SPEC_KMIN=0 OWN_MT_TGR=2:4,3:4,4:4,5:4,6:4 OWN_MT_TGR_ROWS=4096 OWN_DSPARK=$DSP"
VOC="OWN_DR_VOCAB=$W/draft/vocab/cand-c32k-dict.txt OWN_DR_VOCAB_N=60000"
PP=$L/experiments/own-xpu-runtime/data/dsv41-bringup-20261109/spec-prompts
REF=$W/runs/tg105v/ops_v1-spec.txt
for a in "k1|OWN_CK2=1" "k2|OWN_CK2=1" "f1|OWN_CK2=1 OWN_CK2_FORMS=1" "f2|OWN_CK2=1 OWN_CK2_FORMS=2" "off|" "k3|OWN_CK2=1"; do
  IFS='|' read -r nm ex <<< "$a"; memwait; t0=$(date '+%Y-%m-%d %H:%M:%S')
  env $PL $SPEC OWN_SPEC_TAU=0.5 $VOC $ex OWN_PROMPT=$PP/ops-ids.txt OWN_EOS=1 OWN_SPEC_LOG=$D/$nm-spec.txt OWN_VERIFY_REF=$W/runs/e57/ops_plain-ids.txt $W/own_run_v41_tp106 - 512 $D/$nm-ids.txt 4096 > $D/$nm.log 2>&1
  echo "$nm exit $?" >> $sum; grep -h "spec decode" $D/$nm.log | sed "s/^/$nm: /" | cut -c1-120 >> $sum
  python3 -I -c "
import sys
a=[l.split()[:7] for l in open('$D/$nm-spec.txt')]; b=[l.split()[:7] for l in open('$REF')]
d=[i+1 for i,(p,q) in enumerate(zip(a,b)) if p!=q]
print('$nm', 'cycles', len(a), 'vs v1: differing cycles', d[:10], len(d))" >> $sum
  f=$(journalctl -k --since "$t0" -o cat | grep -iE "$J" | head -3); [ -n "$f" ] && { echo "FAULT $f" >> $sum; exit 1; }
done
echo DONE >> $sum
