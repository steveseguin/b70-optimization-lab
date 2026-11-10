#!/bin/bash
# tp65 = tp64 + (a) OWN_ENG_AHEAD=n (default 16): while the cards read one prompt block, the host asks the disk for
# the engram rows of the next n prompt tokens (page-cache hints only); (b) built with the GPU compiler's automatic
# large register file (kernels that would spill get 256 registers per thread instead of 128; same instructions).
# No CPU builds during this campaign; stops at the first fault line.
# (0) gates: tp65 (three traces, plain 128 x 2); (1) plain 128 x [tp64, tp65] x 2; (2) six prompts x [tp64, tp65],
#     two rounds, order swapped (prompt reading timed in every run); (3) four new long documents L5-L8 on tp65,
#     each read cold then warm: odd OWN_ENG_AHEAD=0, even default.
set -u
S=/tmp/claude-1000/-home-steve/6f61a0f6-fd06-49a3-b5b4-babc9645cc37/scratchpad
D=$S/runs/e77
mkdir -p $D
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib ZES_ENABLE_SYSMAN=1
sum=$D/summary.txt; marks=$D/marks.txt
J='fault response|cat error|engine reset|coredump has been created|gt reset|timedout job|exec queue reset|suspend fence|vm worker error|reset started'
mono() { python3 -I -c 'import time; print(f"{time.monotonic():.4f}")'; }
vm() { awk '/^(pgpgin|pgmajfault|pgscan_kswapd|pgsteal_kswapd|compact_stall|pgmigrate_success|workingset_refault_file|nr_free_pages|nr_file_pages) /{printf "%s=%s ", $1, $2}' /proc/vmstat; awk '/^(MemAvailable|MemFree|Cached):/{printf "%s=%s ", $1, $2}' /proc/meminfo; echo; }
python3 -I $S/tools/gpu_sampler.py $D/telemetry.smp 0.01 &
SP=$!
trap 'kill $SP 2>/dev/null' EXIT
G="OWN_MT_EU=6 OWN_MT_TGU=2 OWN_MT_RIDE=1 OWN_MT_RWG=128 OWN_MT_RFUSE=1 OWN_HC_FIN=1"
PL="OWN_TP=6 OWN_PROMPT_BLOCK=16 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G"
tg=$(date '+%Y-%m-%d %H:%M:%S')
T16="OWN_TP=6 OWN_TP_THREADS=1 OWN_PROMPT_BLOCK=16 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G OWN_MT_TGR=16:4,1:4 OWN_MT_TGR_ROWS=0"
T5="OWN_TP=6 OWN_TP_THREADS=1 OWN_PROMPT_BLOCK=5 OWN_MT_TGM=1:1,2:1,3:3,4:2,5:3 $G"
T1="OWN_TP=6 OWN_TP_THREADS=1 OWN_PROMPT_BLOCK=1 $G"
$S/run_exp.sh e77 tp65 "h16|$T16|trace" "h5|$T5|trace" "h1|$T1|trace" "p1n0|$PL|speed"
$S/run_exp.sh e77 tp64 "p1a1|$PL|speed"
$S/run_exp.sh e77 tp65 "p1n1|$PL|speed" "p1n2|$PL|speed"
$S/run_exp.sh e77 tp64 "p1a2|$PL|speed"
sed -i '/^DONE$/d' $sum
for n in h16 h5 h1 p1n0 p1a1 p1n1 p1n2 p1a2; do grep -h "host io" $D/$n.log | sed "s/^/$n: /" >> $sum; done
journalctl -k --since "$tg" -o cat | grep -iE "$J" | head -3 | sed 's/^/FAULT: /' >> $sum
grep -q "TRACE_DIFFERS\|IDS40_DIFFER\|SPEED128_DIFFER\|exit [^0]\|FAULT" $sum && { echo STOP_GATE >> $sum; exit 1; }
PP=/home/steve/b70-optimization-lab/experiments/own-xpu-runtime/data/dsv41-bringup-20261109/spec-prompts
R57=$S/runs/e57
DS=/mnt/fast-ai/llm-models/DeepSeek-V4.1-Flash-1017-GGUF/dspark-DeepSeek-V4.1-Flash-1017-Q8_0.gguf
BEST="$PL OWN_MT_TGM=1:1,2:1,3:3,4:2,5:3,6:3 OWN_SPEC=5 OWN_SPEC_TAU=0.5 OWN_SPEC_KMIN=0 OWN_MT_TGR=2:4,3:4,4:4,5:4,6:4 OWN_MT_TGR_ROWS=4096"
s() { local name=$1 bin=$S/own_run_v41_$2 pr=$3 ref=$4 nt=$5 ms=$6 eos=$7; shift 7; t0=$(date '+%Y-%m-%d %H:%M:%S')
  echo "$name start $(mono)" >> $marks
  echo "$name before $(vm)" >> $D/vmstat.txt
  env $BEST "$@" OWN_PROMPT=$pr OWN_EOS=$eos OWN_VERIFY_REF=$ref OWN_DSPARK=$DS $bin - $nt $D/$name-ids.txt $ms > $D/$name.log 2>&1
  local rc=$?
  echo "$name after $(vm)" >> $D/vmstat.txt
  echo "$name end $(mono)" >> $marks
  echo "$name exit $rc" >> $sum; grep -h "prompt:\|spec decode\|host io\|rror\|timed out" $D/$name.log | sed "s/^/$name: /" >> $sum
  local f; f=$(journalctl -k --since "$t0" -o cat | grep -iE "$J" | head -3)
  if [ -n "$f" ] || [ $rc -ne 0 ]; then echo "$f" | sed 's/^/FAULT: /' >> $sum; echo STOP_FAULT >> $sum; exit 1; fi; }
P3=$S/prompts/p3k-ids.txt; R3=$S/runs/e52/p3kplain-ids.txt
args() { if [ $1 = p3k ]; then echo "$P3 $R3 256 4096 -1"; else echo "$PP/$1-ids.txt $R57/${1}_plain-ids.txt 512 4096 1"; fi; }
for n in code prose analysis ops docs p3k; do s ${n}_w0 tp65 $(args $n); done
for n in code prose analysis ops docs p3k; do s ${n}_a1 tp64 $(args $n); s ${n}_n1 tp65 $(args $n); done
for n in code prose analysis ops docs p3k; do s ${n}_n2 tp65 $(args $n); s ${n}_a2 tp64 $(args $n); done
for k in 5 6 7 8; do
  if [ $((k % 2)) = 1 ]; then e=OWN_ENG_AHEAD=0; a=o; else e=; a=n; fi
  s L${k}_${a}cold tp65 $S/prompts/long/L$k-ids.txt /dev/null 16 4096 -1 $e
  s L${k}_${a}warm tp65 $S/prompts/long/L$k-ids.txt /dev/null 16 4096 -1 $e
  cmp -s $D/L${k}_${a}cold-ids.txt $D/L${k}_${a}warm-ids.txt && echo "L${k} cold/warm SAME" >> $sum || echo "L${k} cold/warm DIFFER" >> $sum
done
# (4) kernel-time profiles of the 3K read on a card with one attention group (0) and the two with two (2, 5)
for cd in 0 2 5; do
  t0=$(date '+%Y-%m-%d %H:%M:%S')
  env $PL OWN_PROMPT=$P3 OWN_EOS=-1 OWN_GPROF=2 OWN_GPROF_CARD=$cd $S/own_run_v41_tp65 - 2 $D/prof$cd-ids.txt 4096 > $D/prof$cd.log 2>&1
  echo "prof$cd exit $?" >> $sum
  f=$(journalctl -k --since "$t0" -o cat | grep -iE "$J" | head -3)
  if [ -n "$f" ]; then echo "$f" | sed 's/^/FAULT: /' >> $sum; echo STOP_FAULT >> $sum; exit 1; fi
done
echo ALLDONE >> $sum
