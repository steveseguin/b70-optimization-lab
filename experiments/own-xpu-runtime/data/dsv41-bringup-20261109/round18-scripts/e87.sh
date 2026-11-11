#!/bin/bash
# tp73 = tp72 with: OWN_ATT_TRIM's block-step fix (WindowAppendM's launch kept at max(d, win + nc) items per token:
# e86 h16t / h5t differed because a trimmed launch left later tokens' lists unwritten; h1t was identical);
# OWN_TOPK_R for the plain / masked selects only (the block select keeps TopKSelP: test_topk_r, R slower there),
# and for the candidate select too (TopKSelC::rwalk, new). Waits for e86 (it stops at its gate). Builds tp73 +
# test_index_cand from the src73 snapshot, then: (0) test_index_cand on a 230 W card (both walks of TopKSelC,
# bitwise; stops on FAIL); (1) gates: traces of blocks of 16 / 5 / one token and plain 128, default and
# A = ATT_TRIM + TOPK_R (all must be identical; stops otherwise); (2) plain 128 after prompt 1: n a a n;
# (3) checks on the 34K document: IDX_CAND=2 + TOPK_R (candidate lists by ranges against the full TopKSelP one),
# TOPK_R + DEV_INDEX_CHECK on the 10K prompt (every list against the host); (4) guessing six prompts x [n, a], two rounds;
# (5) long documents: 69K default, then 19K / 34K / 69K / 95K with A (256 answers = e82's).
# Stops at the first fault line.
set -u
S=/tmp/claude-1000/-home-steve/6f61a0f6-fd06-49a3-b5b4-babc9645cc37/scratchpad
until grep -q "ALLDONE\|STOP" $S/runs/e86/summary.txt 2>/dev/null; do sleep 10; done
while systemctl --user is-active --quiet dsv41-e86; do sleep 2; done
D=$S/runs/e87
mkdir -p $D
sum=$D/summary.txt; marks=$D/marks.txt
cd $S/src73 # snapshot of engine/src + planning/dsv41-fixtures + tools/bench taken when this script was written
export PATH=/opt/intel/oneapi/compiler/latest/bin:$PATH
t0=$(date +%s)
icpx -fsycl -fsycl-targets=intel_gpu_bmg_g31 -Xsycl-target-backend=intel_gpu_bmg_g31 "-options -ze-intel-enable-auto-large-GRF-mode" -O2 -std=c++20 -fp-model=precise -ffp-contract=off -Wno-deprecated-declarations -I planning/dsv41-fixtures -I src planning/dsv41-fixtures/own_run_v41.cpp -o $S/own_run_v41_tp73 -lze_loader > $S/build-tp73.log 2>&1 &
B1=$!
icpx -fsycl -fsycl-targets=intel_gpu_bmg_g31 -Xsycl-target-backend=intel_gpu_bmg_g31 "-options -ze-intel-enable-auto-large-GRF-mode" -O2 -std=c++20 -fp-model=precise -ffp-contract=off -Wno-deprecated-declarations -I src tools/bench/test_index_cand.cpp -o $S/test_index_cand73 > $S/build-test-index-cand73.log 2>&1
r2=$?
wait $B1; r1=$?
echo "tp73 build exit $r1, test_index_cand build exit $r2 in $(( $(date +%s) - t0 )) s" >> $sum
[ $r1 -eq 0 ] && [ $r2 -eq 0 ] || { echo STOP_BUILD >> $sum; exit 1; }
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib ZES_ENABLE_SYSMAN=1
J='fault response|cat error|engine reset|coredump has been created|gt reset|timedout job|exec queue reset|suspend fence|vm worker error|reset started'
mono() { python3 -I -c 'import time; print(f"{time.monotonic():.4f}")'; }
python3 -I $S/tools/gpu_sampler.py $D/telemetry.smp 0.05 &
SP=$!
trap 'kill $SP 2>/dev/null' EXIT
tg=$(date '+%Y-%m-%d %H:%M:%S')
echo "test start $(mono)" >> $marks
ONEAPI_DEVICE_SELECTOR=level_zero:1 $S/test_index_cand73 > $D/test-index-cand.txt 2>&1
rc=$?
echo "test end $(mono)" >> $marks
echo "test_index_cand exit $rc: $(tail -1 $D/test-index-cand.txt)" >> $sum
f=$(journalctl -k --since "$tg" -o cat | grep -iE "$J" | head -3)
[ -n "$f" ] && { echo "$f" | sed 's/^/FAULT: /' >> $sum; echo STOP_FAULT >> $sum; exit 1; }
[ $rc -eq 0 ] || { echo STOP_TEST >> $sum; exit 1; }
G="OWN_MT_EU=6 OWN_MT_TGU=2 OWN_MT_RIDE=1 OWN_MT_RWG=128 OWN_MT_RFUSE=1 OWN_HC_FIN=1"
PL="OWN_TP=6 OWN_PROMPT_BLOCK=16 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G"
T16="OWN_TP=6 OWN_TP_THREADS=1 OWN_PROMPT_BLOCK=16 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G OWN_MT_TGR=16:4,1:4 OWN_MT_TGR_ROWS=0"
T5="OWN_TP=6 OWN_TP_THREADS=1 OWN_PROMPT_BLOCK=5 OWN_MT_TGM=1:1,2:1,3:3,4:2,5:3 $G"
T1="OWN_TP=6 OWN_TP_THREADS=1 OWN_PROMPT_BLOCK=1 $G"
AT="OWN_ATT_TRIM=1 OWN_TOPK_R=1"
tg=$(date '+%Y-%m-%d %H:%M:%S')
$S/run_exp.sh e87 tp73 "h16|$T16|trace" "h5|$T5|trace" "h1|$T1|trace" "h16a|$T16 $AT|trace" "h5a|$T5 $AT|trace" "h1a|$T1 $AT|trace"
sed -i '/^DONE$/d' $sum
journalctl -k --since "$tg" -o cat | grep -iE "$J" | head -3 | sed 's/^/FAULT: /' >> $sum
grep -q "TRACE_DIFFERS\|IDS40_DIFFER\|SPEED128_DIFFER\|exit [^0]\|FAULT" $sum && { echo STOP_GATE >> $sum; exit 1; }
tg=$(date '+%Y-%m-%d %H:%M:%S')
$S/run_exp.sh e87 tp73 "p1n1|$PL|speed" "p1a1|$PL $AT|speed" "p1a2|$PL $AT|speed" "p1n2|$PL|speed"
sed -i '/^DONE$/d' $sum
journalctl -k --since "$tg" -o cat | grep -iE "$J" | head -3 | sed 's/^/FAULT: /' >> $sum
grep -q "TRACE_DIFFERS\|IDS40_DIFFER\|SPEED128_DIFFER\|exit [^0]\|FAULT" $sum && { echo STOP_GATE >> $sum; exit 1; }
bin=$S/own_run_v41_tp73
X=$S/prompts/xl
r() { local name=$1 pr=$2 nt=$3 ms=$4; shift 4; local t0; t0=$(date '+%Y-%m-%d %H:%M:%S')
  echo "$name start $(mono)" >> $marks
  env "$@" OWN_PROMPT=$pr OWN_EOS=-1 $bin - $nt $D/$name-ids.txt $ms > $D/$name.log 2>&1
  local rc=$?
  echo "$name end $(mono)" >> $marks
  echo "$name exit $rc" >> $sum
  grep -h "free after load\|prompt:\|decode:\|host io\|rror\|timed out\|exceeds\|dev_index check\|idx_cand check" $D/$name.log | tail -n 14 | sed "s/^/$name: /" >> $sum
  local f; f=$(journalctl -k --since "$t0" -o cat | grep -iE "$J" | head -3)
  if [ -n "$f" ] || [ $rc -ne 0 ]; then echo "$f" | sed 's/^/FAULT: /' >> $sum; echo STOP_FAULT >> $sum; exit 1; fi; }
same() { cmp -s <(head -$3 $D/$1-ids.txt) <(head -$3 $2) && echo "$1 ANSWER$3_SAME" >> $sum || echo "$1 ANSWER$3_DIFFERS" >> $sum; }
ms() { echo $(( ( $(wc -l < $1) + 256 + 1023 ) / 1024 * 1024 )); }
p=$X/x34k-ids.txt
r x34k_cchk $p 64 $(ms $p) $PL OWN_IDX_CAND=2 OWN_TOPK_R=1; same x34k_cchk $S/runs/e82/x34k_plain-ids.txt 64
grep -q "MISMATCH\|ANSWER64_DIFFERS" $D/x34k_cchk.log $sum && { echo STOP_CHECK_MISMATCH >> $sum; exit 1; }
grep -q "idx_cand check: [0-9]* lists, 0 mismatches" $D/x34k_cchk.log || { echo STOP_CHECK_NOT_RUN >> $sum; exit 1; }
# (the host check sorts every list: O(len^2) for a prompt; e26's 10,621-token check read in 189 s)
p=$S/prompts/p10k-ids.txt
r p10k_rchk $p 32 $(ms $p) $PL OWN_TOPK_R=1 OWN_DEV_INDEX_CHECK=1
grep -q "MISMATCH" $D/p10k_rchk.log && { echo STOP_CHECK_MISMATCH >> $sum; exit 1; }
grep -q "dev_index check: [0-9]* lists, 0 mismatches" $D/p10k_rchk.log || { echo STOP_CHECK_NOT_RUN >> $sum; exit 1; }
PP=/home/steve/b70-optimization-lab/experiments/own-xpu-runtime/data/dsv41-bringup-20261109/spec-prompts
R57=$S/runs/e57
DS=/mnt/fast-ai/llm-models/DeepSeek-V4.1-Flash-1017-GGUF/dspark-DeepSeek-V4.1-Flash-1017-Q8_0.gguf
BEST="$PL OWN_MT_TGM=1:1,2:1,3:3,4:2,5:3,6:3 OWN_SPEC=5 OWN_SPEC_TAU=0.5 OWN_SPEC_KMIN=0 OWN_MT_TGR=2:4,3:4,4:4,5:4,6:4 OWN_MT_TGR_ROWS=4096"
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
for n in code prose analysis ops docs p3k; do s ${n}_n1 $(args $n); s ${n}_a1 $(args $n) $AT; done
for n in code prose analysis ops docs p3k; do s ${n}_a2 $(args $n) $AT; s ${n}_n2 $(args $n); done
p=$X/x69k-ids.txt; r x69k_n $p 256 $(ms $p) $PL; same x69k_n $S/runs/e82/x69k_plain-ids.txt 256
for n in x19k x34k x69k x95k; do
  p=$X/$n-ids.txt; r ${n}_a $p 256 $(ms $p) $PL $AT; same ${n}_a $S/runs/e82/${n}_plain-ids.txt 256
done
echo ALLDONE >> $sum
