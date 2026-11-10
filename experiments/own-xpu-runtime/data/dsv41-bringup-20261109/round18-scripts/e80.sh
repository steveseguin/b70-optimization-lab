#!/bin/bash
# tp66 kernel-time profiles (OWN_GPROF=2): (1) the guessing cycle (code prompt, 512 tokens) on cards 0, 2, 5 with
# the whole-group layout; (2) the 3K read in blocks of 16 with OWN_TP_HEADS=3,3,3,3,2,2 on cards 0, 2, 4, 5.
# Waits for e79 (exits if it stopped). Profiles are not speed measurements. Stops at the first fault line.
set -u
S=/tmp/claude-1000/-home-steve/6f61a0f6-fd06-49a3-b5b4-babc9645cc37/scratchpad
until grep -q "ALLDONE\|STOP" $S/runs/e79/summary.txt 2>/dev/null; do sleep 10; done
grep -q STOP $S/runs/e79/summary.txt && exit 1
while systemctl --user is-active --quiet dsv41-e79; do sleep 2; done
D=$S/runs/e80
mkdir -p $D
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib ZES_ENABLE_SYSMAN=1
sum=$D/summary.txt
J='fault response|cat error|engine reset|coredump has been created|gt reset|timedout job|exec queue reset|suspend fence|vm worker error|reset started'
G="OWN_MT_EU=6 OWN_MT_TGU=2 OWN_MT_RIDE=1 OWN_MT_RWG=128 OWN_MT_RFUSE=1 OWN_HC_FIN=1"
PL="OWN_TP=6 OWN_PROMPT_BLOCK=16 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G"
PP=/home/steve/b70-optimization-lab/experiments/own-xpu-runtime/data/dsv41-bringup-20261109/spec-prompts
R57=$S/runs/e57
DS=/mnt/fast-ai/llm-models/DeepSeek-V4.1-Flash-1017-GGUF/dspark-DeepSeek-V4.1-Flash-1017-Q8_0.gguf
BEST="$PL OWN_MT_TGM=1:1,2:1,3:3,4:2,5:3,6:3 OWN_SPEC=5 OWN_SPEC_TAU=0.5 OWN_SPEC_KMIN=0 OWN_MT_TGR=2:4,3:4,4:4,5:4,6:4 OWN_MT_TGR_ROWS=4096"
bin=$S/own_run_v41_tp66
P3=$S/prompts/p3k-ids.txt
chk() { local t0=$1 n=$2; echo "$n exit $3" >> $sum
  local f; f=$(journalctl -k --since "$t0" -o cat | grep -iE "$J" | head -3)
  if [ -n "$f" ] || [ $3 -ne 0 ]; then echo "$f" | sed 's/^/FAULT: /' >> $sum; echo STOP_FAULT >> $sum; exit 1; fi; }
for cd in 0 2 5; do
  t0=$(date '+%Y-%m-%d %H:%M:%S')
  env $BEST OWN_GPROF=2 OWN_GPROF_CARD=$cd OWN_PROMPT=$PP/code-ids.txt OWN_EOS=1 OWN_VERIFY_REF=$R57/code_plain-ids.txt \
    OWN_DSPARK=$DS $bin - 512 $D/spec$cd-ids.txt 4096 > $D/spec$cd.log 2>&1
  chk "$t0" spec$cd $?
done
for cd in 0 2 4 5; do
  t0=$(date '+%Y-%m-%d %H:%M:%S')
  env $PL OWN_TP_HEADS=3,3,3,3,2,2 OWN_GPROF=2 OWN_GPROF_CARD=$cd OWN_PROMPT=$P3 OWN_EOS=-1 $bin - 2 $D/proa$cd-ids.txt 4096 \
    > $D/proa$cd.log 2>&1
  chk "$t0" proa$cd $?
done
echo ALLDONE >> $sum
