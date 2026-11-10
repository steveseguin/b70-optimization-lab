#!/bin/bash
# The head's token groups without row blocks ONLY for blocks of 5 tokens (the draft's head every round, and checks
# of 4 guesses): OWN_MT_TGW_ROWS=16384 OWN_MT_TGWM=1:0,2:0,3:0,4:0,5:3,6:0 (bench: 650 -> 305 us at 5 tokens).
# e67/e68: the form on every block size made the four 230 W cards run ~2,600 MHz (net -2 %); is one launch per round
# enough to do that? Six prompts x [tp60 best, + head-5 groups] x 2, interleaved, with the clock / power sampler.
# Usage: e71.sh "<extra env of the e70 winner>"
set -u
S=/tmp/claude-1000/-home-steve/6f61a0f6-fd06-49a3-b5b4-babc9645cc37/scratchpad
D=$S/runs/e71
mkdir -p $D
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib ZES_ENABLE_SYSMAN=1
sum=$D/summary.txt; marks=$D/marks.txt
J='fault response|cat error|engine reset|coredump has been created|gt reset'
mono() { python3 -I -c 'import time; print(f"{time.monotonic():.4f}")'; }
python3 -I $S/tools/gpu_sampler.py $D/telemetry.smp 0.01 &
SP=$!
trap 'kill $SP 2>/dev/null' EXIT
W="${1:-}"
G="OWN_MT_EU=6 OWN_MT_TGU=2 OWN_MT_RIDE=1 OWN_MT_RWG=128 OWN_MT_RFUSE=1 OWN_HC_FIN=1"
PL="OWN_TP=6 OWN_PROMPT_BLOCK=16 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G"
PP=/home/steve/b70-optimization-lab/experiments/own-xpu-runtime/data/dsv41-bringup-20261109/spec-prompts
R57=$S/runs/e57
DS=/mnt/fast-ai/llm-models/DeepSeek-V4.1-Flash-1017-GGUF/dspark-DeepSeek-V4.1-Flash-1017-Q8_0.gguf
BEST="$PL OWN_MT_TGM=1:1,2:1,3:3,4:2,5:3,6:3 OWN_SPEC=5 OWN_SPEC_TAU=0.5 OWN_SPEC_KMIN=0 OWN_MT_TGR=2:4,3:4,4:4,5:4,6:4 OWN_MT_TGR_ROWS=4096 $W"
H5="OWN_MT_TGW_ROWS=16384 OWN_MT_TGWM=1:0,2:0,3:0,4:0,5:3,6:0"
s() { local name=$1 bin=$S/own_run_v41_$2 pr=$3 ref=$4 nt=$5 ms=$6 eos=$7; shift 7; t0=$(date '+%Y-%m-%d %H:%M:%S')
  echo "$name start $(mono)" >> $marks
  env $BEST "$@" OWN_PROMPT=$pr OWN_EOS=$eos OWN_VERIFY_REF=$ref OWN_DSPARK=$DS $bin - $nt $D/$name-ids.txt $ms > $D/$name.log 2>&1 &
  local pid=$!
  # thread placement every second (CPU of each thread with recent CPU time; the decode is the last ~6 s)
  ( k=0; while kill -0 $pid 2>/dev/null; do sleep 1; k=$((k+1)); ps -L -o tid=,psr=,time= -p $pid 2>/dev/null | tr '\n' ' ' | sed "s/^/$name s$k: /"; echo; done ) >> $D/threads.txt &
  local tp=$!
  wait $pid
  local rc=$?
  wait $tp 2>/dev/null
  echo "$name end $(mono)" >> $marks
  echo "$name exit $rc" >> $sum; grep -h "spec decode\|rror\|timed out" $D/$name.log | sed "s/^/$name: /" >> $sum
  journalctl -k --since "$t0" -o cat | grep -iE "$J" | head -3 >> $sum; }
P3=$S/prompts/p3k-ids.txt; R3=$S/runs/e52/p3kplain-ids.txt
for i in 1 2; do
  for n in code prose analysis ops docs p3k; do
    if [ $n = p3k ]; then a="$P3 $R3 256 4096 -1"; else a="$PP/$n-ids.txt $R57/${n}_plain-ids.txt 512 4096 1"; fi
    s ${n}_b$i tp60 $a
    s ${n}_h$i tp60 $a $H5
  done
done
echo ALLDONE >> $sum
