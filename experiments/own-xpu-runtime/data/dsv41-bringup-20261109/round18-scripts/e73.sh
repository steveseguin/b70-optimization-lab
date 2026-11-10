#!/bin/bash
# tp62 = tp61 + OWN_ENG_EARLY=1: the engram rows' disk reads start sooner (the anchor's 48 rows while the draft runs;
# a block's other rows split over the six card threads, each asking for its share and waiting on it before reading
# all rows; MADV_RANDOM on the table so a miss reads one page). e72 showed the "slow mode" is engram rows missing
# from the page cache (after a build: 78-123 MiB read from disk per answer, 0.75-0.80 ms per step on the rows vs
# ~0.19-0.36 warm). OWN_ENG_DEV stays off (e72: a GPU fault on card 43 in one of its runs; suspect, not proven).
# No CPU builds run during this campaign. The campaign stops at the first fault line in the kernel log.
# (0) gates with OWN_ENG_EARLY=1 (three traces, plain 128) + plain 128 without;
# (1) round 0: six prompts, base, the first runs after the build (rows partly evicted); rounds 1-2: base vs EARLY,
#     order swapped in round 2; (2) twelve fresh prompts (never run): odd ones EARLY, even ones base, each run
#     cold then warm: the cold-row cost per arm. Per run: /proc/vmstat deltas + MemAvailable (to pin a fault).
set -u
S=/tmp/claude-1000/-home-steve/6f61a0f6-fd06-49a3-b5b4-babc9645cc37/scratchpad
D=$S/runs/e73
mkdir -p $D
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib ZES_ENABLE_SYSMAN=1
sum=$D/summary.txt; marks=$D/marks.txt
J='fault response|cat error|engine reset|coredump has been created|gt reset|timedout job|exec queue reset|suspend fence|vm worker error|reset started'
mono() { python3 -I -c 'import time; print(f"{time.monotonic():.4f}")'; }
vm() { awk '/^(pgmajfault|pgscan_kswapd|pgscan_direct|pgsteal_kswapd|pgsteal_direct|compact_stall|compact_migrate_scanned|pgmigrate_success|thp_collapse_alloc|numa_pages_migrated|workingset_refault_file|nr_free_pages|nr_file_pages) /{printf "%s=%s ", $1, $2}' /proc/vmstat; awk '/^(MemAvailable|MemFree|Cached):/{printf "%s=%s ", $1, $2}' /proc/meminfo; echo; }
python3 -I $S/tools/gpu_sampler.py $D/telemetry.smp 0.01 &
SP=$!
trap 'kill $SP 2>/dev/null' EXIT
X="OWN_ENG_EARLY=1"
G="OWN_MT_EU=6 OWN_MT_TGU=2 OWN_MT_RIDE=1 OWN_MT_RWG=128 OWN_MT_RFUSE=1 OWN_HC_FIN=1"
PL="OWN_TP=6 OWN_PROMPT_BLOCK=16 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G"
tg=$(date '+%Y-%m-%d %H:%M:%S')
$S/run_exp.sh e73 tp62 "h16|OWN_TP=6 OWN_TP_THREADS=1 OWN_PROMPT_BLOCK=16 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G OWN_MT_TGR=16:4,1:4 OWN_MT_TGR_ROWS=0 $X|trace" \
  "h5|OWN_TP=6 OWN_TP_THREADS=1 OWN_PROMPT_BLOCK=5 OWN_MT_TGM=1:1,2:1,3:3,4:2,5:3 $G $X|trace" \
  "h1|OWN_TP=6 OWN_TP_THREADS=1 OWN_PROMPT_BLOCK=1 $G $X|trace" \
  "p1x|$PL $X|speed" \
  "p1b|$PL|speed"
sed -i '/^DONE$/d' $sum
for n in h16 h5 h1 p1x p1b; do grep -h "host io" $D/$n.log | sed "s/^/$n: /" >> $sum; done
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
for n in code prose analysis ops docs p3k; do s ${n}_w0 tp62 $(args $n); done
for n in code prose analysis ops docs p3k; do s ${n}_b1 tp62 $(args $n); s ${n}_x1 tp62 $(args $n) $X; done
for n in code prose analysis ops docs p3k; do s ${n}_x2 tp62 $(args $n) $X; s ${n}_b2 tp62 $(args $n); done
# fresh prompts, each cold then warm with the same setting
FP=$S/prompts/fresh
for k in 1 2 3 4 5 6 7 8 9 10 11 12; do
  if [ $((k % 2)) = 1 ]; then e=$X; a=x; else e=; a=b; fi
  s f${k}_${a}cold tp62 $FP/f$k-ids.txt /dev/null 512 4096 1 $e
  s f${k}_${a}warm tp62 $FP/f$k-ids.txt /dev/null 512 4096 1 $e
  cmp -s $D/f${k}_${a}cold-ids.txt $D/f${k}_${a}warm-ids.txt && echo "f${k} cold/warm SAME" >> $sum || echo "f${k} cold/warm DIFFER" >> $sum
done
echo ALLDONE >> $sum
