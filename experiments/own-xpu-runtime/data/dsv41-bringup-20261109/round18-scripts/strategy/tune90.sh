#!/bin/bash
# tune90: guessing settings on tp89 (short six-card runs, the code / analysis prompts, 512 answers): the check
# blocks' token-group table (OWN_MT_TGM: groups of 3 were slow for Q6_K rows in the decode-once bench) and the
# guess-count threshold (OWN_SPEC_TAU), each SAME AS the plain run; plus one OWN_GPROF=2 run (draft + check kernel
# time per type, card 2). OPTS (env) = options passed to every run (the tg88 winners).
set -u
W=/home/steve/dsv41-work
L=/home/steve/b70-optimization-lab
D=$W/runs/tune90
mkdir -p $D
sum=$D/summary.txt
OPTS=${OPTS:-}
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib ZES_ENABLE_SYSMAN=1
J='fault response|cat error|engine reset|coredump has been created|gt reset|timedout job|exec queue reset|suspend fence|vm worker error|reset started|PCIe Bus Error|AER:|Hardware Error|Machine check'
fcheck() { local w f; w=$(journalctl -k --since "$1" -o cat); f=$(echo "$w" | grep -iE "$J"); [ -z "$f" ] && return 0
  if ! echo "$f" | grep -qvE '^\{[0-9]+\}\[Hardware Error\]' && ! echo "$w" | grep -qE 'event severity: (fatal|recoverable)'; then
    echo "WARN corrected PCIe: $(echo "$w" | grep -E 'device_id: 0000' | sort | uniq -c | tr -s ' ' | tr '\n' ';')" >> $sum; return 0; fi
  echo "$f" | head -3 | sed 's/^/FAULT: /' >> $sum; echo STOP_FAULT >> $sum; exit 1; }
SP=
touch $W/six.active
trap 'rm -f $W/six.active; [ -n "$SP" ] && kill $SP 2>/dev/null' EXIT
while [ -n "$(ls -A $W/locks 2>/dev/null)" ] || pgrep -f "own_run_v41_" > /dev/null; do sleep 10; done
echo "tune90 OPTS=$OPTS" >> $sum
G="OWN_MT_EU=6 OWN_MT_TGU=2 OWN_MT_RIDE=1 OWN_MT_RWG=128 OWN_MT_RFUSE=1 OWN_HC_FIN=1"
PL="OWN_TP=6 OWN_PROMPT_BLOCK=64 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G"
DS=/mnt/fast-ai/llm-models/DeepSeek-V4.1-Flash-1017-GGUF/dspark-DeepSeek-V4.1-Flash-1017-Q8_0.gguf
BASE="$PL OWN_SPEC=5 OWN_SPEC_KMIN=0 OWN_MT_TGR=2:4,3:4,4:4,5:4,6:4 OWN_MT_TGR_ROWS=4096 OWN_DSPARK=$DS"
TGM0="1:1,2:1,3:3,4:2,5:3,6:3"
PP=$L/experiments/own-xpu-runtime/data/dsv41-bringup-20261109/spec-prompts
r() { local name=$1 n=$2; shift 2; local t0; t0=$(date '+%Y-%m-%d %H:%M:%S')
  env $BASE $OPTS "$@" OWN_PROMPT=$PP/$n-ids.txt OWN_EOS=1 OWN_VERIFY_REF=$W/runs/e57/${n}_plain-ids.txt \
    OWN_SPEC_LOG=$D/$name-spec.txt $W/own_run_v41_tp89 - 512 $D/$name-ids.txt 4096 > $D/$name.log 2>&1
  local rc=$?
  echo "$name exit $rc" >> $sum
  grep -h "spec decode\|kept guesses\|rror\|timed out" $D/$name.log | sed "s/^/$name: /" >> $sum
  fcheck "$t0"
  [ $rc -eq 0 ] || { echo STOP_EXIT >> $sum; exit 1; }; }
for rd in 1 2; do
  for n in code analysis; do
    r ${n}_base_$rd $n OWN_MT_TGM=$TGM0 OWN_SPEC_TAU=0.5
    r ${n}_tgmA_$rd $n OWN_MT_TGM=1:1,2:1,3:1,4:2,5:1,6:2 OWN_SPEC_TAU=0.5
    r ${n}_tgmB_$rd $n OWN_MT_TGM=1:1,2:1,3:1,4:1,5:1,6:1 OWN_SPEC_TAU=0.5
  done
done
for n in code analysis; do
  for t in 0.3 0.4 0.6; do r ${n}_tau$t $n OWN_MT_TGM=$TGM0 OWN_SPEC_TAU=$t; done
done
r code_gprof code OWN_MT_TGM=$TGM0 OWN_SPEC_TAU=0.5 OWN_GPROF=2 OWN_GPROF_CARD=2
grep -A80 "kernel time per type" $D/code_gprof.log | head -60 > $D/code_gprof-kernels.txt
# checks of one token only (no guess is ever confident enough): the block path's fixed cost against a plain step
r code_k0 code OWN_MT_TGM=$TGM0 OWN_SPEC_TAU=1.01
r code_k0gprof code OWN_MT_TGM=$TGM0 OWN_SPEC_TAU=1.01 OWN_GPROF=2 OWN_GPROF_CARD=2
grep -A80 "kernel time per type" $D/code_k0gprof.log | head -70 > $D/code_k0gprof-kernels.txt
grep -c "SAME AS the plain" $sum | sed 's/^/SAME count (of 21): /' >> $sum
grep -q "DIFFERENT FROM" $sum && echo SOME_DIFFER >> $sum
echo ALLDONE >> $sum
