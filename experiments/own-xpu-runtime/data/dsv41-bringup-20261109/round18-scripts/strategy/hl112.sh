#!/bin/bash
# hl112 (2026-11-13): under the 200 W cap card 3 (0000:83) runs the prompt kernels ~12 % slower than the others
# (tlpx112: experts 406.6 vs ~363 ms, dense 287 vs ~255 per 512 piece) and is the critical card. Arms: the prompt
# head layout (whole 4-head units, same bits) with card 3 lighter: L1 = 3,3,2,2,3,3, L2 = 3,3,3,2,3,2 (default
# 3,3,3,3,2,2), blocks of >= 16 tokens only. Gate: 3K traces at px-512 vs runs/gm64/t3k_ref; then 3K reads
# D L1 L2 L2 L1 D (unprofiled, 256 answers vs runs/e52). Each run its own six.active take (>= 195 s quiet).
set -u
W=/home/steve/dsv41-work; D=$W/runs/hl112; mkdir -p $D; sum=$D/summary.txt
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib ZES_ENABLE_SYSMAN=1
J='fault response|cat error|engine reset|coredump has been created|gt reset|timedout job|exec queue reset|suspend fence|vm worker error|reset started|PCIe Bus Error|AER:|Hardware Error|Machine check'
now() { date +%s; }; lp=$(now)
take() { local q=0; until [ $q -ge 195 ]; do if [ -e $W/six.active ]; then q=0; lp=$(now); else q=$((q+2)); fi; pgrep '^own_run_v41' > /dev/null && lp=$(now); sleep 2; done
  sleep $((RANDOM % 4 + 1)); [ -e $W/six.active ] && { lp=$(now); return 1; }; touch $W/six.active; }
hold() { while [ $(( $(now) - lp )) -lt 210 ] || [ -n "$(ls -A $W/locks 2>/dev/null)" ] || pgrep '^own_run_v41' > /dev/null || pgrep -x icpx > /dev/null || pgrep -x ocloc > /dev/null; do
  pgrep '^own_run_v41' > /dev/null && lp=$(now); touch $W/six.active; sleep 2; done; }
memwait() { local i=0; until [ $(awk '/MemAvailable/ {print int($2/1048576)}' /proc/meminfo) -ge 7 ] || [ $i -ge 120 ]; do sleep 5; i=$((i+1)); done; }
fcheck() { local w f; w=$(journalctl -k --since "$1" -o cat); f=$(echo "$w" | grep -iE "$J"); [ -z "$f" ] && return 0
  if ! echo "$f" | grep -qvE '^\{[0-9]+\}\[Hardware Error\]' && ! echo "$w" | grep -qE 'event severity: (fatal|recoverable)'; then
    echo "WARN corrected PCIe: $(echo "$w" | grep -E 'device_id: 0000' | sort | uniq -c | tr -s ' ' | tr '\n' ';')" >> $sum; return 0; fi
  echo "$f" | head -3 | sed 's/^/FAULT: /' >> $sum; echo STOP_FAULT >> $sum; exit 1; }
trap 'rm -f $W/six.active' EXIT
G="OWN_MT_EU=6 OWN_MT_TGU=2 OWN_MT_RIDE=1 OWN_MT_RWG=128 OWN_MT_RFUSE=1 OWN_HC_FIN=1"
PL="OWN_TP=6 OWN_PROMPT_BLOCK=64 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G"
TB="OWN_TP=6 OWN_TP_THREADS=1 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G OWN_MT_TGR=16:4,1:4 OWN_MT_TGR_ROWS=0"
P5="OWN_PROMPT_BLOCK=512 OWN_PX=1 OWN_PX_BIG=1"
PB="OWN_PX=1 OWN_PX_BIG=1 OWN_PX_CHECK=1"
A_D=""; A_L1="OWN_TP_HEADS=3,3,2,2,3,3 OWN_TP_HEADS_MIN=16"; A_L2="OWN_TP_HEADS=3,3,3,2,3,2 OWN_TP_HEADS_MIN=16"
p=$W/prompts/p3k-ids.txt; REF=$W/runs/gm64/t3k_ref
r() { local name=$1 nt=$2 eos=$3 out=$4; shift 4; local t0 rc
  until take; do :; done; hold; memwait; t0=$(date '+%Y-%m-%d %H:%M:%S'); echo "$name start $t0" >> $sum
  timeout 600 env "$@" OWN_PROMPT=$p OWN_EOS=$eos $W/own_run_v41_tp112 - $nt $out 4096 > $D/$name.log 2>&1; rc=$?
  rm -f $W/six.active; lp=$(now)
  echo "$name exit $rc" >> $sum
  grep -h "prompt:\|decode:\|rror\|timed out\|MISMATCH\|heads" $D/$name.log | sed "s/^/$name: /" >> $sum
  fcheck "$t0"; [ $rc -eq 0 ] || { echo STOP_EXIT >> $sum; exit 1; }; }
for a in L1 L2; do
  v=A_$a; r t3k_$a 40 1 $D/t3k_$a-ids.txt $TB OWN_PROMPT_BLOCK=512 $PB ${!v} OWN_TRACE=$D/t3k_$a.trc OWN_TRACE_STEPS=3
  cmp -s $D/t3k_$a.trc $REF.trc && echo "t3k_$a TRACE_IDENTICAL" >> $sum || echo "t3k_$a TRACE_DIFFERS" >> $sum
  cmp -s $D/t3k_$a-ids.txt $REF-ids.txt && echo "t3k_$a IDS40_SAME" >> $sum || echo "t3k_$a IDS40_DIFFER" >> $sum
  rm -f $D/t3k_$a.trc
done
ok=""; for a in L1 L2; do grep -q "^t3k_$a TRACE_IDENTICAL" $sum && grep -q "^t3k_$a IDS40_SAME" $sum && ok="$ok $a"; done
echo "gate: identical arms:$ok" >> $sum
[ -z "$ok" ] && { echo STOP_GATE >> $sum; exit 1; }
seq=(D); for a in $ok; do seq+=($a); done; for a in $(echo $ok | tr ' ' '\n' | tac); do seq+=($a); done; seq+=(D)
i=0; for a in "${seq[@]}"; do i=$((i+1)); v=A_$a
  r p3k_${a}_$i 256 -1 $D/p3k_${a}_$i-ids.txt $PL $P5 ${!v}
  cmp -s <(head -256 $D/p3k_${a}_$i-ids.txt) <(head -256 $W/runs/e52/p3kplain-ids.txt) && echo "p3k_${a}_$i ANSWER256_SAME" >> $sum || echo "p3k_${a}_$i ANSWER256_DIFFERS" >> $sum
done
echo ALLDONE >> $sum
