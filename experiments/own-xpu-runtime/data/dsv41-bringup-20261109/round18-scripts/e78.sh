#!/bin/bash
# tp65 (large register file where a kernel would spill): one screening round of the block settings that were tuned
# while those kernels spilled. Waits for e77 (exits if e77 stopped). No build; stops at the first fault line.
# (1) six prompts, settings interleaved per prompt: n = current, r2 = 2-row blocks for checks, rr = row blocks from
#     2,048 rows, g4 = one token group for blocks of 4, g6 = groups of 2 for blocks of 6;
# (2) 3K read, blocks of 16: b, r2 (16:2), r4 (16:4), m9 (all 16 tokens in one sub-group), 16 answer tokens checked.
set -u
S=/tmp/claude-1000/-home-steve/6f61a0f6-fd06-49a3-b5b4-babc9645cc37/scratchpad
until grep -q "ALLDONE\|STOP" $S/runs/e77/summary.txt 2>/dev/null; do sleep 10; done
grep -q STOP $S/runs/e77/summary.txt && exit 1
while systemctl --user is-active --quiet dsv41-e77; do sleep 2; done
D=$S/runs/e78
mkdir -p $D
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib ZES_ENABLE_SYSMAN=1
sum=$D/summary.txt; marks=$D/marks.txt
J='fault response|cat error|engine reset|coredump has been created|gt reset|timedout job|exec queue reset|suspend fence|vm worker error|reset started'
mono() { python3 -I -c 'import time; print(f"{time.monotonic():.4f}")'; }
python3 -I $S/tools/gpu_sampler.py $D/telemetry.smp 0.01 &
SP=$!
trap 'kill $SP 2>/dev/null' EXIT
G="OWN_MT_EU=6 OWN_MT_TGU=2 OWN_MT_RIDE=1 OWN_MT_RWG=128 OWN_MT_RFUSE=1 OWN_HC_FIN=1"
PL="OWN_TP=6 OWN_PROMPT_BLOCK=16 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G"
PP=/home/steve/b70-optimization-lab/experiments/own-xpu-runtime/data/dsv41-bringup-20261109/spec-prompts
R57=$S/runs/e57
DS=/mnt/fast-ai/llm-models/DeepSeek-V4.1-Flash-1017-GGUF/dspark-DeepSeek-V4.1-Flash-1017-Q8_0.gguf
BEST="$PL OWN_MT_TGM=1:1,2:1,3:3,4:2,5:3,6:3 OWN_SPEC=5 OWN_SPEC_TAU=0.5 OWN_SPEC_KMIN=0 OWN_MT_TGR=2:4,3:4,4:4,5:4,6:4 OWN_MT_TGR_ROWS=4096"
bin=$S/own_run_v41_tp65
s() { local name=$1 pr=$2 ref=$3 nt=$4 ms=$5 eos=$6; shift 6; t0=$(date '+%Y-%m-%d %H:%M:%S')
  echo "$name start $(mono)" >> $marks
  env $BEST "$@" OWN_PROMPT=$pr OWN_EOS=$eos OWN_VERIFY_REF=$ref OWN_DSPARK=$DS $bin - $nt $D/$name-ids.txt $ms > $D/$name.log 2>&1
  local rc=$?
  echo "$name end $(mono)" >> $marks
  echo "$name exit $rc" >> $sum; grep -h "prompt:\|spec decode\|host io\|rror\|timed out" $D/$name.log | sed "s/^/$name: /" >> $sum
  local f; f=$(journalctl -k --since "$t0" -o cat | grep -iE "$J" | head -3)
  if [ -n "$f" ] || [ $rc -ne 0 ]; then echo "$f" | sed 's/^/FAULT: /' >> $sum; echo STOP_FAULT >> $sum; exit 1; fi; }
P3=$S/prompts/p3k-ids.txt; R3=$S/runs/e52/p3kplain-ids.txt
args() { if [ $1 = p3k ]; then echo "$P3 $R3 256 4096 -1"; else echo "$PP/$1-ids.txt $R57/${1}_plain-ids.txt 512 4096 1"; fi; }
declare -A A
A[n]=""
A[r2]="OWN_MT_TGR=2:2,3:2,4:2,5:2,6:2"
A[rr]="OWN_MT_TGR_ROWS=2048"
A[g4]="OWN_MT_TGM=1:1,2:1,3:3,4:4,5:3,6:3"
A[g6]="OWN_MT_TGM=1:1,2:1,3:3,4:2,5:3,6:2"
ORD=(n r2 rr g4 g6)
i=0
for n in code prose analysis ops docs p3k; do
  for j in 0 1 2 3 4; do a=${ORD[$(( (i + j) % 5 ))]}; s ${n}_$a $(args $n) ${A[$a]}; done
  i=$((i + 1))
done
head -16 $R3 > $D/ref16.txt
declare -A B
B[b]=""
B[r2]="OWN_MT_TGR=16:2 OWN_MT_TGR_ROWS=4096"
B[r4]="OWN_MT_TGR=16:4 OWN_MT_TGR_ROWS=4096"
B[m9]="OWN_MT_TGM=16:9"
for a in b r2 r4 m9; do
  t0=$(date '+%Y-%m-%d %H:%M:%S')
  env $PL ${B[$a]} OWN_PROMPT=$P3 OWN_EOS=-1 $bin - 16 $D/pr_$a-ids.txt 4096 > $D/pr_$a.log 2>&1
  echo "pr_$a exit $?" >> $sum; grep -h "prompt:" $D/pr_$a.log | sed "s/^/pr_$a: /" >> $sum
  cmp -s <(head -16 $D/pr_$a-ids.txt) $D/ref16.txt && echo "pr_$a ANSWER16_SAME" >> $sum || echo "pr_$a ANSWER16_DIFFER" >> $sum
  f=$(journalctl -k --since "$t0" -o cat | grep -iE "$J" | head -3)
  if [ -n "$f" ]; then echo "$f" | sed 's/^/FAULT: /' >> $sum; echo STOP_FAULT >> $sum; exit 1; fi
done
echo ALLDONE >> $sum
