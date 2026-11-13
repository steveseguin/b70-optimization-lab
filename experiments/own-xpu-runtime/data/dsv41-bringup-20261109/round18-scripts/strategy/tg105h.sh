#!/bin/bash
# tg105h (2026-11-12): OWN_MT_EU_HEAVY=0 (rux3 side finding: plain expert-group order, -6 % routed kernel time on one card).
# tp105 binary; 3K traces vs t3k_ref (256, px-512), then 3K reads alternated x2 (256 answers vs e52 plain).
# tg105: gate for tp105 = tp104 + xorP compiled in (-DOWN_R2_XORP=1, default path: the traces are its exactness check)
# + fl-1 (OWN_FL=1..3 opt-in) + OWN_U3_NOPAIR=1 (opt-in) + sw (OWN_MT_SW=1 checks / 2 one-token / 3 both, opt-in).
# No b300 / PX halves of 150 (banned: host resets). Speed only from unprofiled runs alternated.
set -u
W=/home/steve/dsv41-work
L=/home/steve/b70-optimization-lab
D=$W/runs/tg105h
mkdir -p $D
sum=$D/summary.txt; marks=$D/marks.txt
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib ZES_ENABLE_SYSMAN=1
J='fault response|cat error|engine reset|coredump has been created|gt reset|timedout job|exec queue reset|suspend fence|vm worker error|reset started|PCIe Bus Error|AER:|Hardware Error|Machine check'
mono() { python3 -I -c 'import time; print(f"{time.monotonic():.4f}")'; }
fcheck() { local w f; w=$(journalctl -k --since "$1" -o cat); f=$(echo "$w" | grep -iE "$J"); [ -z "$f" ] && return 0
  if ! echo "$f" | grep -qvE '^\{[0-9]+\}\[Hardware Error\]' && ! echo "$w" | grep -qE 'event severity: (fatal|recoverable)'; then
    echo "WARN corrected PCIe: $(echo "$w" | grep -E 'device_id: 0000' | sort | uniq -c | tr -s ' ' | tr '\n' ';')" >> $sum; return 0; fi
  echo "$f" | head -3 | sed 's/^/FAULT: /' >> $sum; echo STOP_FAULT >> $sum; exit 1; }
memwait() { local i=0; until [ $(awk '/MemAvailable/ {print int($2/1048576)}' /proc/meminfo) -ge 7 ] || [ $i -ge 120 ]; do sleep 5; i=$((i+1)); done; }
SP=
until [ ! -e $W/six.active ]; do sleep 5; done
touch $W/six.active
trap 'rm -f $W/six.active; [ -n "$SP" ] && kill $SP 2>/dev/null' EXIT
while [ -n "$(ls -A $W/locks 2>/dev/null)" ] || pgrep -f "^/home/steve/dsv41-work/own_run_v41" > /dev/null || pgrep -x icpx > /dev/null || pgrep -x ocloc > /dev/null; do sleep 10; done
SP= # gpu_sampler off since 2026-11-12 19:20: its 120 card-register reads per second are CPU waits on the cards (host-reset victims)
tg=$(date '+%Y-%m-%d %H:%M:%S')
echo "start $tg" >> $sum
G="OWN_MT_EU=6 OWN_MT_TGU=2 OWN_MT_RIDE=1 OWN_MT_RWG=128 OWN_MT_RFUSE=1 OWN_HC_FIN=1"
PL="OWN_TP=6 OWN_PROMPT_BLOCK=64 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G"
TB="OWN_TP=6 OWN_TP_THREADS=1 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G OWN_MT_TGR=16:4,1:4 OWN_MT_TGR_ROWS=0"
T5="OWN_TP=6 OWN_TP_THREADS=1 OWN_PROMPT_BLOCK=5 OWN_MT_TGM=1:1,2:1,3:3,4:2,5:3 $G"
T1="OWN_TP=6 OWN_TP_THREADS=1 OWN_PROMPT_BLOCK=1 $G"
TM="OWN_TP=6 OWN_TP_THREADS=1 OWN_MT_TG=4 OWN_MT_TG_MAX=16 OWN_MT_TGM=1:1,2:1,3:3,4:2,5:3,6:3 $G"
AX="OWN_PAIR_G128=1 OWN_MT_PACE=1" # A (tp102) = tp104's defaults
OFF="OWN_PAIR_G128=0 OWN_MT_PACE=0 OWN_PB=0 OWN_ATT_WA=0"
R127="OWN_MT_PACE_ROLES=127"
PX="OWN_PX=1 OWN_PX_CHECK=1"
VOC="OWN_DR_VOCAB=$W/draft/vocab/cand-c32k-dict.txt OWN_DR_VOCAB_N=60000"
okn() { for n in "$@"; do grep -q "^$n TRACE_IDENTICAL" $sum && grep -q "^$n IDS40_SAME" $sum || return 1; done; }
PB="OWN_PX=1 OWN_PX_BIG=1 OWN_PX_CHECK=1"
W8="OWN_PX_WGS=16,16,16,16,8,8,16,16"; W4="OWN_PX_WGS=16,16,16,16,4,4,16,16"
r() { local name=$1 b=$2 pr=$3 nt=$4 mx=$5 eos=$6 out=$7; shift 7; local t0; t0=$(date '+%Y-%m-%d %H:%M:%S')
  memwait; echo "$name start $(mono)" >> $marks
  env "$@" OWN_PROMPT=$pr OWN_EOS=$eos $W/own_run_v41_$b - $nt $out $mx > $D/$name.log 2>&1
  local rc=$?
  echo "$name end $(mono)" >> $marks
  echo "$name exit $rc" >> $sum
  grep -h "prompt:\|decode:\|spec decode\|kept guesses\|rror\|timed out\|exceeds\|MISMATCH" $D/$name.log | sed "s/^/$name: /" >> $sum
  fcheck "$t0"
  [ $rc -eq 0 ] || { echo STOP_EXIT >> $sum; exit 1; }; }
same() { cmp -s <(head -$3 $1) <(head -$3 $2) && echo "$4 ANSWER$3_SAME" >> $sum || echo "$4 ANSWER$3_DIFFERS" >> $sum; }
p=$W/prompts/p3k-ids.txt
REF=$W/runs/gm64/t3k_ref
t3k() { local nm=$1; shift
  r t3k_$nm tp105 $p 40 4096 1 $D/t3k_$nm-ids.txt $TB "$@" OWN_TRACE=$D/t3k_$nm.trc OWN_TRACE_STEPS=3
  cmp -s $D/t3k_$nm.trc $REF.trc && echo "t3k_$nm TRACE_IDENTICAL" >> $sum || echo "t3k_$nm TRACE_DIFFERS" >> $sum
  cmp -s $D/t3k_$nm-ids.txt $REF-ids.txt && echo "t3k_$nm IDS40_SAME" >> $sum || echo "t3k_$nm IDS40_DIFFER" >> $sum
  rm -f $D/t3k_$nm.trc; }
FLB="OWN_FL=3 OWN_U3_NOPAIR=1"
t3k b256h0 OWN_PROMPT_BLOCK=256 $FLB OWN_MT_EU_HEAVY=0
t3k b512pxh0 OWN_PROMPT_BLOCK=512 $PB $FLB OWN_MT_EU_HEAVY=0
okn t3k_b256h0 t3k_b512pxh0 || { echo STOP_TRACE >> $sum; exit 1; }
for rd in 1 2; do
  r p3k_px_$rd tp105 $p 256 4096 -1 $D/p3k_px_$rd-ids.txt $PL $FLB OWN_PROMPT_BLOCK=512 OWN_PX=1 OWN_PX_BIG=1; same $D/p3k_px_$rd-ids.txt $W/runs/e52/p3kplain-ids.txt 256 p3k_px_$rd
  r p3k_pxh0_$rd tp105 $p 256 4096 -1 $D/p3k_pxh0_$rd-ids.txt $PL $FLB OWN_PROMPT_BLOCK=512 OWN_PX=1 OWN_PX_BIG=1 OWN_MT_EU_HEAVY=0; same $D/p3k_pxh0_$rd-ids.txt $W/runs/e52/p3kplain-ids.txt 256 p3k_pxh0_$rd
  r p3k_b256_$rd tp105 $p 256 4096 -1 $D/p3k_b256_$rd-ids.txt $PL $FLB OWN_PROMPT_BLOCK=256; same $D/p3k_b256_$rd-ids.txt $W/runs/e52/p3kplain-ids.txt 256 p3k_b256_$rd
  r p3k_b256h0_$rd tp105 $p 256 4096 -1 $D/p3k_b256h0_$rd-ids.txt $PL $FLB OWN_PROMPT_BLOCK=256 OWN_MT_EU_HEAVY=0; same $D/p3k_b256h0_$rd-ids.txt $W/runs/e52/p3kplain-ids.txt 256 p3k_b256h0_$rd
done
grep -q "ANSWER.*DIFFERS" $sum && echo "SOME_DIFFER" >> $sum
echo ALLDONE >> $sum
