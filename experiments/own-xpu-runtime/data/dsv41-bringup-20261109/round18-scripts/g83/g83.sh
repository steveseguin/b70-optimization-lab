#!/bin/bash
# tp83 = tp82 + the router pick's branch-free tests with a fixed candidate count (rp1-rp3, rt6) + OWN_ENG_FF (the
# engram gate's sums from a bracket over 16 sub-groups per stream; eg1-eg2), all exact, default on. SHORT runs only.
# tp83 is built beforehand (build83.sh, src83). Traces of blocks of 16 / 5 / one token + 40 answers with the
# defaults, one token with OWN_ENG_FF=0 and with OWN_ROUTE_Q=0; prompt 1 128 answers tp83 / tp83 OWN_ENG_FF=0 / tp82
# alternated twice; profile tp83 (card 2); guessing on the code / analysis prompts; the 3K prompt tp83 / tp82
# alternated; guessing on the 3K prompt.
set -u
W=/home/steve/dsv41-work
L=/home/steve/b70-optimization-lab
D=$W/runs/g83
mkdir -p $D
sum=$D/summary.txt; marks=$D/marks.txt
export PATH=/opt/intel/oneapi/compiler/latest/bin:$PATH
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib ZES_ENABLE_SYSMAN=1
J='fault response|cat error|engine reset|coredump has been created|gt reset|timedout job|exec queue reset|suspend fence|vm worker error|reset started|PCIe Bus Error|AER:|Hardware Error|Machine check'
mono() { python3 -I -c 'import time; print(f"{time.monotonic():.4f}")'; }
# a window with only corrected PCIe records (the firmware's "{N}[Hardware Error]" lines, severity corrected: card
# 0000:23's link has logged corrected receiver errors since the 19:43 reset) is noted and the run goes on
fcheck() { local w f; w=$(journalctl -k --since "$1" -o cat); f=$(echo "$w" | grep -iE "$J"); [ -z "$f" ] && return 0
  if ! echo "$f" | grep -qvE '^\{[0-9]+\}\[Hardware Error\]' && ! echo "$w" | grep -qE 'event severity: (fatal|recoverable)'; then
    echo "WARN corrected PCIe: $(echo "$w" | grep -E 'device_id: 0000' | sort | uniq -c | tr -s ' ' | tr '\n' ';')" >> $sum; return 0; fi
  echo "$f" | head -3 | sed 's/^/FAULT: /' >> $sum; echo STOP_FAULT >> $sum; exit 1; }
python3 -I $W/tools/gpu_sampler.py $D/telemetry.smp 0.05 &
SP=$!
trap 'kill $SP 2>/dev/null' EXIT
G="OWN_MT_EU=6 OWN_MT_TGU=2 OWN_MT_RIDE=1 OWN_MT_RWG=128 OWN_MT_RFUSE=1 OWN_HC_FIN=1"
PL="OWN_TP=6 OWN_PROMPT_BLOCK=16 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G"
T16="OWN_TP=6 OWN_TP_THREADS=1 OWN_PROMPT_BLOCK=16 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G OWN_MT_TGR=16:4,1:4 OWN_MT_TGR_ROWS=0"
T5="OWN_TP=6 OWN_TP_THREADS=1 OWN_PROMPT_BLOCK=5 OWN_MT_TGM=1:1,2:1,3:3,4:2,5:3 $G"
T1="OWN_TP=6 OWN_TP_THREADS=1 OWN_PROMPT_BLOCK=1 $G"
tg=$(date '+%Y-%m-%d %H:%M:%S')
grep -q "exit 0" $W/build-tp83.log || { echo STOP_BUILD >> $sum; exit 1; }
tail -1 $W/build-tp83.log >> $sum
for k in "h16|$T16" "h5|$T5" "h1|$T1" "h1ef0|$T1 OWN_ENG_FF=0" "h1rq0|$T1 OWN_ROUTE_Q=0"; do
  IFS='|' read -r name envs <<< "$k"; $W/run_exp.sh g83 tp83 "$name|$envs|trace"; sed -i '/^DONE$/d' $sum
done
fcheck "$tg"
grep -q "TRACE_DIFFERS\|IDS40_DIFFER\|SPEED128_DIFFER\|exit [^0]" $sum && { echo STOP_GATE >> $sum; exit 1; }
ms() { echo $(( ( $(wc -l < $1) + 256 + 1023 ) / 1024 * 1024 )); }
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
X=$W/prompts/xl
DS=/mnt/fast-ai/llm-models/DeepSeek-V4.1-Flash-1017-GGUF/dspark-DeepSeek-V4.1-Flash-1017-Q8_0.gguf
BEST="$PL OWN_MT_TGM=1:1,2:1,3:3,4:2,5:3,6:3 OWN_SPEC=5 OWN_SPEC_TAU=0.5 OWN_SPEC_KMIN=0 OWN_MT_TGR=2:4,3:4,4:4,5:4,6:4 OWN_MT_TGR_ROWS=4096"
PP=$L/experiments/own-xpu-runtime/data/dsv41-bringup-20261109/spec-prompts
for rd in 1 2; do
  for k in "s_new$rd|tp83|" "s_ef0_$rd|tp83|OWN_ENG_FF=0" "s_old$rd|tp82|"; do
    IFS='|' read -r name bin envs <<< "$k"; $W/run_exp.sh g83 $bin "$name|$PL $envs|speed"; sed -i '/^DONE$/d' $sum
  done
done
grep -q "SPEED128_DIFFER\|exit [^0]" $sum && { echo STOP_SPEED >> $sum; exit 1; }
for k in "pf_new|"; do
  IFS='|' read -r name envs <<< "$k"; $W/run_exp.sh g83 tp83 "$name|$PL $envs OWN_GPROF=2 OWN_GPROF_DECODE=1 OWN_GPROF_CARD=2|gprof"; sed -i '/^DONE$/d' $sum
done
fcheck "$tg"
for n in code analysis; do
  r ${n}_q tp83 $PP/$n-ids.txt 512 4096 1 $D/${n}_q-ids.txt $BEST OWN_VERIFY_REF=$W/runs/e57/${n}_plain-ids.txt OWN_DSPARK=$DS
done
p=$W/prompts/p3k-ids.txt
for k in "q1|tp83" "d1|tp82" "q2|tp83" "d2|tp82"; do
  IFS='|' read -r nm bn <<< "$k"; r p3k_$nm $bn $p 256 4096 -1 $D/p3k_$nm-ids.txt $PL; same $D/p3k_$nm-ids.txt $W/runs/e52/p3kplain-ids.txt 256 p3k_$nm
done
r p3k_spec tp83 $p 256 4096 -1 $D/p3k_spec-ids.txt $BEST OWN_VERIFY_REF=$W/runs/e52/p3kplain-ids.txt OWN_DSPARK=$DS
grep -c "SAME AS the plain" $sum | sed 's/^/guessing SAME count: /' >> $sum
grep -q "ANSWER.*DIFFERS\|DIFFERS from" $sum && echo "SOME_DIFFER" >> $sum
echo ALLDONE >> $sum
