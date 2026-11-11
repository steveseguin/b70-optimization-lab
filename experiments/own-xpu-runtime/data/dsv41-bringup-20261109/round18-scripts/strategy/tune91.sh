#!/bin/bash
# tune91 (after tg91, tp91 binary): the attention-head split for CHECKS. Cards 2 / 5 carry 16 heads, the other four
# 8; in tg90's check timeline the heavy cards' non-exchange work exceeds the light cards' by ~0.6 ms at one token and
# ~0.33 ms per extra token (1.9 ms in a check of 5), and the light cards wait that out in the exchanges. Prompt blocks
# of >= 16 tokens already split the doubled groups between card pairs (OWN_TP_HEADS 3,3,3,3,2,2, OWN_TP_HEADS_MIN=16,
# XchgPair; bit-identical). Here: the split from 2 / 3 / 4 tokens on (checks), also for the draft's stages
# (OWN_TP_HEADS_DR=1). Each: SAME AS the plain answers, guess logs equal to the default run's, rounds per second.
set -u
W=/home/steve/dsv41-work
L=/home/steve/b70-optimization-lab
D=$W/runs/tune91
mkdir -p $D
sum=$D/summary.txt
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib ZES_ENABLE_SYSMAN=1
J='fault response|cat error|engine reset|coredump has been created|gt reset|timedout job|exec queue reset|suspend fence|vm worker error|reset started|PCIe Bus Error|AER:|Hardware Error|Machine check'
fcheck() { local w f; w=$(journalctl -k --since "$1" -o cat); f=$(echo "$w" | grep -iE "$J"); [ -z "$f" ] && return 0
  if ! echo "$f" | grep -qvE '^\{[0-9]+\}\[Hardware Error\]' && ! echo "$w" | grep -qE 'event severity: (fatal|recoverable)'; then
    echo "WARN corrected PCIe: $(echo "$w" | grep -E 'device_id: 0000' | sort | uniq -c | tr -s ' ' | tr '\n' ';')" >> $sum; return 0; fi
  echo "$f" | head -3 | sed 's/^/FAULT: /' >> $sum; echo STOP_FAULT >> $sum; exit 1; }
until grep -qE "ALLDONE|STOP" $W/runs/tg91/summary.txt 2>/dev/null; do sleep 20; done
grep -q ALLDONE $W/runs/tg91/summary.txt || { echo "STOP tg91 did not finish" >> $sum; exit 1; }
SP=
until [ ! -e $W/six.active ]; do sleep 5; done
touch $W/six.active
trap 'rm -f $W/six.active' EXIT
while [ -n "$(ls -A $W/locks 2>/dev/null)" ] || pgrep -f "^/home/steve/dsv41-work/own_run_v41" > /dev/null; do sleep 10; done
G="OWN_MT_EU=6 OWN_MT_TGU=2 OWN_MT_RIDE=1 OWN_MT_RWG=128 OWN_MT_RFUSE=1 OWN_HC_FIN=1"
PL="OWN_TP=6 OWN_PROMPT_BLOCK=64 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G"
DSP=/mnt/fast-ai/llm-models/DeepSeek-V4.1-Flash-1017-GGUF/dspark-DeepSeek-V4.1-Flash-1017-Q8_0.gguf
SPEC="OWN_MT_TGM=1:1,2:1,3:3,4:2,5:3,6:3 OWN_SPEC=5 OWN_SPEC_KMIN=0 OWN_MT_TGR=2:4,3:4,4:4,5:4,6:4 OWN_MT_TGR_ROWS=4096 OWN_DSPARK=$DSP"
BEST="$PL $SPEC OWN_SPEC_TAU=0.5 ${OPTS:-}"
PP=$L/experiments/own-xpu-runtime/data/dsv41-bringup-20261109/spec-prompts
glog() { cmp -s <(awk '{print $1,$2,$3,$4,$5,$6,$7}' $1) <(awk '{print $1,$2,$3,$4,$5,$6,$7}' $2) && echo "$3 GLOG_SAME" >> $sum || echo "$3 GLOG_DIFFER" >> $sum; }
r() { local name=$1 n=$2; shift 2; local t0; t0=$(date '+%Y-%m-%d %H:%M:%S')
  env $BEST "$@" OWN_PROMPT=$PP/$n-ids.txt OWN_EOS=1 OWN_VERIFY_REF=$W/runs/e57/${n}_plain-ids.txt \
    OWN_SPEC_LOG=$D/$name-spec.txt $W/own_run_v41_tp91 - 512 $D/$name-ids.txt 4096 > $D/$name.log 2>&1
  local rc=$?
  echo "$name exit $rc" >> $sum
  grep -h "spec decode\|heads per card\|rror\|timed out" $D/$name.log | sed "s/^/$name: /" >> $sum
  fcheck "$t0"
  [ $rc -eq 0 ] || { echo STOP_EXIT >> $sum; exit 1; }; }
echo "tune91 OPTS=${OPTS:-}" >> $sum
for rd in 1 2; do
  for n in code analysis; do
    r ${n}_d_$rd $n
    r ${n}_hm2_$rd $n OWN_TP_HEADS_MIN=2;  glog $D/${n}_hm2_$rd-spec.txt $D/${n}_d_$rd-spec.txt ${n}_hm2_$rd
    r ${n}_hm4_$rd $n OWN_TP_HEADS_MIN=4;  glog $D/${n}_hm4_$rd-spec.txt $D/${n}_d_$rd-spec.txt ${n}_hm4_$rd
  done
done
for n in code analysis; do
  r ${n}_hm3 $n OWN_TP_HEADS_MIN=3;                   glog $D/${n}_hm3-spec.txt $D/${n}_d_1-spec.txt ${n}_hm3
  r ${n}_hm2dr $n OWN_TP_HEADS_MIN=2 OWN_TP_HEADS_DR=1; glog $D/${n}_hm2dr-spec.txt $D/${n}_d_1-spec.txt ${n}_hm2dr
done
grep -c "SAME AS the plain" $sum | sed 's/^/SAME count (of 16): /' >> $sum
grep -q "DIFFERENT FROM\|GLOG_DIFFER" $sum && echo SOME_DIFFER >> $sum
echo ALLDONE >> $sum
