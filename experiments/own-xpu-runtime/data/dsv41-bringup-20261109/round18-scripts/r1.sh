#!/bin/bash
# After the 15:16 host reset (firmware: fatal PCIe completion timeout on the network chip 0000:a7:00.0, which
# shares root complex 0000:a0 with card a3; no GPU fault line) the scratchpad was gone: references, prompts,
# binaries and e87's results. This campaign rebuilds them in a folder that survives a reset (/home/steve/dsv41-work)
# and repeats e87 + e88:
#  (A) builds: tp68h = the pushed commit 1562843b8 (git archive), tp73 = the working tree (the same source as the
#      lost tp73), test_index_cand, bench_norm_dp;
#  (B) the card health probe (scripts/check-qwen36-xpu-xccl-health.sh, run separately in a clean unit);
#  (C) references with tp68h (every build since ab1 gave these byte for byte): the 3-step trace + 40 answer
#      tokens after prompt 1 (one-token form, then the default env: must be identical), 128 tokens (speed
#      reference), the five guessing prompts' 512-token plain answers, the 3K document's 256, the four long
#      documents' 256 (first token must be 2581 as in e82);
#  (D) = e87 with tp73: test_index_cand; gates default and A = ATT_TRIM + TOPK_R; prompt-1 speed o / n / a
#      alternated (o = tp68h: is the default slower than this morning?); candidate check (IDX_CAND=2 + TOPK_R,
#      34K) and host check (TOPK_R + DEV_INDEX_CHECK, 10K); guessing six prompts x [n, a], two rounds; long
#      documents 69K default, then 19K / 34K / 69K / 95K with A;
#  (E) = e88: bench_norm_dp; profiles (card 2, answer steps only) with A after prompt 1 / 19K / 69K.
# Stops at the first fault line (GPU or PCIe / machine-check lines).
set -u
W=/home/steve/dsv41-work
L=/home/steve/b70-optimization-lab
D=$W/runs/r1
mkdir -p $D $W/runs/ab1 $W/runs/e57 $W/runs/e52 $W/runs/e82
sum=$D/summary.txt; marks=$D/marks.txt
export PATH=/opt/intel/oneapi/compiler/latest/bin:$PATH
CX='-fsycl -fsycl-targets=intel_gpu_bmg_g31 -Xsycl-target-backend=intel_gpu_bmg_g31 -options -ze-intel-enable-auto-large-GRF-mode -O2 -std=c++20 -fp-model=precise -ffp-contract=off -Wno-deprecated-declarations'
bld() { local src=$1 out=$2 main=$3; shift 3; (cd $W/$src && icpx -fsycl -fsycl-targets=intel_gpu_bmg_g31 -Xsycl-target-backend=intel_gpu_bmg_g31 "-options -ze-intel-enable-auto-large-GRF-mode" -O2 -std=c++20 -fp-model=precise -ffp-contract=off -Wno-deprecated-declarations "$@" $main -o $W/$out > $W/build-$out.log 2>&1); }
t0=$(date +%s)
if [ -x $W/own_run_v41_tp68h ] && [ -x $W/own_run_v41_tp73 ] && [ -x $W/test_index_cand ] && [ -x $W/bench_norm_dp ]; then
  r1=0; r2=0; r3=0; r4=0; echo "builds: reused (built 17:13-17:21 from the same snapshots)" >> $sum
else
bld src68h own_run_v41_tp68h planning/dsv41-fixtures/own_run_v41.cpp -I planning/dsv41-fixtures -I src -lze_loader & B1=$!
bld src73 own_run_v41_tp73 planning/dsv41-fixtures/own_run_v41.cpp -I planning/dsv41-fixtures -I src -lze_loader; r2=$?
wait $B1; r1=$?
bld src73 test_index_cand tools/bench/test_index_cand.cpp -I src & B3=$!
bld src73 bench_norm_dp tools/bench/bench_norm_dp.cpp -I src; r4=$?
wait $B3; r3=$?
echo "builds: tp68h $r1, tp73 $r2, test_index_cand $r3, bench_norm_dp $r4 in $(( $(date +%s) - t0 )) s" >> $sum
fi
[ $r1 -eq 0 ] && [ $r2 -eq 0 ] && [ $r3 -eq 0 ] || { echo STOP_BUILD >> $sum; exit 1; }
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib ZES_ENABLE_SYSMAN=1
J='fault response|cat error|engine reset|coredump has been created|gt reset|timedout job|exec queue reset|suspend fence|vm worker error|reset started|PCIe Bus Error|AER:|Hardware Error|Machine check'
mono() { python3 -I -c 'import time; print(f"{time.monotonic():.4f}")'; }
fcheck() { local f; f=$(journalctl -k --since "$1" -o cat | grep -iE "$J" | head -3); [ -n "$f" ] && { echo "$f" | sed 's/^/FAULT: /' >> $sum; echo STOP_FAULT >> $sum; exit 1; }; return 0; }
python3 -I $W/tools/gpu_sampler.py $D/telemetry.smp 0.05 &
SP=$!
trap 'kill $SP 2>/dev/null' EXIT
# (B) health probe: run on its own in a clean unit (runs/probe/health-probe.txt, 17:24, six cards barrier +
# all-reduce ok); inside this script it failed at once because of the engine's LD_LIBRARY_PATH (oneAPI runtime
# loaded into the probe's PyTorch)
grep -q "^rc 0" $W/runs/probe/health-probe.txt && echo "health probe (separate unit, clean env): rc 0" >> $sum || { echo STOP_PROBE >> $sum; exit 1; }
G="OWN_MT_EU=6 OWN_MT_TGU=2 OWN_MT_RIDE=1 OWN_MT_RWG=128 OWN_MT_RFUSE=1 OWN_HC_FIN=1"
PL="OWN_TP=6 OWN_PROMPT_BLOCK=16 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G"
T16="OWN_TP=6 OWN_TP_THREADS=1 OWN_PROMPT_BLOCK=16 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G OWN_MT_TGR=16:4,1:4 OWN_MT_TGR_ROWS=0"
T5="OWN_TP=6 OWN_TP_THREADS=1 OWN_PROMPT_BLOCK=5 OWN_MT_TGM=1:1,2:1,3:3,4:2,5:3 $G"
T1="OWN_TP=6 OWN_TP_THREADS=1 OWN_PROMPT_BLOCK=1 $G"
P1=$L/experiments/own-xpu-runtime/data/dsv41-bringup-20261109/prompt1-ids.txt
PP=$L/experiments/own-xpu-runtime/data/dsv41-bringup-20261109/spec-prompts
X=$W/prompts/xl
ms() { echo $(( ( $(wc -l < $1) + 256 + 1023 ) / 1024 * 1024 )); }
# r NAME BIN PROMPT NTOK MAXSEQ EOS OUTIDS [ENV...]
r() { local name=$1 b=$2 pr=$3 nt=$4 mx=$5 eos=$6 out=$7; shift 7; local t0; t0=$(date '+%Y-%m-%d %H:%M:%S')
  echo "$name start $(mono)" >> $marks
  env "$@" OWN_PROMPT=$pr OWN_EOS=$eos $W/own_run_v41_$b - $nt $out $mx > $D/$name.log 2>&1
  local rc=$?
  echo "$name end $(mono)" >> $marks
  echo "$name exit $rc" >> $sum
  grep -h "prompt:\|decode:\|spec decode\|host io\|rror\|timed out\|exceeds\|  total \|kernels .* ms, launches" $D/$name.log | sed "s/^/$name: /" >> $sum
  grep -h "dev_index check\|idx_cand check" $D/$name.log | tail -n 3 | sed "s/^/$name: /" >> $sum
  fcheck "$t0"
  [ $rc -eq 0 ] || { echo STOP_EXIT >> $sum; exit 1; }; }
same() { cmp -s <(head -$3 $1) <(head -$3 $2) && echo "$4 ANSWER$3_SAME" >> $sum || echo "$4 ANSWER$3_DIFFERS" >> $sum; }
# (C) references with tp68h
B=$W/runs/ab1
r ref_t1 tp68h $P1 40 4096 1 $B/base-ids.txt $T1 OWN_TRACE=$B/base.trc OWN_TRACE_STEPS=3
r ref_def tp68h $P1 40 4096 1 $D/ref_def-ids.txt OWN_TRACE=$D/ref_def.trc OWN_TRACE_STEPS=3
cmp -s $B/base.trc $D/ref_def.trc && echo "ref_def TRACE_IDENTICAL (to ref_t1)" >> $sum || { echo "ref_def TRACE_DIFFERS" >> $sum; echo STOP_REF >> $sum; exit 1; }
same $B/base-ids.txt $D/ref_def-ids.txt 40 ref_def
for f in f32-six-card-greedy-ids-40.txt six-card-greedy-ids-100.txt cards-only-p1-greedy-ids.txt cpu-reference-greedy-ids.txt; do
  same $B/base-ids.txt $L/experiments/own-xpu-runtime/data/dsv41-bringup-20261109/$f $(wc -l < $B/base-ids.txt) "ref_t1-vs-$f"
done
r ref_speed tp68h $P1 128 4096 -1 $B/base-speed-ids.txt $PL
for n in code prose analysis ops docs; do r ref_${n} tp68h $PP/$n-ids.txt 512 4096 1 $W/runs/e57/${n}_plain-ids.txt $PL; done
p=$W/prompts/p3k-ids.txt; r ref_p3k tp68h $p 256 4096 -1 $W/runs/e52/p3kplain-ids.txt $PL
for n in x19k x34k x69k x95k; do p=$X/$n-ids.txt; r ref_$n tp68h $p 256 $(ms $p) -1 $W/runs/e82/${n}_plain-ids.txt $PL; done
grep "^ref_x.*: prompt:" $sum | grep -v "first token 2581" && { echo STOP_REF_FIRST_TOKEN >> $sum; exit 1; }
echo "REFS_DONE" >> $sum
# (D) e87 with tp73
tg=$(date '+%Y-%m-%d %H:%M:%S')
echo "test start $(mono)" >> $marks
ONEAPI_DEVICE_SELECTOR=level_zero:1 $W/test_index_cand > $D/test-index-cand.txt 2>&1; rc=$?
echo "test end $(mono)" >> $marks
echo "test_index_cand exit $rc: $(tail -1 $D/test-index-cand.txt)" >> $sum
fcheck "$tg"
[ $rc -eq 0 ] || { echo STOP_TEST >> $sum; exit 1; }
AT="OWN_ATT_TRIM=1 OWN_TOPK_R=1"
tg=$(date '+%Y-%m-%d %H:%M:%S')
for k in "h16|$T16" "h5|$T5" "h1|$T1" "h16a|$T16 $AT" "h5a|$T5 $AT" "h1a|$T1 $AT"; do
  IFS='|' read -r name envs <<< "$k"
  $W/run_exp.sh r1 tp73 "$name|$envs|trace"; sed -i '/^DONE$/d' $sum
done
for k in "o1 tp68h|" "n1 tp73|" "a1 tp73|$AT" "a2 tp73|$AT" "n2 tp73|" "o2 tp68h|"; do
  IFS='|' read -r nb envs <<< "$k"; set -- $nb
  $W/run_exp.sh r1 $2 "p1$1|$PL $envs|speed"; sed -i '/^DONE$/d' $sum
done
fcheck "$tg"
grep -q "TRACE_DIFFERS\|IDS40_DIFFER\|SPEED128_DIFFER\|exit [^0]" $sum && { echo STOP_GATE >> $sum; exit 1; }
p=$X/x34k-ids.txt
r x34k_cchk tp73 $p 64 $(ms $p) -1 $D/x34k_cchk-ids.txt $PL OWN_IDX_CAND=2 OWN_TOPK_R=1; same $D/x34k_cchk-ids.txt $W/runs/e82/x34k_plain-ids.txt 64 x34k_cchk
grep -q "MISMATCH" $D/x34k_cchk.log && { echo STOP_CHECK_MISMATCH >> $sum; exit 1; }
grep -q "idx_cand check: [0-9]* lists, 0 mismatches" $D/x34k_cchk.log || { echo STOP_CHECK_NOT_RUN >> $sum; exit 1; }
p=$W/prompts/p10k-ids.txt
r p10k_rchk tp73 $p 32 $(ms $p) -1 $D/p10k_rchk-ids.txt $PL OWN_TOPK_R=1 OWN_DEV_INDEX_CHECK=1
grep -q "MISMATCH" $D/p10k_rchk.log && { echo STOP_CHECK_MISMATCH >> $sum; exit 1; }
grep -q "dev_index check: [0-9]* lists, 0 mismatches" $D/p10k_rchk.log || { echo STOP_CHECK_NOT_RUN >> $sum; exit 1; }
DS=/mnt/fast-ai/llm-models/DeepSeek-V4.1-Flash-1017-GGUF/dspark-DeepSeek-V4.1-Flash-1017-Q8_0.gguf
BEST="$PL OWN_MT_TGM=1:1,2:1,3:3,4:2,5:3,6:3 OWN_SPEC=5 OWN_SPEC_TAU=0.5 OWN_SPEC_KMIN=0 OWN_MT_TGR=2:4,3:4,4:4,5:4,6:4 OWN_MT_TGR_ROWS=4096"
s() { local name=$1 n=$2; shift 2
  if [ $n = p3k ]; then r $name tp73 $W/prompts/p3k-ids.txt 256 4096 -1 $D/$name-ids.txt $BEST "$@" OWN_VERIFY_REF=$W/runs/e52/p3kplain-ids.txt OWN_DSPARK=$DS
  else r $name tp73 $PP/$n-ids.txt 512 4096 1 $D/$name-ids.txt $BEST "$@" OWN_VERIFY_REF=$W/runs/e57/${n}_plain-ids.txt OWN_DSPARK=$DS; fi; }
for n in code prose analysis ops docs p3k; do s ${n}_n1 $n; s ${n}_a1 $n $AT; done
for n in code prose analysis ops docs p3k; do s ${n}_a2 $n $AT; s ${n}_n2 $n; done
p=$X/x69k-ids.txt; r x69k_n tp73 $p 256 $(ms $p) -1 $D/x69k_n-ids.txt $PL; same $D/x69k_n-ids.txt $W/runs/e82/x69k_plain-ids.txt 256 x69k_n
for n in x19k x34k x69k x95k; do
  p=$X/$n-ids.txt; r ${n}_a tp73 $p 256 $(ms $p) -1 $D/${n}_a-ids.txt $PL $AT; same $D/${n}_a-ids.txt $W/runs/e82/${n}_plain-ids.txt 256 ${n}_a
done
echo "E87_DONE" >> $sum
# (E) e88
if [ $r4 -eq 0 ]; then
  tg=$(date '+%Y-%m-%d %H:%M:%S')
  echo "bench start $(mono)" >> $marks
  ONEAPI_DEVICE_SELECTOR=level_zero:1 $W/bench_norm_dp > $D/bench-norm-dp.txt 2>&1
  echo "bench_norm_dp exit $?: $(tail -1 $D/bench-norm-dp.txt)" >> $sum
  echo "bench end $(mono)" >> $marks
  fcheck "$tg"
fi
PR="OWN_GPROF=2 OWN_GPROF_DECODE=1 OWN_GPROF_CARD=2"
r p1_prof2 tp73 $P1 64 4096 -1 $D/p1_prof2-ids.txt $PL $AT $PR; same $D/p1_prof2-ids.txt $B/base-speed-ids.txt 64 p1_prof2
p=$X/x19k-ids.txt; r x19k_prof2 tp73 $p 64 $(ms $p) -1 $D/x19k_prof2-ids.txt $PL $AT $PR; same $D/x19k_prof2-ids.txt $W/runs/e82/x19k_plain-ids.txt 64 x19k_prof2
p=$X/x69k-ids.txt; r x69k_prof2 tp73 $p 64 $(ms $p) -1 $D/x69k_prof2-ids.txt $PL $AT $PR; same $D/x69k_prof2-ids.txt $W/runs/e82/x69k_plain-ids.txt 64 x69k_prof2
echo ALLDONE >> $sum
