#!/bin/bash
# Long prompts (tp68 = tp67 + the split attention layout as the default for blocks of >= 16 tokens + OWN_IDX_R,
# the indexer score with R rows per item). (0) gates of the new defaults: traces of blocks of 16 / 5 / one token,
# plain 128-token answers. (1) documents of 18,692 / 33,815 / 68,506 tokens (repo docs, chat-templated request,
# prompts/xl): read in blocks of 16 + 256 plain answer tokens (the reference), the same with OWN_IDX_R=$IR (answer
# must be identical), then guessing (answers must be the same as the plain run); 95,497 tokens: plain and IDX_R.
# (2) the 19K document read one token at a time, 16 answer tokens = the block reading's first 16. (3) a kernel
# profile of card 2 on the 69K document. No CPU builds during this campaign; stops at the first fault line.
set -u
S=/tmp/claude-1000/-home-steve/6f61a0f6-fd06-49a3-b5b4-babc9645cc37/scratchpad
D=$S/runs/e82
mkdir -p $D
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib ZES_ENABLE_SYSMAN=1
sum=$D/summary.txt; marks=$D/marks.txt
J='fault response|cat error|engine reset|coredump has been created|gt reset|timedout job|exec queue reset|suspend fence|vm worker error|reset started'
mono() { python3 -I -c 'import time; print(f"{time.monotonic():.4f}")'; }
python3 -I $S/tools/gpu_sampler.py $D/telemetry.smp 0.05 &
SP=$!
trap 'kill $SP 2>/dev/null' EXIT
G="OWN_MT_EU=6 OWN_MT_TGU=2 OWN_MT_RIDE=1 OWN_MT_RWG=128 OWN_MT_RFUSE=1 OWN_HC_FIN=1"
PL="OWN_TP=6 OWN_PROMPT_BLOCK=16 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G"
IR="${IR:-4}"
tg=$(date '+%Y-%m-%d %H:%M:%S')
T16="OWN_TP=6 OWN_TP_THREADS=1 OWN_PROMPT_BLOCK=16 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G OWN_MT_TGR=16:4,1:4 OWN_MT_TGR_ROWS=0"
T5="OWN_TP=6 OWN_TP_THREADS=1 OWN_PROMPT_BLOCK=5 OWN_MT_TGM=1:1,2:1,3:3,4:2,5:3 $G"
T1="OWN_TP=6 OWN_TP_THREADS=1 OWN_PROMPT_BLOCK=1 $G"
$S/run_exp.sh e82 tp68 "h16|$T16|trace" "h5|$T5|trace" "h1|$T1|trace" "h16i|$T16 OWN_IDX_R=$IR|trace" "p1|$PL|speed"
sed -i '/^DONE$/d' $sum
journalctl -k --since "$tg" -o cat | grep -iE "$J" | head -3 | sed 's/^/FAULT: /' >> $sum
grep -q "TRACE_DIFFERS\|IDS40_DIFFER\|SPEED128_DIFFER\|exit [^0]\|FAULT" $sum && { echo STOP_GATE >> $sum; exit 1; }
DS=/mnt/fast-ai/llm-models/DeepSeek-V4.1-Flash-1017-GGUF/dspark-DeepSeek-V4.1-Flash-1017-Q8_0.gguf
BEST="$PL OWN_MT_TGM=1:1,2:1,3:3,4:2,5:3,6:3 OWN_SPEC=5 OWN_SPEC_TAU=0.5 OWN_SPEC_KMIN=0 OWN_MT_TGR=2:4,3:4,4:4,5:4,6:4 OWN_MT_TGR_ROWS=4096"
bin=$S/own_run_v41_tp68
X=$S/prompts/xl
echo "IR=$IR" >> $sum
r() { local name=$1 pr=$2 nt=$3 ms=$4; shift 4; local t0; t0=$(date '+%Y-%m-%d %H:%M:%S')
  echo "$name start $(mono)" >> $marks
  env "$@" OWN_PROMPT=$pr OWN_EOS=-1 $bin - $nt $D/$name-ids.txt $ms > $D/$name.log 2>&1
  local rc=$?
  echo "$name end $(mono)" >> $marks
  echo "$name exit $rc" >> $sum
  grep -h "free after load\|prompt:\|decode:\|spec decode\|host io\|rror\|timed out\|exceeds" $D/$name.log | sed "s/^/$name: /" >> $sum
  local f; f=$(journalctl -k --since "$t0" -o cat | grep -iE "$J" | head -3)
  if [ -n "$f" ] || [ $rc -ne 0 ]; then echo "$f" | sed 's/^/FAULT: /' >> $sum; echo STOP_FAULT >> $sum; exit 1; fi; }
same() { cmp -s <(head -$3 $D/$1-ids.txt) <(head -$3 $D/$2-ids.txt) && echo "$1 ANSWER$3_SAME_AS_$2" >> $sum || echo "$1 ANSWER$3_DIFFERS_FROM_$2" >> $sum; }
ms() { echo $(( ( $(wc -l < $1) + 256 + 1023 ) / 1024 * 1024 )); }
for n in x19k x34k x69k; do
  p=$X/$n-ids.txt; m=$(ms $p)
  r ${n}_plain $p 256 $m $PL
  r ${n}_idx $p 256 $m $PL OWN_IDX_R=$IR; same ${n}_idx ${n}_plain 256
  r ${n}_spec $p 256 $m $BEST OWN_VERIFY_REF=$D/${n}_plain-ids.txt OWN_DSPARK=$DS
done
p=$X/x95k-ids.txt; m=$(ms $p)
r x95k_plain $p 256 $m $PL
r x95k_idx $p 256 $m $PL OWN_IDX_R=$IR; same x95k_idx x95k_plain 256
p=$X/x19k-ids.txt; r x19k_one $p 16 $(ms $p) OWN_TP=6 OWN_PROMPT_BLOCK=1 $G; same x19k_one x19k_plain 16
# kernel-time profile of card 2 (not a speed measurement): the 69K read and 32 plain answer tokens
p=$X/x69k-ids.txt; r x69k_prof2 $p 32 $(ms $p) $PL OWN_GPROF=2 OWN_GPROF_CARD=2; same x69k_prof2 x69k_plain 32
echo ALLDONE >> $sum
