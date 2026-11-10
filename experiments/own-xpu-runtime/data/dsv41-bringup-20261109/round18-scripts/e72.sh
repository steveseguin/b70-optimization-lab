#!/bin/bash
# tp61 = tp60 + (a) OWN_ENG_DEV=1: the 24 hashed engram rows per engram layer and token go to each card as raw
# Q5_K bytes (a pinned host copy) and the card decodes them (EngRowsA = EmbedRowA's decode), instead of six card
# threads each decoding the same rows on the host before their card can start; (b) a "host io" line per run: MiB
# read from disk, major page faults, host time in the engram row upload per step. Question for the "slow mode":
# are slow runs the ones whose engram rows were not in the page cache (a build or a new prompt)?
# No CPU builds run during this campaign.
# (1) gates with OWN_ENG_DEV=1 (three traces, plain 128 tokens) + plain 128 without;
# (2) six prompts x [tp61 default, ENG_DEV=1] x 2, interleaved, clock / power sampler;
# (3) four fresh prompts (never run): guessing run twice (cold rows, then warm), then the plain reference.
set -u
S=/tmp/claude-1000/-home-steve/6f61a0f6-fd06-49a3-b5b4-babc9645cc37/scratchpad
D=$S/runs/e72
mkdir -p $D
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib ZES_ENABLE_SYSMAN=1
sum=$D/summary.txt; marks=$D/marks.txt
J='fault response|cat error|engine reset|coredump has been created|gt reset'
mono() { python3 -I -c 'import time; print(f"{time.monotonic():.4f}")'; }
python3 -I $S/tools/gpu_sampler.py $D/telemetry.smp 0.01 &
SP=$!
trap 'kill $SP 2>/dev/null' EXIT
ED="OWN_ENG_DEV=1"
G="OWN_MT_EU=6 OWN_MT_TGU=2 OWN_MT_RIDE=1 OWN_MT_RWG=128 OWN_MT_RFUSE=1 OWN_HC_FIN=1"
PL="OWN_TP=6 OWN_PROMPT_BLOCK=16 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G"
$S/run_exp.sh e72 tp61 "h16|OWN_TP=6 OWN_TP_THREADS=1 OWN_PROMPT_BLOCK=16 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G OWN_MT_TGR=16:4,1:4 OWN_MT_TGR_ROWS=0 $ED|trace" \
  "h5|OWN_TP=6 OWN_TP_THREADS=1 OWN_PROMPT_BLOCK=5 OWN_MT_TGM=1:1,2:1,3:3,4:2,5:3 $G $ED|trace" \
  "h1|OWN_TP=6 OWN_TP_THREADS=1 OWN_PROMPT_BLOCK=1 $G $ED|trace" \
  "p1e|$PL $ED|speed" \
  "p1b|$PL|speed"
sed -i '/^DONE$/d' $sum
for n in h16 h5 h1 p1e p1b; do grep -h "host io" $D/$n.log | sed "s/^/$n: /" >> $sum; done
grep -q "TRACE_DIFFERS\|IDS40_DIFFER\|SPEED128_DIFFER\|exit [^0]" $sum && { echo STOP_GATE >> $sum; exit 1; }
PP=/home/steve/b70-optimization-lab/experiments/own-xpu-runtime/data/dsv41-bringup-20261109/spec-prompts
R57=$S/runs/e57
DS=/mnt/fast-ai/llm-models/DeepSeek-V4.1-Flash-1017-GGUF/dspark-DeepSeek-V4.1-Flash-1017-Q8_0.gguf
BEST="$PL OWN_MT_TGM=1:1,2:1,3:3,4:2,5:3,6:3 OWN_SPEC=5 OWN_SPEC_TAU=0.5 OWN_SPEC_KMIN=0 OWN_MT_TGR=2:4,3:4,4:4,5:4,6:4 OWN_MT_TGR_ROWS=4096"
s() { local name=$1 bin=$S/own_run_v41_$2 pr=$3 ref=$4 nt=$5 ms=$6 eos=$7; shift 7; t0=$(date '+%Y-%m-%d %H:%M:%S')
  echo "$name start $(mono)" >> $marks
  env $BEST "$@" OWN_PROMPT=$pr OWN_EOS=$eos OWN_VERIFY_REF=$ref OWN_DSPARK=$DS $bin - $nt $D/$name-ids.txt $ms > $D/$name.log 2>&1
  local rc=$?
  echo "$name end $(mono)" >> $marks
  echo "$name exit $rc" >> $sum; grep -h "spec decode\|host io\|rror\|timed out" $D/$name.log | sed "s/^/$name: /" >> $sum
  journalctl -k --since "$t0" -o cat | grep -iE "$J" | head -3 >> $sum; }
P3=$S/prompts/p3k-ids.txt; R3=$S/runs/e52/p3kplain-ids.txt
for i in 1 2; do
  for n in code prose analysis ops docs p3k; do
    if [ $n = p3k ]; then a="$P3 $R3 256 4096 -1"; else a="$PP/$n-ids.txt $R57/${n}_plain-ids.txt 512 4096 1"; fi
    s ${n}_b$i tp61 $a
    s ${n}_e$i tp61 $a $ED
  done
done
# fresh prompts: the guessing run twice (the first reads its engram rows from disk), then the plain reference
FP=$S/prompts/fresh
for n in f1 f2 f3 f4; do
  s ${n}_cold tp61 $FP/$n-ids.txt /dev/null 512 4096 1
  s ${n}_warm tp61 $FP/$n-ids.txt /dev/null 512 4096 1
  t0=$(date '+%Y-%m-%d %H:%M:%S')
  env $PL OWN_MT_TGM=1:1,2:1,3:3,4:2,5:3,6:3 OWN_PROMPT=$FP/$n-ids.txt OWN_EOS=1 $S/own_run_v41_tp61 - 512 $D/${n}_plain-ids.txt 4096 > $D/${n}_plain.log 2>&1
  echo "${n}_plain exit $? ($(wc -l < $D/${n}_plain-ids.txt) ids)" >> $sum
  grep -h "decode:\|host io\|rror\|timed out" $D/${n}_plain.log | sed "s/^/${n}_plain: /" >> $sum
  journalctl -k --since "$t0" -o cat | grep -iE "$J" | head -3 >> $sum
  for r in cold warm; do cmp -s $D/${n}_$r-ids.txt $D/${n}_plain-ids.txt && echo "${n}_$r SAME_AS_PLAIN" >> $sum || echo "${n}_$r DIFFERS_FROM_PLAIN" >> $sum; done
done
echo ALLDONE >> $sum
