#!/bin/bash
# after e57: (1) row-blocked dense rows bench on card 0 (bitwise + cold timing); (2) tp46 adaptive guesses:
# OWN_SPEC=5 with OWN_SPEC_TAU 0.3 / 0.4 / 0.5 against fixed k=3, five prompts + 3K; fixed k=1 / k=2 on code
set -u
S=/tmp/claude-1000/-home-steve/6f61a0f6-fd06-49a3-b5b4-babc9645cc37/scratchpad
while systemctl --user is-active -q dsv41-e57; do sleep 3; done
B=tp46; D=$S/runs/e58; bin=$S/own_run_v41_$B
mkdir -p $D
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib ZES_ENABLE_SYSMAN=1
sum=$D/summary.txt
J='fault response|cat error|engine reset|coredump has been created|gt reset'
t0=$(date '+%Y-%m-%d %H:%M:%S')
$S/bench_dense_rowblock 0 > $D/bench.log 2>&1; echo "bench exit $?" >> $sum
journalctl -k --since "$t0" -o cat | grep -iE "$J" | head -3 >> $sum
grep -q "fault response\|engine reset" $sum && { echo STOP >> $sum; exit 1; }
PP=/home/steve/b70-optimization-lab/experiments/own-xpu-runtime/data/dsv41-bringup-20261109/spec-prompts
R57=$S/runs/e57
DS=/mnt/fast-ai/llm-models/DeepSeek-V4.1-Flash-1017-GGUF/dspark-DeepSeek-V4.1-Flash-1017-Q8_0.gguf
BASE="OWN_TP=6 OWN_PROMPT_BLOCK=16 OWN_MT_TG=4 OWN_MT_TG_MAX=16 OWN_MT_EU=6 OWN_MT_TGU=2 OWN_MT_RIDE=1 OWN_MT_RWG=128 OWN_MT_RFUSE=1 OWN_MT_TGM=2:1,3:3,4:2,5:3,6:3"
s() { local name=$1 pr=$2 ref=$3 nt=$4 ms=$5 eos=$6; shift 6; t0=$(date '+%Y-%m-%d %H:%M:%S')
  env $BASE "$@" OWN_PROMPT=$pr OWN_EOS=$eos OWN_VERIFY_REF=$ref OWN_DSPARK=$DS $bin - $nt $D/$name-ids.txt $ms > $D/$name.log 2>&1
  echo "$name exit $?" >> $sum; grep -h "spec decode\|kept guesses\|rror\|timed out" $D/$name.log | sed "s/^/$name: /" >> $sum
  journalctl -k --since "$t0" -o cat | grep -iE "$J" | head -3 >> $sum; }
s code_k1 $PP/code-ids.txt $R57/code_plain-ids.txt 512 4096 1 OWN_SPEC=1
s code_k2 $PP/code-ids.txt $R57/code_plain-ids.txt 512 4096 1 OWN_SPEC=2
for n in code prose analysis ops docs; do
  s ${n}_s3 $PP/$n-ids.txt $R57/${n}_plain-ids.txt 512 4096 1 OWN_SPEC=3
  for t in 3 4 5; do
    s ${n}_t$t $PP/$n-ids.txt $R57/${n}_plain-ids.txt 512 4096 1 OWN_SPEC=5 OWN_SPEC_TAU=0.$t OWN_SPEC_LOG=$D/${n}_t$t.conf
  done
done
s p3k_s3 $S/prompts/p3k-ids.txt $S/runs/e52/p3kplain-ids.txt 256 4096 -1 OWN_SPEC=3
for t in 3 4 5; do
  s p3k_t$t $S/prompts/p3k-ids.txt $S/runs/e52/p3kplain-ids.txt 256 4096 -1 OWN_SPEC=5 OWN_SPEC_TAU=0.$t OWN_SPEC_LOG=$D/p3k_t$t.conf
done
echo ALLDONE >> $sum
