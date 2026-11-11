#!/bin/bash
# p80: where the time goes now (tp79 defaults), short runs only: OWN_GPROF=2 OWN_GPROF_DECODE=1 profiles of
# (a) plain one-token answer steps on prompt 1 (cards 2 and 0), (b) guessing rounds on the code prompt (cards 2, 0)
set -u
W=/home/steve/dsv41-work
L=/home/steve/b70-optimization-lab
D=$W/runs/p80
mkdir -p $D
sum=$D/summary.txt
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib ZES_ENABLE_SYSMAN=1
J='fault response|cat error|engine reset|coredump has been created|gt reset|timedout job|exec queue reset|suspend fence|vm worker error|reset started|PCIe Bus Error|AER:|Hardware Error|Machine check'
fcheck() { local w f; w=$(journalctl -k --since "$1" -o cat); f=$(echo "$w" | grep -iE "$J"); [ -z "$f" ] && return 0
  if ! echo "$f" | grep -qvE '^\{[0-9]+\}\[Hardware Error\]' && ! echo "$w" | grep -qE 'event severity: (fatal|recoverable)'; then
    echo "WARN corrected PCIe: $(echo "$w" | grep -E 'device_id: 0000' | sort | uniq -c | tr -s ' ' | tr '\n' ';')" >> $sum; return 0; fi
  echo "$f" | head -3 | sed 's/^/FAULT: /' >> $sum; echo STOP_FAULT >> $sum; exit 1; }
G="OWN_MT_EU=6 OWN_MT_TGU=2 OWN_MT_RIDE=1 OWN_MT_RWG=128 OWN_MT_RFUSE=1 OWN_HC_FIN=1"
PL="OWN_TP=6 OWN_PROMPT_BLOCK=16 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G"
DS=/mnt/fast-ai/llm-models/DeepSeek-V4.1-Flash-1017-GGUF/dspark-DeepSeek-V4.1-Flash-1017-Q8_0.gguf
BEST="$PL OWN_MT_TGM=1:1,2:1,3:3,4:2,5:3,6:3 OWN_SPEC=5 OWN_SPEC_TAU=0.5 OWN_SPEC_KMIN=0 OWN_MT_TGR=2:4,3:4,4:4,5:4,6:4 OWN_MT_TGR_ROWS=4096"
P1=$L/experiments/own-xpu-runtime/data/dsv41-bringup-20261109/prompt1-ids.txt
PP=$L/experiments/own-xpu-runtime/data/dsv41-bringup-20261109/spec-prompts
r() { local name=$1; shift; local t0; t0=$(date '+%Y-%m-%d %H:%M:%S')
  env "$@" > $D/$name.log 2>&1; echo "$name exit $?" >> $sum
  grep -h "prompt:\|decode:\|spec decode\|rror\|timed out\|MISMATCH" $D/$name.log | sed "s/^/$name: /" >> $sum
  fcheck "$t0"; }
for c in 2 0; do
  r p1_c$c $PL OWN_GPROF=2 OWN_GPROF_DECODE=1 OWN_GPROF_CARD=$c OWN_PROMPT=$P1 OWN_EOS=-1 $W/own_run_v41_tp79 - 128 $D/p1_c$c-ids.txt 4096
  r code_c$c $BEST OWN_GPROF=2 OWN_GPROF_DECODE=1 OWN_GPROF_CARD=$c OWN_DSPARK=$DS OWN_PROMPT=$PP/code-ids.txt OWN_EOS=1 $W/own_run_v41_tp79 - 512 $D/code_c$c-ids.txt 4096
done
echo ALLDONE >> $sum
