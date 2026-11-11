#!/bin/bash
# u84: every prompt token's 6 expert ids per layer (OWN_MT_IDSTAT=1 OWN_MT_IDDUMP, card 0, diagnostic with waits) on the
# 3K and 10K prompts, blocks of 16, 2 answer tokens; offline: distinct experts per block of M tokens (prefill plan step 0).
# SHORT six-card runs (3K / 10K reads; the paused class is 34K-95K).
set -u
W=/home/steve/dsv41-work; D=$W/runs/u84; mkdir -p $D; sum=$D/summary.txt
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib ZES_ENABLE_SYSMAN=1
J='fault response|cat error|engine reset|coredump has been created|gt reset|timedout job|exec queue reset|suspend fence|vm worker error|reset started|PCIe Bus Error|AER:|Hardware Error|Machine check'
grep -q "exit 0" $W/build-tp84.log || { echo STOP_BUILD >> $sum; exit 1; }
G="OWN_MT_EU=6 OWN_MT_TGU=2 OWN_MT_RIDE=1 OWN_MT_RWG=128 OWN_MT_RFUSE=1 OWN_HC_FIN=1"
PL="OWN_TP=6 OWN_PROMPT_BLOCK=16 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G"
for k in "p3k|$W/prompts/p3k-ids.txt" "p10k|$W/prompts/p10k-ids.txt"; do
  IFS='|' read -r name pr <<< "$k"; t0=$(date '+%Y-%m-%d %H:%M:%S')
  env $PL OWN_MT_IDSTAT=1 OWN_MT_IDDUMP=$D/$name-ids-per-layer.txt OWN_PROMPT=$pr OWN_EOS=-1 $W/own_run_v41_tp84 - 2 $D/$name-ans.txt 16384 > $D/$name.log 2>&1
  echo "$name exit $?" >> $sum
  grep -h "prompt:\|expert picks\|rror" $D/$name.log | sed "s/^/$name: /" >> $sum
  f=$(journalctl -k --since "$t0" -o cat | grep -iE "$J" | grep -vE '^\{[0-9]+\}\[Hardware Error\]' | head -3)
  [ -n "$f" ] && { echo "$f" | sed 's/^/FAULT: /' >> $sum; echo STOP_FAULT >> $sum; exit 1; }
done
echo ALLDONE >> $sum
