#!/bin/bash
# tp64 = tp63 with OWN_ENG_EARLY, OWN_ENG_LATE and OWN_ENG_DEV on by default (e74: median 97.5-98.0 -> 99.0, every
# answer SAME), + OWN_TP_SPIN_US=n: the main thread and the card threads poll for each other's hand-off for up to n us
# before sleeping (two hand-offs each way per round). No CPU builds during this campaign; stops at the first fault.
# (0) gates: tp64 default (three traces, plain 128), SPIN 2000 (three traces, plain 128); plain 128 x [old way
#     (all three off), default, SPIN] x 2;
# (1) round 0 = six prompts, default; rounds 1-2: [default, SPIN 2000] interleaved, order swapped in round 2;
# (2) twelve fresh prompts f13-f24 (never run), each cold then warm: odd = old way (all three off), even = default.
set -u
S=/tmp/claude-1000/-home-steve/6f61a0f6-fd06-49a3-b5b4-babc9645cc37/scratchpad
D=$S/runs/e75
mkdir -p $D
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib ZES_ENABLE_SYSMAN=1
sum=$D/summary.txt; marks=$D/marks.txt
J='fault response|cat error|engine reset|coredump has been created|gt reset|timedout job|exec queue reset|suspend fence|vm worker error|reset started'
mono() { python3 -I -c 'import time; print(f"{time.monotonic():.4f}")'; }
vm() { awk '/^(pgmajfault|pgscan_kswapd|pgscan_direct|pgsteal_kswapd|pgsteal_direct|compact_stall|compact_migrate_scanned|pgmigrate_success|thp_collapse_alloc|numa_pages_migrated|workingset_refault_file|nr_free_pages|nr_file_pages) /{printf "%s=%s ", $1, $2}' /proc/vmstat; awk '/^(MemAvailable|MemFree|Cached):/{printf "%s=%s ", $1, $2}' /proc/meminfo; echo; }
python3 -I $S/tools/gpu_sampler.py $D/telemetry.smp 0.01 &
SP=$!
trap 'kill $SP 2>/dev/null' EXIT
OLD="OWN_ENG_EARLY=0 OWN_ENG_LATE=0 OWN_ENG_DEV=0"; SPN="OWN_TP_SPIN_US=2000"
G="OWN_MT_EU=6 OWN_MT_TGU=2 OWN_MT_RIDE=1 OWN_MT_RWG=128 OWN_MT_RFUSE=1 OWN_HC_FIN=1"
PL="OWN_TP=6 OWN_PROMPT_BLOCK=16 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G"
tg=$(date '+%Y-%m-%d %H:%M:%S')
T16="OWN_TP=6 OWN_TP_THREADS=1 OWN_PROMPT_BLOCK=16 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G OWN_MT_TGR=16:4,1:4 OWN_MT_TGR_ROWS=0"
T5="OWN_TP=6 OWN_TP_THREADS=1 OWN_PROMPT_BLOCK=5 OWN_MT_TGM=1:1,2:1,3:3,4:2,5:3 $G"
T1="OWN_TP=6 OWN_TP_THREADS=1 OWN_PROMPT_BLOCK=1 $G"
$S/run_exp.sh e75 tp64 "h16|$T16|trace" "h5|$T5|trace" "h1|$T1|trace" \
  "s16|$T16 $SPN|trace" "s5|$T5 $SPN|trace" "s1|$T1 $SPN|trace" \
  "p1o0|$PL $OLD|speed" "p1n1|$PL|speed" "p1s1|$PL $SPN|speed" "p1o1|$PL $OLD|speed" \
  "p1s2|$PL $SPN|speed" "p1n2|$PL|speed" "p1o2|$PL $OLD|speed"
sed -i '/^DONE$/d' $sum
for n in h16 h5 h1 s16 s5 s1 p1o0 p1n1 p1s1 p1o1 p1s2 p1n2 p1o2; do grep -h "host io" $D/$n.log | sed "s/^/$n: /" >> $sum; done
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
  echo "$name exit $rc" >> $sum; grep -h "spec decode\|host io\|rror\|timed out" $D/$name.log | sed "s/^/$name: /" >> $sum
  local f; f=$(journalctl -k --since "$t0" -o cat | grep -iE "$J" | head -3)
  if [ -n "$f" ] || [ $rc -ne 0 ]; then echo "$f" | sed 's/^/FAULT: /' >> $sum; echo STOP_FAULT >> $sum; exit 1; fi; }
P3=$S/prompts/p3k-ids.txt; R3=$S/runs/e52/p3kplain-ids.txt
args() { if [ $1 = p3k ]; then echo "$P3 $R3 256 4096 -1"; else echo "$PP/$1-ids.txt $R57/${1}_plain-ids.txt 512 4096 1"; fi; }
for n in code prose analysis ops docs p3k; do s ${n}_w0 tp64 $(args $n); done
for n in code prose analysis ops docs p3k; do s ${n}_n1 tp64 $(args $n); s ${n}_s1 tp64 $(args $n) $SPN; done
for n in code prose analysis ops docs p3k; do s ${n}_s2 tp64 $(args $n) $SPN; s ${n}_n2 tp64 $(args $n); done
FP=$S/prompts/fresh
for k in 13 14 15 16 17 18 19 20 21 22 23 24; do
  if [ $((k % 2)) = 1 ]; then e=$OLD; a=o; else e=; a=n; fi
  s f${k}_${a}cold tp64 $FP/f$k-ids.txt /dev/null 512 4096 1 $e
  s f${k}_${a}warm tp64 $FP/f$k-ids.txt /dev/null 512 4096 1 $e
  cmp -s $D/f${k}_${a}cold-ids.txt $D/f${k}_${a}warm-ids.txt && echo "f${k} cold/warm SAME" >> $sum || echo "f${k} cold/warm DIFFER" >> $sum
done
echo ALLDONE >> $sum
