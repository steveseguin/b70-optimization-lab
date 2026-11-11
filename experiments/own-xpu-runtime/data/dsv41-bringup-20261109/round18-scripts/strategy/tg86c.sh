#!/bin/bash
# tg86c (resume of tg86 after its speed section): gate for tp86 = tp84 + the timeline patch + OWN_ATT_HG / OWN_ATT_PK (the one-token attention's score over
# more sub-groups and the trimmed lists' softmax built per slot count, bench_attn_dec ad4: same bits) + OWN_XPF (the
# pull exchanges' spare work-groups prefetch the next weight rows into the cache). All opt-in. SHORT runs only.
# 1. traces + 40 answers: defaults (blocks 16 / 5 / 1), then each option on one-token blocks, then all on blocks of 16
# 2. prompt 1, 128 answers: defaults / att / xpf 1 / 2 / 3 / att + xpf 3, alternated twice
# 3. the 3K document, 256 answers: defaults / att + xpf 3 alternated twice (against runs/e52)
# 4. guessing on the code / analysis prompts and the 3K prompt with att + xpf 3: SAME AS the plain run
set -u
W=/home/steve/dsv41-work
L=/home/steve/b70-optimization-lab
D=$W/runs/tg86
mkdir -p $D
sum=$D/summary.txt; marks=$D/marks.txt
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib ZES_ENABLE_SYSMAN=1
J='fault response|cat error|engine reset|coredump has been created|gt reset|timedout job|exec queue reset|suspend fence|vm worker error|reset started|PCIe Bus Error|AER:|Hardware Error|Machine check'
mono() { python3 -I -c 'import time; print(f"{time.monotonic():.4f}")'; }
# a window with only corrected PCIe records (the firmware's "{N}[Hardware Error]" lines, severity corrected: card
# 0000:23's link has logged corrected receiver errors since the 19:43 reset) is noted and the run goes on (as g83)
fcheck() { local w f; w=$(journalctl -k --since "$1" -o cat); f=$(echo "$w" | grep -iE "$J"); [ -z "$f" ] && return 0
  if ! echo "$f" | grep -qvE '^\{[0-9]+\}\[Hardware Error\]' && ! echo "$w" | grep -qE 'event severity: (fatal|recoverable)'; then
    echo "WARN corrected PCIe: $(echo "$w" | grep -E 'device_id: 0000' | sort | uniq -c | tr -s ' ' | tr '\n' ';')" >> $sum; return 0; fi
  echo "$f" | head -3 | sed 's/^/FAULT: /' >> $sum; echo STOP_FAULT >> $sum; exit 1; }
grep -q "build exit 0" $W/build-tp86.log || { echo STOP_BUILD >> $sum; exit 1; }
tail -1 $W/build-tp86.log >> $sum
python3 -I $W/tools/gpu_sampler.py $D/telemetry.smp 0.05 &
SP=$!
trap 'kill $SP 2>/dev/null' EXIT
G="OWN_MT_EU=6 OWN_MT_TGU=2 OWN_MT_RIDE=1 OWN_MT_RWG=128 OWN_MT_RFUSE=1 OWN_HC_FIN=1"
PL="OWN_TP=6 OWN_PROMPT_BLOCK=16 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G"
T16="OWN_TP=6 OWN_TP_THREADS=1 OWN_PROMPT_BLOCK=16 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G OWN_MT_TGR=16:4,1:4 OWN_MT_TGR_ROWS=0"
T5="OWN_TP=6 OWN_TP_THREADS=1 OWN_PROMPT_BLOCK=5 OWN_MT_TGM=1:1,2:1,3:3,4:2,5:3 $G"
T1="OWN_TP=6 OWN_TP_THREADS=1 OWN_PROMPT_BLOCK=1 $G"
ATT="OWN_ATT_HG=1 OWN_ATT_PK=1"
tg=$(date '+%Y-%m-%d %H:%M:%S')
# ---- 1. traces: done in the first run (10 of 10 identical; p16all was a script error: trace mode parks the card
# threads, which the PL settings' multi-token prompt needs)
# ---- 2. prompt 1 speed: done in tg86b (all SPEED128_SAME; att 88.88 / 87.33 vs default 85.95 / 86.83, XPF 1-3
# slower: closed). 3 and 4 below with the attention change alone.
echo "tg86c: resumed after the speed runs" >> $sum
ATT="OWN_ATT_HG=1 OWN_ATT_PK=1"
r() { local name=$1 b=$2 pr=$3 nt=$4 mx=$5 eos=$6 out=$7; shift 7; local t0; t0=$(date '+%Y-%m-%d %H:%M:%S')
  echo "$name start $(mono)" >> $marks
  env "$@" OWN_PROMPT=$pr OWN_EOS=$eos $W/own_run_v41_$b - $nt $out $mx > $D/$name.log 2>&1
  local rc=$?
  echo "$name end $(mono)" >> $marks
  echo "$name exit $rc" >> $sum
  grep -h "prompt:\|decode:\|spec decode\|host io\|rror\|timed out\|exceeds\|MISMATCH" $D/$name.log | sed "s/^/$name: /" >> $sum
  grep -h "check:" $D/$name.log | tail -2 | sed "s/^/$name: /" >> $sum
  fcheck "$t0"
  [ $rc -eq 0 ] || { echo STOP_EXIT >> $sum; exit 1; }; }
same() { cmp -s <(head -$3 $1) <(head -$3 $2) && echo "$4 ANSWER$3_SAME" >> $sum || echo "$4 ANSWER$3_DIFFERS" >> $sum; }
# ---- 3. the 3K document (long lists: 640-slot attention on most layers)
p=$W/prompts/p3k-ids.txt
for k in "d1|" "n1|$ATT" "d2|" "n2|$ATT"; do
  IFS='|' read -r nm envs <<< "$k"; r p3k_$nm tp86 $p 256 4096 -1 $D/p3k_$nm-ids.txt $PL $envs
  same $D/p3k_$nm-ids.txt $W/runs/e52/p3kplain-ids.txt 256 p3k_$nm
done
# ---- 4. guessing
DS=/mnt/fast-ai/llm-models/DeepSeek-V4.1-Flash-1017-GGUF/dspark-DeepSeek-V4.1-Flash-1017-Q8_0.gguf
BEST="$PL OWN_MT_TGM=1:1,2:1,3:3,4:2,5:3,6:3 OWN_SPEC=5 OWN_SPEC_TAU=0.5 OWN_SPEC_KMIN=0 OWN_MT_TGR=2:4,3:4,4:4,5:4,6:4 OWN_MT_TGR_ROWS=4096"
PP=$L/experiments/own-xpu-runtime/data/dsv41-bringup-20261109/spec-prompts
for n in code analysis; do
  r ${n}_q tp86 $PP/$n-ids.txt 512 4096 1 $D/${n}_q-ids.txt $BEST $ATT OWN_VERIFY_REF=$W/runs/e57/${n}_plain-ids.txt OWN_DSPARK=$DS
done
r p3k_spec tp86 $p 256 4096 -1 $D/p3k_spec-ids.txt $BEST $ATT OWN_VERIFY_REF=$W/runs/e52/p3kplain-ids.txt OWN_DSPARK=$DS
sed -n "/tg86c: resumed/,\$p" $sum | grep -c "SAME AS the plain" | sed 's/^/guessing SAME count (of 3): /' >> $sum
sed -n "/tg86c: resumed/,\$p" $sum | grep -q "ANSWER.*DIFFERS\|DIFFERS from" && echo "SOME_DIFFER" >> $sum
echo ALLDONE >> $sum
