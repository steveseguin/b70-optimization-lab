#!/bin/bash
# tp81 = tp79 + OWN_NORM_FF (RMS norms of 1,280+ columns: the scale from a fast bracket of the double chain, the
# same scale bit for bit; bench n1-n4) + OWN_NORM_WG (one-token norm launches in smaller work-groups; n5). SHORT runs
# only. Builds tp81 (build81.sh, src81) first. Traces of blocks of 16 / 5 / one token + 40 answers with the candidate
# (FF on, WG 64), one token with FF on + WG 128 and the old form (FF off, WG 512); prompt 1 128 answers for old /
# FF / FF+WG64 / FF+WG128 alternated twice; profiles old vs FF+WG64 (card 2); the 3K prompt; guessing on the code /
# analysis / 3K prompts (SAME as plain).
set -u
W=/home/steve/dsv41-work
L=/home/steve/b70-optimization-lab
D=$W/runs/g81
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
$W/build81.sh
grep -q "exit 0" $W/build-tp81.log || { echo STOP_BUILD >> $sum; exit 1; }
tail -1 $W/build-tp81.log >> $sum
C64="OWN_NORM_FF=1 OWN_NORM_WG=64"
OLD="OWN_NORM_FF=0 OWN_NORM_WG=512"
for k in "h16|$T16 $C64" "h5|$T5 $C64" "h1|$T1 $C64" "h1w128|$T1 OWN_NORM_FF=1 OWN_NORM_WG=128" "h1old|$T1 $OLD"; do
  IFS='|' read -r name envs <<< "$k"; $W/run_exp.sh g81 tp81 "$name|$envs|trace"; sed -i '/^DONE$/d' $sum
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
  for k in "s_old$rd|$OLD" "s_ff$rd|OWN_NORM_FF=1 OWN_NORM_WG=512" "s_w64_$rd|$C64" "s_w128_$rd|OWN_NORM_FF=1 OWN_NORM_WG=128"; do
    IFS='|' read -r name envs <<< "$k"; $W/run_exp.sh g81 tp81 "$name|$PL $envs|speed"; sed -i '/^DONE$/d' $sum
  done
done
grep -q "SPEED128_DIFFER\|exit [^0]" $sum && { echo STOP_SPEED >> $sum; exit 1; }
for k in "pf_w64|$C64" "pf_old|$OLD"; do
  IFS='|' read -r name envs <<< "$k"; $W/run_exp.sh g81 tp81 "$name|$PL $envs OWN_GPROF=2 OWN_GPROF_DECODE=1 OWN_GPROF_CARD=2|gprof"; sed -i '/^DONE$/d' $sum
done
fcheck "$tg"
for n in code analysis; do
  r ${n}_q tp81 $PP/$n-ids.txt 512 4096 1 $D/${n}_q-ids.txt $BEST $C64 OWN_VERIFY_REF=$W/runs/e57/${n}_plain-ids.txt OWN_DSPARK=$DS
  r ${n}_qold tp81 $PP/$n-ids.txt 512 4096 1 $D/${n}_qold-ids.txt $BEST $OLD OWN_VERIFY_REF=$W/runs/e57/${n}_plain-ids.txt OWN_DSPARK=$DS
done
p=$W/prompts/p3k-ids.txt
for k in "q1|$C64" "d1|$OLD" "q2|$C64" "d2|$OLD"; do
  IFS='|' read -r nm ev <<< "$k"; r p3k_$nm tp81 $p 256 4096 -1 $D/p3k_$nm-ids.txt $PL $ev; same $D/p3k_$nm-ids.txt $W/runs/e52/p3kplain-ids.txt 256 p3k_$nm
done
r p3k_spec tp81 $p 256 4096 -1 $D/p3k_spec-ids.txt $BEST $C64 OWN_VERIFY_REF=$W/runs/e52/p3kplain-ids.txt OWN_DSPARK=$DS
grep -c "SAME AS the plain" $sum | sed 's/^/guessing SAME count: /' >> $sum
grep -q "ANSWER.*DIFFERS\|DIFFERS from" $sum && echo "SOME_DIFFER" >> $sum
echo ALLDONE >> $sum
