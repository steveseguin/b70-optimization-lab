#!/bin/bash
# pr2 (2026-11-16): bisect of c117's s200k failure (pr1: the tp115 binary fails the same way - stuck 12 h in its
# destructor after the fault, GPU idle - so it predates tp116/117). Was: pr1 probe (guessing at 194,000 tokens, tp117: "card 0: card-to-card exchange
# timed out waiting for card 1" ~2 min after load; no kernel fault line, host memory steady). Which change: (c) the
# tp115 binary, same case; (b) tp117 with OWN_ROPE_WIN=0 OWN_IDX_ROWS=0 (tp115's layout); (a) tp117 guessing at
# 95,497 tokens (tp115 passed this as c115 s95). A non-zero exit is recorded and the next probe runs (a software
# fault probe); a kernel fault line still stops everything. Diagnostic configuration, preflight, synced logs.
set -u
W=/home/steve/dsv41-work; L=/home/steve/b70-optimization-lab; B=$W/own_run_v41_tp117
TS=$(date +%Y%m%dT%H%M); D=$W/runs/pr2-$TS; mkdir -p $D
sum=$D/summary.txt; marks=$D/marks.txt
say() { echo "$*" >> $sum; sync -f $sum 2>/dev/null || sync; }
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib ZES_ENABLE_SYSMAN=1
g=$(cat $W/six.active 2>/dev/null); case "$g" in ""|pr2) ;; *) say "STOP six.active held by $g"; exit 1;; esac
ls $W/locks/ | grep -q . && { say "STOP a lock is held: $(ls $W/locks)"; exit 1; }
echo pr2 > $W/six.active; sync
pgrep -f "^/home/steve/dsv41-work/own_run_v41" > /dev/null && { say "STOP engine running"; exit 1; }
journalctl -k -f -o short-precise > $D/kernel-follow.txt 2>&1 & JF=$!
( while true; do sleep 5; sync -f $D/kernel-follow.txt $D/mem.txt 2>/dev/null; done ) & SY=$!
( while true; do echo "$(date +%T.%N | cut -c1-10) $(awk '/MemAvailable/ {print int($2/1024)}' /proc/meminfo)"; sleep 0.5; done >> $D/mem.txt ) & MS=$!
trap 'kill $JF $SY $MS 2>/dev/null; rm -f $W/six.active; sync' EXIT
source $W/stable/stable.env
say "pr2 start $(date '+%F %T') boot $(cut -c1-8 /proc/sys/kernel/random/boot_id) binary $(sha256sum $B | cut -c1-16)"
say "smt active $(cat /sys/devices/system/cpu/smt/active), cpus $(nproc), bios $(cat /sys/class/dmi/id/bios_version)"
J='fault response|cat error|engine reset|coredump has been created|gt reset|timedout job|exec queue reset|suspend fence|vm worker error|reset started|PCIe Bus Error|AER:|Hardware Error|Machine check|watchdog: BUG|rcu_sched self-detected|AMD-Vi: Event|wedged|inaccessible|GuC'
stop() { say "STOP $*"; say "STOPPED $(date '+%F %T')"; exit 1; }
pre() { local o; o=$($W/stable/preflight.sh 2>&1) || stop "preflight: $o"; }
G="OWN_MT_EU=6 OWN_MT_TGU=2 OWN_MT_RIDE=1 OWN_MT_RWG=128 OWN_MT_RFUSE=1 OWN_HC_FIN=1"
PL="OWN_TP=6 OWN_PROMPT_BLOCK=64 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G OWN_HOST_FLOOR_MIB=2560"
P5="OWN_PROMPT_BLOCK=512 OWN_PX=1 OWN_PX_BIG=1"
VOC="OWN_DR_VOCAB=$W/draft/vocab/cand-c32k-dict.txt OWN_DR_VOCAB_N=60000"
DSP=/mnt/fast-ai/llm-models/DeepSeek-V4.1-Flash-1017-GGUF/dspark-DeepSeek-V4.1-Flash-1017-Q8_0.gguf
SPEC="OWN_MT_TGM=1:1,2:1,3:3,4:2,5:3,6:3 OWN_SPEC=5 OWN_SPEC_KMIN=0 OWN_MT_TGR=2:4,3:4,4:4,5:4,6:4 OWN_MT_TGR_ROWS=4096 OWN_DSPARK=$DSP"
PP=$L/experiments/own-xpu-runtime/data/dsv41-bringup-20261109/spec-prompts
P1=$L/experiments/own-xpu-runtime/data/dsv41-bringup-20261109/prompt1-ids.txt
memwait() { local i=0; until [ $(awk '/MemAvailable/ {print int($2/1048576)}' /proc/meminfo) -ge 7 ] || [ $i -ge 120 ]; do sleep 5; i=$((i+1)); done; }
mx() { echo $(( ( $(wc -l < $1) + $2 + 1023 ) / 1024 * 1024 )); }
n=0
# run NAME PROMPT NTOK MAXCTX REF REFN [env...] (REF "-": no reference compare here)
run() { local name=$1 pr=$2 nt=$3 m=$4 ref=$5 rn=$6; shift 6; local t0 rc f
  pre; memwait; n=$((n+1)); t0=$(date '+%F %T')
  echo "$name start $(date '+%T.%N' | cut -c1-12)" >> $marks; sync -f $marks
  env "$@" OWN_PROMPT=$pr OWN_EOS=-1 $B - $nt $D/$name-ids.txt $m > $D/$name.log 2>&1; rc=$?
  echo "$name end $(date '+%T.%N' | cut -c1-12) rc $rc" >> $marks; sync -f $marks
  journalctl -k --since "$t0" -o short-precise > $D/$name-kernel.txt 2>&1
  grep -h "OWN_IDX_ROWS\|OWN_ROPE_WIN\|prompt:\|decode:\|spec decode\|tile 2 card.*free after load\|rror\|timed out\|exceeds\|MISMATCH\|DIFFER\|BAD:" $D/$name.log | sed "s/^/$name: /" >> $sum
  say "$name exit $rc (case $n)"
  f=$(grep -iE "$J" $D/$name-kernel.txt | head -3); [ -n "$f" ] && stop "$name kernel: $f"
  [ $rc -eq 0 ] || stop "$name exit $rc"
  grep -qE "MISMATCH|DIFFERS from|DIFFERENT FROM|BAD:" $D/$name.log && stop "$name: a check line reports a difference"
  [ "$ref" = - ] && return 0
  cmp -s <(head -$rn $D/$name-ids.txt) <(head -$rn $ref) && say "$name IDS${rn}_SAME" || stop "$name IDS${rn}_DIFFER vs $ref"; }
# soft NAME BINARY PROMPT NTOK REF [env...]: one fresh start; exit code and the reference compare recorded, no stop
soft() { local name=$1 bin=$2 pr=$3 nt=$4 ref=$5; shift 5; local t0 rc f m
  pre; memwait; n=$((n+1)); t0=$(date '+%F %T'); m=$(mx $pr 1024)
  echo "$name start $(date '+%T.%N' | cut -c1-12)" >> $marks; sync -f $marks
  [ -n "${MXO:-}" ] && m=$MXO
  env "$@" OWN_PROMPT=$pr OWN_EOS=-1 $bin - $nt $D/$name-ids.txt $m > $D/$name.log 2>&1 & local ep=$! ts=$(date +%s)
  # watchdog: past DL seconds, if the six cards' busy counters stand still for 5 s (a host-side hang, as pr1's
  # tp115 in its destructor), keep backtraces and stop it (never while a card is busy: no kill mid-spin)
  while kill -0 $ep 2>/dev/null; do sleep 5
    if [ $(( $(date +%s) - ts )) -ge ${DL:-660} ]; then
      local a b; a=$(cat /proc/$ep/fdinfo/* 2>/dev/null | awk '/drm-cycles-(ccs|bcs)/ {s+=$2} END {print s+0}'); sleep 5
      b=$(cat /proc/$ep/fdinfo/* 2>/dev/null | awk '/drm-cycles-(ccs|bcs)/ {s+=$2} END {print s+0}')
      if [ "$a" = "$b" ]; then say "$name HUNG past ${DL:-660} s with the cards idle: backtraces, then TERM"
        timeout 120 gdb -p $ep -batch -ex "thread apply all bt 25" > $D/$name-gdb.txt 2>&1; kill -TERM $ep; fi
    fi; done
  wait $ep; rc=$?
  echo "$name end $(date '+%T.%N' | cut -c1-12) rc $rc" >> $marks; sync -f $marks
  journalctl -k --since "$t0" -o short-precise > $D/$name-kernel.txt 2>&1
  grep -h "prompt:\|decode:\|spec decode\|tile 2 card.*free after load\|rror\|fatal\|timed out\|MISMATCH\|DIFFER" $D/$name.log | sed "s/^/$name: /" >> $sum
  say "$name exit $rc (case $n)"
  f=$(grep -iE "$J" $D/$name-kernel.txt | head -3); [ -n "$f" ] && stop "$name kernel: $f"
  [ $rc -eq 0 ] && { cmp -s <(head -$nt $D/$name-ids.txt) <(head -$nt $ref) && say "$name IDS${nt}_SAME" || say "$name IDS${nt}_DIFFER"; }; }
x200=$W/prompts/lc/x200k-ids.txt; R2=$W/runs/lc1-20261115T1936/x200k_def-ids.txt
x95=$W/prompts/xl/x95k-ids.txt; R9=$W/runs/e82/x95k_plain-ids.txt
GS="$SPEC OWN_SPEC_TAU=0.5 $VOC"
TG="OWN_MT_TGM=1:1,2:1,3:3,4:2,5:3,6:3 OWN_MT_TGR=2:4,3:4,4:4,5:4,6:4 OWN_MT_TGR_ROWS=4096"
# (1) full guessing, the 95,497-token prompt (passes at max 96,768) with room for 195,584 positions
MXO=195584 soft g_s95big $B $x95 64 $R9 $PL $P5 $GS OWN_SPEC_LOG=$D/g_s95big-spec.txt OWN_VERIFY_REF=$R9
# (2) the draft alone at 194K (guessing without the TGM/TGR kernel shapes and the vocabulary)
soft g_draft $B $x200 64 $R2 $PL $P5 OWN_SPEC=5 OWN_SPEC_KMIN=0 OWN_DSPARK=$DSP OWN_SPEC_TAU=0.5 OWN_SPEC_LOG=$D/g_draft-spec.txt OWN_VERIFY_REF=$R2
# (3) the guessing kernel shapes alone at 194K (plain answers)
soft g_tg $B $x200 64 $R2 $PL $P5 $TG
say "ALLDONE $(date '+%F %T'): $n probes"
