#!/bin/bash
# tp67 = tp66 + OWN_TP_HEADS_MIN=m: the split attention layout (OWN_TP_HEADS) only for blocks of >= m tokens
# (prompt reading); one-token steps, guess checks and the draft keep whole groups. Every card holds both layouts'
# q_b / output-a rows. No CPU builds during this campaign; stops at the first fault line.
# (0) gates: traces (blocks of 16 / 5 / one token) with A + MIN=16, block 16 without heads; plain 128 with it;
# (1) plain 128: default vs dual, twice; (2) six prompts x [n default, d dual], two rounds (order swapped);
# (3) 3K read, blocks of 16, 16 answer tokens: b, dA, dB, r4 (row blocks of 4 from 4,096 rows), dA + r4; twice.
set -u
S=/tmp/claude-1000/-home-steve/6f61a0f6-fd06-49a3-b5b4-babc9645cc37/scratchpad
D=$S/runs/e81
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
DA="OWN_TP_HEADS=3,3,3,3,2,2 OWN_TP_HEADS_MIN=16"; DB="OWN_TP_HEADS=2,3,3,3,3,2 OWN_TP_HEADS_MIN=16"
tg=$(date '+%Y-%m-%d %H:%M:%S')
T16="OWN_TP=6 OWN_TP_THREADS=1 OWN_PROMPT_BLOCK=16 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G OWN_MT_TGR=16:4,1:4 OWN_MT_TGR_ROWS=0"
T5="OWN_TP=6 OWN_TP_THREADS=1 OWN_PROMPT_BLOCK=5 OWN_MT_TGM=1:1,2:1,3:3,4:2,5:3 $G"
T1="OWN_TP=6 OWN_TP_THREADS=1 OWN_PROMPT_BLOCK=1 $G"
$S/run_exp.sh e81 tp67 "h16d|$T16 $DA|trace" "h5d|$T5 $DA|trace" "h1d|$T1 $DA|trace" "h16n|$T16|trace" "p1d0|$PL $DA|speed"
$S/run_exp.sh e81 tp67 "p1n1|$PL|speed" "p1d1|$PL $DA|speed" "p1d2|$PL $DA|speed" "p1n2|$PL|speed"
sed -i '/^DONE$/d' $sum
journalctl -k --since "$tg" -o cat | grep -iE "$J" | head -3 | sed 's/^/FAULT: /' >> $sum
grep -q "TRACE_DIFFERS\|IDS40_DIFFER\|SPEED128_DIFFER\|exit [^0]\|FAULT" $sum && { echo STOP_GATE >> $sum; exit 1; }
PP=/home/steve/b70-optimization-lab/experiments/own-xpu-runtime/data/dsv41-bringup-20261109/spec-prompts
R57=$S/runs/e57
DS=/mnt/fast-ai/llm-models/DeepSeek-V4.1-Flash-1017-GGUF/dspark-DeepSeek-V4.1-Flash-1017-Q8_0.gguf
BEST="$PL OWN_MT_TGM=1:1,2:1,3:3,4:2,5:3,6:3 OWN_SPEC=5 OWN_SPEC_TAU=0.5 OWN_SPEC_KMIN=0 OWN_MT_TGR=2:4,3:4,4:4,5:4,6:4 OWN_MT_TGR_ROWS=4096"
bin=$S/own_run_v41_tp67
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
for n in code prose analysis ops docs p3k; do s ${n}_n1 $(args $n); s ${n}_d1 $(args $n) $DA; done
for n in code prose analysis ops docs p3k; do s ${n}_d2 $(args $n) $DA; s ${n}_n2 $(args $n); done
head -16 $R3 > $D/ref16.txt
declare -A B
B[b]=""
B[dA]="$DA"
B[dB]="$DB"
B[r4]="OWN_MT_TGR=16:4 OWN_MT_TGR_ROWS=4096"
B[dr]="$DA OWN_MT_TGR=16:4 OWN_MT_TGR_ROWS=4096"
pr() { local a=$1 k=$2; t0=$(date '+%Y-%m-%d %H:%M:%S')
  env $PL ${B[$a]} OWN_PROMPT=$P3 OWN_EOS=-1 $bin - 16 $D/pr_$a$k-ids.txt 4096 > $D/pr_$a$k.log 2>&1
  local rc=$?
  echo "pr_$a$k exit $rc" >> $sum; grep -h "prompt:" $D/pr_$a$k.log | sed "s/^/pr_$a$k: /" >> $sum
  cmp -s <(head -16 $D/pr_$a$k-ids.txt) $D/ref16.txt && echo "pr_$a$k ANSWER16_SAME" >> $sum || echo "pr_$a$k ANSWER16_DIFFER" >> $sum
  local f; f=$(journalctl -k --since "$t0" -o cat | grep -iE "$J" | head -3)
  if [ -n "$f" ] || [ $rc -ne 0 ]; then echo "$f" | sed 's/^/FAULT: /' >> $sum; echo STOP_FAULT >> $sum; exit 1; fi; }
for a in b dA dB r4 dr; do pr $a 1; done
for a in dr r4 dB dA b; do pr $a 2; done
echo ALLDONE >> $sum
