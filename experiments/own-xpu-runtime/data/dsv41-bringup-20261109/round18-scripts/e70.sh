#!/bin/bash
# tp60 = tp59 + (a) the draft's MXFP4 experts packed and grouped by expert (OWN_DR_MXP=1 default; bench_draft_mxfp4
# bitwise PASS; same guesses -> the same "kept" counts), (b) OWN_TP_PIN (card threads on CPUs 0-5 = six physical
# cores, main thread on CPU 6; e69: the six threads float and sometimes share a core, CPU n and n + 8).
# No CPU builds run during this campaign.
# (1) tp60 trace gates + plain 128 tokens; (2) six prompts x [pin + MXP, pin + MXP=0, no pin + MXP] x 2 (interleaved);
# (3) plain 128-token runs with the host-time profile (OWN_TP_HOSTPROF), pinned and not.
set -u
S=/tmp/claude-1000/-home-steve/6f61a0f6-fd06-49a3-b5b4-babc9645cc37/scratchpad
D=$S/runs/e70
mkdir -p $D
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib ZES_ENABLE_SYSMAN=1
sum=$D/summary.txt; marks=$D/marks.txt
J='fault response|cat error|engine reset|coredump has been created|gt reset'
mono() { python3 -I -c 'import time; print(f"{time.monotonic():.4f}")'; }
python3 -I $S/tools/gpu_sampler.py $D/telemetry.smp 0.01 &
SP=$!
trap 'kill $SP 2>/dev/null' EXIT
PIN="OWN_TP_PIN=0,1,2,3,4,5,6"
G="OWN_MT_EU=6 OWN_MT_TGU=2 OWN_MT_RIDE=1 OWN_MT_RWG=128 OWN_MT_RFUSE=1 OWN_HC_FIN=1"
PL="OWN_TP=6 OWN_PROMPT_BLOCK=16 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G"
$S/run_exp.sh e70 tp60 "h16|OWN_TP=6 OWN_TP_THREADS=1 OWN_PROMPT_BLOCK=16 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G OWN_MT_TGR=16:4,1:4 OWN_MT_TGR_ROWS=0 $PIN|trace" \
  "h5|OWN_TP=6 OWN_TP_THREADS=1 OWN_PROMPT_BLOCK=5 OWN_MT_TGM=1:1,2:1,3:3,4:2,5:3 $G $PIN|trace" \
  "h1|OWN_TP=6 OWN_TP_THREADS=1 OWN_PROMPT_BLOCK=1 $G|trace" \
  "p1|$PL $PIN|speed" \
  "p1n|$PL|speed"
sed -i '/^DONE$/d' $sum
grep -q "TRACE_DIFFERS\|IDS40_DIFFER\|SPEED128_DIFFER\|exit [^0]" $sum && { echo STOP_GATE >> $sum; exit 1; }
PP=/home/steve/b70-optimization-lab/experiments/own-xpu-runtime/data/dsv41-bringup-20261109/spec-prompts
R57=$S/runs/e57
DS=/mnt/fast-ai/llm-models/DeepSeek-V4.1-Flash-1017-GGUF/dspark-DeepSeek-V4.1-Flash-1017-Q8_0.gguf
BEST="$PL OWN_MT_TGM=1:1,2:1,3:3,4:2,5:3,6:3 OWN_SPEC=5 OWN_SPEC_TAU=0.5 OWN_SPEC_KMIN=0 OWN_MT_TGR=2:4,3:4,4:4,5:4,6:4 OWN_MT_TGR_ROWS=4096"
s() { local name=$1 bin=$S/own_run_v41_$2 pr=$3 ref=$4 nt=$5 ms=$6 eos=$7; shift 7; t0=$(date '+%Y-%m-%d %H:%M:%S')
  echo "$name start $(mono)" >> $marks
  env $BEST "$@" OWN_PROMPT=$pr OWN_EOS=$eos OWN_VERIFY_REF=$ref OWN_DSPARK=$DS $bin - $nt $D/$name-ids.txt $ms > $D/$name.log 2>&1 &
  local pid=$!
  # where the threads sit while it decodes (the busy ones are the six card threads and the main thread)
  ( for k in 1 2 3; do sleep 9; ps -L -o tid=,psr=,pcpu= -p $pid 2>/dev/null | awk -v k=$k '$3 > 15 {printf "%s:%s ", $2, $3} END {print ""}' | sed "s/^/$name t$k: /"; done ) >> $D/threads.txt &
  local tp=$!
  wait $pid
  local rc=$?
  kill $tp 2>/dev/null; wait $tp 2>/dev/null
  echo "$name end $(mono)" >> $marks
  echo "$name exit $rc" >> $sum; grep -h "spec decode\|rror\|timed out\|host time" $D/$name.log | sed "s/^/$name: /" >> $sum
  journalctl -k --since "$t0" -o cat | grep -iE "$J" | head -3 >> $sum; }
P3=$S/prompts/p3k-ids.txt; R3=$S/runs/e52/p3kplain-ids.txt
for i in 1 2; do
  for n in code prose analysis ops docs p3k; do
    if [ $n = p3k ]; then a="$P3 $R3 256 4096 -1"; else a="$PP/$n-ids.txt $R57/${n}_plain-ids.txt 512 4096 1"; fi
    s ${n}_pm$i tp60 $a $PIN
    s ${n}_p0$i tp60 $a $PIN OWN_DR_MXP=0
    s ${n}_nm$i tp60 $a
  done
done
# host time per card thread on plain one-token steps (OWN_TP_HOSTPROF prints every 32 steps)
P1=/home/steve/b70-optimization-lab/experiments/own-xpu-runtime/data/dsv41-bringup-20261109/prompt1-ids.txt
for hp in pin nopin; do
  t0=$(date '+%Y-%m-%d %H:%M:%S')
  if [ $hp = pin ]; then pe=$PIN; else pe=; fi
  env $PL $pe OWN_TP_HOSTPROF=1 OWN_PROMPT=$P1 OWN_EOS=-1 $S/own_run_v41_tp60 - 128 $D/hp_$hp-ids.txt 4096 > $D/hp_$hp.log 2>&1
  echo "hp_$hp exit $?" >> $sum; grep -h "decode:\|host per step" $D/hp_$hp.log | tail -3 | sed "s/^/hp_$hp: /" >> $sum
  journalctl -k --since "$t0" -o cat | grep -iE "$J" | head -3 >> $sum
done
echo ALLDONE >> $sum
