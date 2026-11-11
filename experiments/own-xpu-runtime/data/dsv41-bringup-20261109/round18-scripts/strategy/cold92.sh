#!/bin/bash
# cold92: after pp92, what fresh text costs. The engram table (135 GB, 24 rows x 2 layers per position, 4 KiB cold
# reads) cannot stay in the page cache; the gate prompts are re-run all day, so their rows are cached and their
# speeds are warm-cache speeds. Four prompts never run before (prompts/cold), each run once cold and once warm:
# heat / bash: plain first (cold), plain again (warm), guessing (its rejected guesses cold), guessing again (warm);
# tsdb / email: guessing first (all cold), guessing again (warm), then plain (warm; the reference). Answers compared.
set -u
W=/home/steve/dsv41-work
D=$W/runs/cold92; mkdir -p $D; sum=$D/summary.txt
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib ZES_ENABLE_SYSMAN=1
until grep -qE "ALLDONE|STOP" $W/runs/pp92/summary.txt 2>/dev/null; do sleep 20; done
until [ ! -e $W/six.active ]; do sleep 5; done
touch $W/six.active; trap 'rm -f $W/six.active' EXIT
while [ -n "$(ls -A $W/locks 2>/dev/null)" ] || pgrep -f "^/home/steve/dsv41-work/own_run_v41" > /dev/null; do sleep 10; done
J='fault response|cat error|engine reset|coredump has been created|gt reset|timedout job|exec queue reset|suspend fence|vm worker error|reset started|PCIe Bus Error|AER:|Hardware Error|Machine check'
G="OWN_MT_EU=6 OWN_MT_TGU=2 OWN_MT_RIDE=1 OWN_MT_RWG=128 OWN_MT_RFUSE=1 OWN_HC_FIN=1"
PL="OWN_TP=6 OWN_PROMPT_BLOCK=64 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G"
DSP=/mnt/fast-ai/llm-models/DeepSeek-V4.1-Flash-1017-GGUF/dspark-DeepSeek-V4.1-Flash-1017-Q8_0.gguf
SPEC="OWN_MT_TGM=1:1,2:1,3:3,4:2,5:3,6:3 OWN_SPEC=5 OWN_SPEC_KMIN=0 OWN_MT_TGR=2:4,3:4,4:4,5:4,6:4 OWN_MT_TGR_ROWS=4096 OWN_DSPARK=$DSP OWN_SPEC_TAU=0.5"
C=$W/prompts/cold
r() { local name=$1 n=$2; shift 2; local t0; t0=$(date '+%Y-%m-%d %H:%M:%S')
  env $PL "$@" OWN_PROMPT=$C/$n-ids.txt OWN_EOS=1 $W/own_run_v41_tp92 - 512 $D/$name-ids.txt 4096 > $D/$name.log 2>&1
  local rc=$?; echo "$name exit $rc" >> $sum
  grep -h "decode:\|spec decode\|host io\|rror" $D/$name.log | sed "s/^/$name: /" >> $sum
  f=$(journalctl -k --since "$t0" -o cat | grep -iE "$J" | head -3); [ -n "$f" ] && { echo "FAULT: $f" >> $sum; echo STOP_FAULT >> $sum; exit 1; }
  [ $rc -eq 0 ] || { echo STOP_EXIT >> $sum; exit 1; }; }
for n in heat bash; do
  r ${n}_plain_cold $n
  r ${n}_plain_warm $n
  r ${n}_spec_cold $n $SPEC OWN_VERIFY_REF=$D/${n}_plain_cold-ids.txt OWN_SPEC_LOG=$D/${n}_spec_cold-spec.txt
  r ${n}_spec_warm $n $SPEC OWN_VERIFY_REF=$D/${n}_plain_cold-ids.txt OWN_SPEC_LOG=$D/${n}_spec_warm-spec.txt
  cmp -s $D/${n}_plain_cold-ids.txt $D/${n}_plain_warm-ids.txt && echo "$n plain cold/warm SAME" >> $sum || echo "$n plain cold/warm DIFFER" >> $sum
done
for n in tsdb email; do
  r ${n}_spec_cold $n $SPEC OWN_SPEC_LOG=$D/${n}_spec_cold-spec.txt
  r ${n}_spec_warm $n $SPEC OWN_SPEC_LOG=$D/${n}_spec_warm-spec.txt
  r ${n}_plain_warm $n
  for s in cold warm; do
    m=$(wc -l < $D/${n}_plain_warm-ids.txt)
    cmp -s <(head -$m $D/${n}_spec_$s-ids.txt) $D/${n}_plain_warm-ids.txt && echo "$n spec_$s SAME as plain ($m ids)" >> $sum || echo "$n spec_$s DIFFER from plain" >> $sum
  done
done
echo ALLDONE >> $sum
