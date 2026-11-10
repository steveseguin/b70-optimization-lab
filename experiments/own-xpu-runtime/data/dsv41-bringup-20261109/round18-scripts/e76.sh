#!/bin/bash
# Prompt reading (blocks of 16), tp64, no build. Waits for e75 to finish (exits if e75 stopped).
# (1) warm-up read of the 3K document; (2) settings sweep on the 3K document, two rounds (second reversed), each
#     run's first 16 answer tokens checked against the plain 3K answer: row blocks for 16-token blocks
#     (OWN_MT_TGR=16:r at row thresholds), token groups of 3 + row blocks, unpacked-row token groups;
# (3) four new long documents (L1-L4, never run), each read cold then warm with the default settings (answers
#     compared), /proc/vmstat around each run (pgpgin, major faults);
# (4) one kernel-time profile of the 3K read (card 2). Stops at the first fault line.
set -u
S=/tmp/claude-1000/-home-steve/6f61a0f6-fd06-49a3-b5b4-babc9645cc37/scratchpad
until grep -q "ALLDONE\|STOP" $S/runs/e75/summary.txt 2>/dev/null; do sleep 10; done
grep -q STOP $S/runs/e75/summary.txt && exit 1
while systemctl --user is-active --quiet dsv41-e75; do sleep 2; done
D=$S/runs/e76
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
bin=$S/own_run_v41_tp64
P3=$S/prompts/p3k-ids.txt; R3=$S/runs/e52/p3kplain-ids.txt
head -16 $R3 > $D/ref16.txt
s() { local name=$1 pr=$2 nt=$3; shift 3; t0=$(date '+%Y-%m-%d %H:%M:%S')
  echo "$name start $(mono)" >> $marks
  echo "$name before $(vm)" >> $D/vmstat.txt
  env $PL "$@" OWN_PROMPT=$pr OWN_EOS=-1 $bin - $nt $D/$name-ids.txt 4096 > $D/$name.log 2>&1
  local rc=$?
  echo "$name after $(vm)" >> $D/vmstat.txt
  echo "$name end $(mono)" >> $marks
  echo "$name exit $rc" >> $sum; grep -h "prompt:\|decode:\|rror\|timed out" $D/$name.log | sed "s/^/$name: /" >> $sum
  local f; f=$(journalctl -k --since "$t0" -o cat | grep -iE "$J" | head -3)
  if [ -n "$f" ] || [ $rc -ne 0 ]; then echo "$f" | sed 's/^/FAULT: /' >> $sum; echo STOP_FAULT >> $sum; exit 1; fi; }
chk() { cmp -s <(head -16 $D/$1-ids.txt) $D/ref16.txt && echo "$1 ANSWER16_SAME" >> $sum || echo "$1 ANSWER16_DIFFER" >> $sum; }
declare -A A
A[b]=""
A[r4]="OWN_MT_TGR=16:4 OWN_MT_TGR_ROWS=4096"
A[r4m]="OWN_MT_TGR=16:4 OWN_MT_TGR_ROWS=2048"
A[r4z]="OWN_MT_TGR=16:4 OWN_MT_TGR_ROWS=0"
A[r2]="OWN_MT_TGR=16:2 OWN_MT_TGR_ROWS=4096"
A[g3]="OWN_MT_TGM=16:3 OWN_MT_TGR=16:4 OWN_MT_TGR_ROWS=4096"
A[u3]="OWN_MT_TGU=3"
A[u0]="OWN_MT_TGU=0"
ORD="b r4 r4m r4z r2 g3 u3 u0"
s p3k_warm $P3 16; chk p3k_warm
for a in $ORD; do s p3k_${a}1 $P3 16 ${A[$a]}; chk p3k_${a}1; done
for a in $(echo $ORD | tr ' ' '\n' | tac); do s p3k_${a}2 $P3 16 ${A[$a]}; chk p3k_${a}2; done
for k in 1 2 3 4; do
  s L${k}_cold $S/prompts/long/L$k-ids.txt 16
  s L${k}_warm $S/prompts/long/L$k-ids.txt 16
  cmp -s $D/L${k}_cold-ids.txt $D/L${k}_warm-ids.txt && echo "L${k} cold/warm SAME" >> $sum || echo "L${k} cold/warm DIFFER" >> $sum
done
s p3k_prof $P3 2 OWN_GPROF=2 OWN_GPROF_CARD=2
echo ALLDONE >> $sum
