#!/bin/bash
# tp74 = tp73 with OWN_TOPK_R and OWN_ATT_TRIM on by default (a runner change only). Builds tp74 from the src74
# snapshot, then: gates with the default env (traces of blocks of 16 / 5 / one token + 40 answers), one-token
# trace with both off (=0); prompt-1 speed d (tp74 default) / a (tp73 + both on) / n (tp73 default) as
# d a n d a n; the 34K document with the default env (256 answers = the reference); guessing on two prompts with
# the default env (SAME AS plain). Stops at the first fault line.
set -u
W=/home/steve/dsv41-work
L=/home/steve/b70-optimization-lab
D=$W/runs/g74
mkdir -p $D
sum=$D/summary.txt; marks=$D/marks.txt
export PATH=/opt/intel/oneapi/compiler/latest/bin:$PATH
t0=$(date +%s)
(cd $W/src74 && icpx -fsycl -fsycl-targets=intel_gpu_bmg_g31 -Xsycl-target-backend=intel_gpu_bmg_g31 "-options -ze-intel-enable-auto-large-GRF-mode" -O2 -std=c++20 -fp-model=precise -ffp-contract=off -Wno-deprecated-declarations -I planning/dsv41-fixtures -I src planning/dsv41-fixtures/own_run_v41.cpp -o $W/own_run_v41_tp74 -lze_loader > $W/build-tp74.log 2>&1)
rc=$?
echo "tp74 build exit $rc in $(( $(date +%s) - t0 )) s" >> $sum
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
AT="OWN_ATT_TRIM=1 OWN_TOPK_R=1"
OFF="OWN_ATT_TRIM=0 OWN_TOPK_R=0"
tg=$(date '+%Y-%m-%d %H:%M:%S')
for k in "h16|$T16" "h5|$T5" "h1|$T1" "h1off|$T1 $OFF"; do
  IFS='|' read -r name envs <<< "$k"; $W/run_exp.sh g74 tp74 "$name|$envs|trace"; sed -i '/^DONE$/d' $sum
done
for k in "d1 tp74|" "a1 tp73|$AT" "n1 tp73|" "d2 tp74|" "a2 tp73|$AT" "n2 tp73|"; do
  IFS='|' read -r nb envs <<< "$k"; set -- $nb
  $W/run_exp.sh g74 $2 "p1$1|$PL $envs|speed"; sed -i '/^DONE$/d' $sum
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
  grep -h "prompt:\|decode:\|spec decode\|host io\|rror\|timed out\|exceeds" $D/$name.log | sed "s/^/$name: /" >> $sum
  fcheck "$t0"
  [ $rc -eq 0 ] || { echo STOP_EXIT >> $sum; exit 1; }; }
same() { cmp -s <(head -$3 $1) <(head -$3 $2) && echo "$4 ANSWER$3_SAME" >> $sum || echo "$4 ANSWER$3_DIFFERS" >> $sum; }
p=$W/prompts/xl/x34k-ids.txt; r x34k_d tp74 $p 256 $(ms $p) -1 $D/x34k_d-ids.txt $PL; same $D/x34k_d-ids.txt $W/runs/e82/x34k_plain-ids.txt 256 x34k_d
PP=$L/experiments/own-xpu-runtime/data/dsv41-bringup-20261109/spec-prompts
DS=/mnt/fast-ai/llm-models/DeepSeek-V4.1-Flash-1017-GGUF/dspark-DeepSeek-V4.1-Flash-1017-Q8_0.gguf
BEST="$PL OWN_MT_TGM=1:1,2:1,3:3,4:2,5:3,6:3 OWN_SPEC=5 OWN_SPEC_TAU=0.5 OWN_SPEC_KMIN=0 OWN_MT_TGR=2:4,3:4,4:4,5:4,6:4 OWN_MT_TGR_ROWS=4096"
for n in code analysis; do r ${n}_d tp74 $PP/$n-ids.txt 512 4096 1 $D/${n}_d-ids.txt $BEST OWN_VERIFY_REF=$W/runs/e57/${n}_plain-ids.txt OWN_DSPARK=$DS; done
grep -c "SAME AS the plain" $sum | sed 's/^/guessing SAME count: /' >> $sum
echo ALLDONE >> $sum
