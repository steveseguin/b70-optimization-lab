#!/bin/bash
# run_long.sh RUN BIN then "name|ENVS|prompt_ids|ntok|maxseq"...
set -u
S=/tmp/claude-1000/-home-steve/6f61a0f6-fd06-49a3-b5b4-babc9645cc37/scratchpad
D=$S/runs/$1; bin=$S/own_run_v41_$2; shift 2
mkdir -p $D
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib ZES_ENABLE_SYSMAN=1
sum=$D/summary.txt
for spec in "$@"; do
  IFS='|' read -r name envs prompt ntok maxseq <<< "$spec"
  t0=$(date '+%Y-%m-%d %H:%M:%S')
  env $envs OWN_PROMPT=$prompt OWN_EOS=-1 $bin - $ntok $D/$name-ids.txt $maxseq > $D/$name.log 2>&1
  echo "$name exit $?" >> $sum
  grep -h "prompt:\|decode:\|rror\|timed out\|dev_index check" $D/$name.log | sed "s/^/$name: /" >> $sum
  journalctl -k --since "$t0" -o cat | grep -iE "fault response|cat error|engine reset|coredump has been created|gt reset" | head -3 >> $sum
done
echo DONE >> $sum
