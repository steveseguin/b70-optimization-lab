#!/bin/bash
# tp63 = tp62 + (a) OWN_ENG_LATE=1: the engram rows are fetched (and, with OWN_ENG_DEV, copied raw) and pushed after
# layer 0's launches, so the host's row work and any disk wait overlap the card's embed + layer 0 (the embed no
# longer waits for its queue); (b) OWN_ENG_DEV now stages the raw rows in ordinary host memory (no pinned buffers:
# e72's fault run used them). No CPU builds run during this campaign; it stops at the first fault line.
# (0) gates: [EARLY + LATE], [EARLY + LATE + DEV] (three traces each, plain 128); (1) plain 128 x [base, EL, ELD]
# x 2; (2) round 0 = six prompts, base, first runs after the build; rounds 1-2: [EARLY, EL, ELD] interleaved, order
# rotated per round. Per run: /proc/vmstat deltas + MemAvailable.
set -u
S=/tmp/claude-1000/-home-steve/6f61a0f6-fd06-49a3-b5b4-babc9645cc37/scratchpad
D=$S/runs/e74
mkdir -p $D
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib ZES_ENABLE_SYSMAN=1
sum=$D/summary.txt; marks=$D/marks.txt
J='fault response|cat error|engine reset|coredump has been created|gt reset|timedout job|exec queue reset|suspend fence|vm worker error|reset started'
mono() { python3 -I -c 'import time; print(f"{time.monotonic():.4f}")'; }
vm() { awk '/^(pgmajfault|pgscan_kswapd|pgscan_direct|pgsteal_kswapd|pgsteal_direct|compact_stall|compact_migrate_scanned|pgmigrate_success|thp_collapse_alloc|numa_pages_migrated|workingset_refault_file|nr_free_pages|nr_file_pages) /{printf "%s=%s ", $1, $2}' /proc/vmstat; awk '/^(MemAvailable|MemFree|Cached):/{printf "%s=%s ", $1, $2}' /proc/meminfo; echo; }
python3 -I $S/tools/gpu_sampler.py $D/telemetry.smp 0.01 &
SP=$!
trap 'kill $SP 2>/dev/null' EXIT
X="OWN_ENG_EARLY=1"; XL="OWN_ENG_EARLY=1 OWN_ENG_LATE=1"; XLD="OWN_ENG_EARLY=1 OWN_ENG_LATE=1 OWN_ENG_DEV=1"
G="OWN_MT_EU=6 OWN_MT_TGU=2 OWN_MT_RIDE=1 OWN_MT_RWG=128 OWN_MT_RFUSE=1 OWN_HC_FIN=1"
PL="OWN_TP=6 OWN_PROMPT_BLOCK=16 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G"
tg=$(date '+%Y-%m-%d %H:%M:%S')
T16="OWN_TP=6 OWN_TP_THREADS=1 OWN_PROMPT_BLOCK=16 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G OWN_MT_TGR=16:4,1:4 OWN_MT_TGR_ROWS=0"
T5="OWN_TP=6 OWN_TP_THREADS=1 OWN_PROMPT_BLOCK=5 OWN_MT_TGM=1:1,2:1,3:3,4:2,5:3 $G"
T1="OWN_TP=6 OWN_TP_THREADS=1 OWN_PROMPT_BLOCK=1 $G"
$S/run_exp.sh e74 tp63 "l16|$T16 $XL|trace" "l5|$T5 $XL|trace" "l1|$T1 $XL|trace" \
  "d16|$T16 $XLD|trace" "d5|$T5 $XLD|trace" "d1|$T1 $XLD|trace" \
  "p1b0|$PL|speed" "p1l1|$PL $XL|speed" "p1d1|$PL $XLD|speed" "p1b1|$PL|speed" \
  "p1d2|$PL $XLD|speed" "p1l2|$PL $XL|speed" "p1b2|$PL|speed"
sed -i '/^DONE$/d' $sum
for n in l16 l5 l1 d16 d5 d1 p1b0 p1l1 p1d1 p1b1 p1d2 p1l2 p1b2; do grep -h "host io" $D/$n.log | sed "s/^/$n: /" >> $sum; done
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
for n in code prose analysis ops docs p3k; do s ${n}_w0 tp63 $(args $n); done
for n in code prose analysis ops docs p3k; do s ${n}_x1 tp63 $(args $n) $X; s ${n}_l1 tp63 $(args $n) $XL; s ${n}_d1 tp63 $(args $n) $XLD; done
for n in code prose analysis ops docs p3k; do s ${n}_d2 tp63 $(args $n) $XLD; s ${n}_x2 tp63 $(args $n) $X; s ${n}_l2 tp63 $(args $n) $XL; done
echo ALLDONE >> $sum
