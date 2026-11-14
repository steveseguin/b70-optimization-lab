#!/bin/bash
# tlpx112 (2026-11-13): prompt timelines on tp112 at the 200 W cap: late in the 95K document (pieces 183-184) and a 3K
# control (pieces 3-4), px-512 + copy engine, for the long-context prompt budget (what grows with context).
# Profiled: per-kernel times valid, overlap not; speeds from these runs are not used.
set -u
W=/home/steve/dsv41-work; D=$W/runs/tlpx112; mkdir -p $D; sum=$D/summary.txt
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib ZES_ENABLE_SYSMAN=1
J='fault response|cat error|engine reset|coredump has been created|gt reset|timedout job|exec queue reset|suspend fence|vm worker error|reset started|PCIe Bus Error|AER:|Hardware Error|Machine check'
now() { date +%s; }; lp=$(now)
take() { local q=0; until [ $q -ge 195 ]; do if [ -e $W/six.active ]; then q=0; lp=$(now); else q=$((q+2)); fi; pgrep '^own_run_v41' > /dev/null && lp=$(now); sleep 2; done
  sleep $((RANDOM % 4 + 1)); [ -e $W/six.active ] && { lp=$(now); return 1; }; touch $W/six.active; }
hold() { while [ $(( $(now) - lp )) -lt 210 ] || [ -n "$(ls -A $W/locks 2>/dev/null)" ] || pgrep '^own_run_v41' > /dev/null || pgrep -x icpx > /dev/null || pgrep -x ocloc > /dev/null; do
  pgrep '^own_run_v41' > /dev/null && lp=$(now); touch $W/six.active; sleep 2; done; }
memwait() { local i=0; until [ $(awk '/MemAvailable/ {print int($2/1048576)}' /proc/meminfo) -ge 7 ] || [ $i -ge 120 ]; do sleep 5; i=$((i+1)); done; }
G="OWN_MT_EU=6 OWN_MT_TGU=2 OWN_MT_RIDE=1 OWN_MT_RWG=128 OWN_MT_RFUSE=1 OWN_HC_FIN=1"
PL="OWN_TP=6 OWN_PROMPT_BLOCK=64 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G"
P5="OWN_PROMPT_BLOCK=512 OWN_PX=1 OWN_PX_BIG=1"
run() { local name=$1 p=$2 pcs=$3 mx t0 rc
  until take; do :; done; hold; memwait
  mx=$(( ( $(wc -l < $p) + 256 + 1023 ) / 1024 * 1024 )); t0=$(date '+%Y-%m-%d %H:%M:%S')
  echo "$name start $t0" >> $sum
  timeout 900 env $PL $P5 OWN_PROMPT=$p OWN_EOS=-1 OWN_TIMELINE=$D/$name.txt OWN_TIMELINE_PROMPT=$pcs $W/own_run_v41_tp112 - 8 $D/$name-ids.txt $mx > $D/$name.log 2>&1; rc=$?
  echo "$name exit $rc $(date +%T)" >> $sum; grep -h "prompt:\|rror\|free after load" $D/$name.log | sed "s/^/$name: /" >> $sum
  rm -f $W/six.active
  f=$(journalctl -k --since "$t0" -o cat | grep -iE "$J" | head -3); [ -n "$f" ] && { echo "FAULT: $f" >> $sum; echo STOP_FAULT >> $sum; exit 1; }
}
trap 'rm -f $W/six.active' EXIT
run tlpx_95k $W/prompts/xl/x95k-ids.txt 183-184
run tlp_3k $W/prompts/p3k-ids.txt 3-4
echo ALLDONE >> $sum
