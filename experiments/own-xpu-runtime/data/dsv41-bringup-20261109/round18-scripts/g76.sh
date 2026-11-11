#!/bin/bash
# tp76 = tp75 + OWN_ATT_OUT_C (default on): the attention output from local memory with a column per lane and the
# skip of an empty slot as an added -0.0f (SparseOutJC / OutMC; bench_sparse_out s3: 22 -> 12 us per layer at 640
# slots, bitwise). Builds tp76 from the src76 snapshot, then with the default env: traces of blocks of 16 / 5 / one
# token + 40 answers; prompt-1 speed q (tp76) / d (tp75) alternated; guessing on the code and analysis prompts (512
# answers SAME as plain, e57); the 19K / 69K / 95K documents (256 answers = e82's; 69K also with tp75, alternated)
# and guessing on the 34K document (SAME as plain). The 95K run goes last (the 19:43 reset came 30 s into one).
# Corrected-only PCIe records are noted, anything else stops it.
set -u
W=/home/steve/dsv41-work
L=/home/steve/b70-optimization-lab
D=$W/runs/g76
mkdir -p $D
sum=$D/summary.txt; marks=$D/marks.txt
export PATH=/opt/intel/oneapi/compiler/latest/bin:$PATH
t0=$(date +%s)
(cd $W/src76 && icpx -fsycl -fsycl-targets=intel_gpu_bmg_g31 -Xsycl-target-backend=intel_gpu_bmg_g31 "-options -ze-intel-enable-auto-large-GRF-mode" -O2 -std=c++20 -fp-model=precise -ffp-contract=off -Wno-deprecated-declarations -I planning/dsv41-fixtures -I src planning/dsv41-fixtures/own_run_v41.cpp -o $W/own_run_v41_tp76 -lze_loader > $W/build-tp76.log 2>&1)
rc=$?
echo "tp76 build exit $rc in $(( $(date +%s) - t0 )) s" >> $sum
[ $rc -eq 0 ] || { echo STOP_BUILD >> $sum; exit 1; }
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
for k in "h16|$T16" "h5|$T5" "h1|$T1"; do
  IFS='|' read -r name envs <<< "$k"; $W/run_exp.sh g76 tp76 "$name|$envs|trace"; sed -i '/^DONE$/d' $sum
done
for k in "q1 tp76" "d1 tp75" "q2 tp76" "d2 tp75"; do
  set -- $k; $W/run_exp.sh g76 $2 "p1$1|$PL|speed"; sed -i '/^DONE$/d' $sum
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
for n in code analysis; do r ${n}_q tp76 $PP/$n-ids.txt 512 4096 1 $D/${n}_q-ids.txt $BEST OWN_VERIFY_REF=$W/runs/e57/${n}_plain-ids.txt OWN_DSPARK=$DS; done
for k in "x19k q" "x69k q" "x69k d"; do
  set -- $k; b=tp76; [ $2 = d ] && b=tp75
  p=$X/$1-ids.txt; r ${1}_$2 $b $p 256 $(ms $p) -1 $D/${1}_$2-ids.txt $PL; same $D/${1}_$2-ids.txt $W/runs/e82/${1}_plain-ids.txt 256 ${1}_$2
done
p=$X/x34k-ids.txt; r x34k_spec tp76 $p 256 $(ms $p) -1 $D/x34k_spec-ids.txt $BEST OWN_VERIFY_REF=$W/runs/e82/x34k_plain-ids.txt OWN_DSPARK=$DS
p=$X/x95k-ids.txt; r x95k_q tp76 $p 256 $(ms $p) -1 $D/x95k_q-ids.txt $PL; same $D/x95k_q-ids.txt $W/runs/e82/x95k_plain-ids.txt 256 x95k_q
grep -c "SAME AS the plain" $sum | sed 's/^/guessing SAME count: /' >> $sum
grep -q "ANSWER.*DIFFERS\|DIFFERS from" $sum && echo "SOME_DIFFER" >> $sum
echo ALLDONE >> $sum
