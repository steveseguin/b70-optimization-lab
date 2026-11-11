#!/bin/bash
# tp75 = tp74 + OWN_TOPK_Q (default on): the index's selects with every key loaded once into registers
# (TopKSelQ / TopKSelBQ / TopKSelCQ and their block forms; rows >= 4,096, blocks > 2,048; test_topk_q PASS in q4).
# Builds tp75 from the src75 snapshot, then with the default env: traces of blocks of 16 / 5 / one token
# (unchanged: a 36-token prompt never uses the new selects) + 40 answers; prompt-1 speed q (tp75) / d (tp74)
# alternated; the 10,621-token prompt with the host's lists compared (OWN_DEV_INDEX_CHECK=1: the one-token
# selects at 10.6K rows); the 34K document with OWN_IDX_CAND=2 (candidate lists vs the full masked select,
# one-token and blocks); the 19K / 69K / 95K documents (256 answers = the references; 69K also with tp74,
# alternated); guessing on the 34K document (256 answers SAME as plain). Stops at the first fault line.
set -u
W=/home/steve/dsv41-work
L=/home/steve/b70-optimization-lab
D=$W/runs/g75
mkdir -p $D
sum=$D/summary.txt; marks=$D/marks.txt
export PATH=/opt/intel/oneapi/compiler/latest/bin:$PATH
t0=$(date +%s)
(cd $W/src75 && icpx -fsycl -fsycl-targets=intel_gpu_bmg_g31 -Xsycl-target-backend=intel_gpu_bmg_g31 "-options -ze-intel-enable-auto-large-GRF-mode" -O2 -std=c++20 -fp-model=precise -ffp-contract=off -Wno-deprecated-declarations -I planning/dsv41-fixtures -I src planning/dsv41-fixtures/own_run_v41.cpp -o $W/own_run_v41_tp75 -lze_loader > $W/build-tp75.log 2>&1)
rc=$?
echo "tp75 build exit $rc in $(( $(date +%s) - t0 )) s" >> $sum
[ $rc -eq 0 ] || { echo STOP_BUILD >> $sum; exit 1; }
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib ZES_ENABLE_SYSMAN=1
J='fault response|cat error|engine reset|coredump has been created|gt reset|timedout job|exec queue reset|suspend fence|vm worker error|reset started|PCIe Bus Error|AER:|Hardware Error|Machine check'
mono() { python3 -I -c 'import time; print(f"{time.monotonic():.4f}")'; }
fcheck() { local f; f=$(journalctl -k --since "$1" -o cat | grep -iE "$J" | head -3); [ -n "$f" ] && { echo "$f" | sed 's/^/FAULT: /' >> $sum; echo STOP_FAULT >> $sum; exit 1; }; return 0; }
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
  IFS='|' read -r name envs <<< "$k"; $W/run_exp.sh g75 tp75 "$name|$envs|trace"; sed -i '/^DONE$/d' $sum
done
for k in "q1 tp75" "d1 tp74" "q2 tp75" "d2 tp74"; do
  set -- $k; $W/run_exp.sh g75 $2 "p1$1|$PL|speed"; sed -i '/^DONE$/d' $sum
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
p=$W/prompts/p10k-ids.txt; r p10k_qchk tp75 $p 32 $(ms $p) -1 $D/p10k_qchk-ids.txt $PL OWN_DEV_INDEX_CHECK=1
grep -q "dev_index check: .* [1-9][0-9]* mismatches\|MISMATCH" $D/p10k_qchk.log && { echo STOP_INDEX_CHECK >> $sum; exit 1; }
p=$X/x34k-ids.txt; r x34k_cchk tp75 $p 64 $(ms $p) -1 $D/x34k_cchk-ids.txt $PL OWN_IDX_CAND=2; same $D/x34k_cchk-ids.txt $W/runs/e82/x34k_plain-ids.txt 64 x34k_cchk
grep -q "idx_cand check: .* [1-9][0-9]* mismatches\|MISMATCH" $D/x34k_cchk.log && { echo STOP_CAND_CHECK >> $sum; exit 1; }
for k in "x19k q" "x69k q" "x69k d" "x95k q"; do
  set -- $k; b=tp75; [ $2 = d ] && b=tp74
  p=$X/$1-ids.txt; r ${1}_$2 $b $p 256 $(ms $p) -1 $D/${1}_$2-ids.txt $PL; same $D/${1}_$2-ids.txt $W/runs/e82/${1}_plain-ids.txt 256 ${1}_$2
done
DS=/mnt/fast-ai/llm-models/DeepSeek-V4.1-Flash-1017-GGUF/dspark-DeepSeek-V4.1-Flash-1017-Q8_0.gguf
BEST="$PL OWN_MT_TGM=1:1,2:1,3:3,4:2,5:3,6:3 OWN_SPEC=5 OWN_SPEC_TAU=0.5 OWN_SPEC_KMIN=0 OWN_MT_TGR=2:4,3:4,4:4,5:4,6:4 OWN_MT_TGR_ROWS=4096"
p=$X/x34k-ids.txt; r x34k_spec tp75 $p 256 $(ms $p) -1 $D/x34k_spec-ids.txt $BEST OWN_VERIFY_REF=$W/runs/e82/x34k_plain-ids.txt OWN_DSPARK=$DS
grep -c "SAME AS the plain" $sum | sed 's/^/guessing SAME count: /' >> $sum
grep -q "ANSWER.*DIFFERS\|DIFFERS from" $sum && echo "SOME_DIFFER" >> $sum
echo ALLDONE >> $sum
