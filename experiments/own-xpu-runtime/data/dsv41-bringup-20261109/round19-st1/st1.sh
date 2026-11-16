#!/bin/bash
# st1 (2026-11-15): bounded 1-2 h stability test in the current diagnostic configuration (Codex's suggestion, owner
# relayed 16:4x: "please continue optimizing/etc"): SMT disabled (BIOS), Gen4 x16 root links, OWN_PX_SERIAL=1, normal
# power, BIOS 11.02 - all checked by stable/preflight.sh before every case, never changed here. Existing tp115 binary.
# Fresh model start per case; both prompt head layouts (def = 3,3,3,3,2,2; H1 = 4,2,2,4,2,2 for blocks >= 16
# tokens, the layout of the 10:32 reset's first run); prompts of 36 / 82-113 / 3,323 / 10,621 / 33,815 / 95,497 tokens;
# plain and guessing answers. Every output checked against its reference. FIRST fault, mismatch, non-zero exit or
# failed preflight = STOP: no more launches, evidence kept, no retry / reset / reboot. Logs synced to disk after
# every line (a hard reset loses unsynced page cache: sm1's summary was lost at 10:32). Doubles as the def vs H1
# speed A/B (each cycle alternates; speeds are diagnostic, stable-mode only).
set -u
W=/home/steve/dsv41-work; L=/home/steve/b70-optimization-lab
TS=$(date +%Y%m%dT%H%M); D=$W/runs/st1-smtoff-$TS; mkdir -p $D
sum=$D/summary.txt; marks=$D/marks.txt
say() { echo "$*" >> $sum; sync -f $sum 2>/dev/null || sync; }
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib ZES_ENABLE_SYSMAN=1
g=$(cat $W/six.active 2>/dev/null); case "$g" in ""|smt-off-remaining11-20261115T1534|st1) ;; *) say "STOP six.active held by $g"; exit 1;; esac
echo st1 > $W/six.active; sync
pgrep -f "^/home/steve/dsv41-work/own_run_v41" > /dev/null && { say "STOP engine running"; exit 1; }
# continuous kernel log + periodic sync (light: one journalctl follower, one sync every 5 s)
journalctl -k -f -o short-precise > $D/kernel-follow.txt 2>&1 & JF=$!
( while true; do sleep 5; sync -f $D/kernel-follow.txt 2>/dev/null; done ) & SY=$!
trap 'kill $JF $SY 2>/dev/null; rm -f $W/six.active; sync' EXIT
source $W/stable/stable.env
say "st1 start $(date '+%F %T') boot $(cut -c1-8 /proc/sys/kernel/random/boot_id) binary $(sha256sum $W/own_run_v41_tp115 | cut -c1-16)"
say "smt active $(cat /sys/devices/system/cpu/smt/active), cpus $(nproc), bios $(cat /sys/class/dmi/id/bios_version)"
J='fault response|cat error|engine reset|coredump has been created|gt reset|timedout job|exec queue reset|suspend fence|vm worker error|reset started|PCIe Bus Error|AER:|Hardware Error|Machine check|watchdog: BUG|rcu_sched self-detected|AMD-Vi: Event'
stop() { say "STOP $*"; say "STOPPED $(date '+%F %T')"; exit 1; }
pre() { local o; o=$($W/stable/preflight.sh 2>&1) || stop "preflight: $o"; }
G="OWN_MT_EU=6 OWN_MT_TGU=2 OWN_MT_RIDE=1 OWN_MT_RWG=128 OWN_MT_RFUSE=1 OWN_HC_FIN=1"
PL="OWN_TP=6 OWN_PROMPT_BLOCK=64 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G"
P5="OWN_PROMPT_BLOCK=512 OWN_PX=1 OWN_PX_BIG=1"
H1="OWN_TP_HEADS=4,2,2,4,2,2 OWN_TP_HEADS_MIN=16"
VOC="OWN_DR_VOCAB=$W/draft/vocab/cand-c32k-dict.txt OWN_DR_VOCAB_N=60000"
DSP=/mnt/fast-ai/llm-models/DeepSeek-V4.1-Flash-1017-GGUF/dspark-DeepSeek-V4.1-Flash-1017-Q8_0.gguf
SPEC="OWN_MT_TGM=1:1,2:1,3:3,4:2,5:3,6:3 OWN_SPEC=5 OWN_SPEC_KMIN=0 OWN_MT_TGR=2:4,3:4,4:4,5:4,6:4 OWN_MT_TGR_ROWS=4096 OWN_DSPARK=$DSP"
PP=$L/experiments/own-xpu-runtime/data/dsv41-bringup-20261109/spec-prompts
P1=$L/experiments/own-xpu-runtime/data/dsv41-bringup-20261109/prompt1-ids.txt
memwait() { local i=0; until [ $(awk '/MemAvailable/ {print int($2/1048576)}' /proc/meminfo) -ge 7 ] || [ $i -ge 120 ]; do sleep 5; i=$((i+1)); done; }
n=0
# run NAME PROMPT NTOK MAXCTX EOS REF REFN [env...]: one fresh start, then every check; any failure stops
run() { local name=$1 pr=$2 nt=$3 mx=$4 eos=$5 ref=$6 rn=$7; shift 7; local t0 rc f
  pre; memwait; n=$((n+1)); t0=$(date '+%F %T')
  echo "$name start $(date '+%T.%N' | cut -c1-12)" >> $marks; sync -f $marks
  env "$@" OWN_PROMPT=$pr OWN_EOS=$eos $W/own_run_v41_tp115 - $nt $D/$name-ids.txt $mx > $D/$name.log 2>&1; rc=$?
  echo "$name end $(date '+%T.%N' | cut -c1-12) rc $rc" >> $marks; sync -f $marks
  journalctl -k --since "$t0" -o short-precise > $D/$name-kernel.txt 2>&1
  grep -h "prompt:\|decode:\|spec decode\|rror\|timed out\|exceeds\|MISMATCH\|DIFFER\|BAD:" $D/$name.log | sed "s/^/$name: /" >> $sum
  say "$name exit $rc (case $n)"
  f=$(grep -iE "$J" $D/$name-kernel.txt | head -3); [ -n "$f" ] && stop "$name kernel: $f"
  [ $rc -eq 0 ] || stop "$name exit $rc"
  grep -qE "MISMATCH|DIFFERS from|DIFFERENT FROM|BAD:" $D/$name.log && stop "$name: a check line reports a difference"
  cmp -s <(head -$rn $D/$name-ids.txt) <(head -$rn $ref) && say "$name IDS${rn}_SAME" || stop "$name IDS${rn}_DIFFER vs $ref"; }
spec() { local name=$1 pn=$2; shift 2
  run $name $PP/$pn-ids.txt 512 4096 1 $W/runs/e57/${pn}_plain-ids.txt 511 $PL $SPEC OWN_SPEC_TAU=0.5 $VOC OWN_SPEC_LOG=$D/$name-spec.txt OWN_VERIFY_REF=$W/runs/e57/${pn}_plain-ids.txt "$@"
  grep -q "SAME AS the plain" $D/$name.log || stop "$name: no SAME AS the plain line"
  cmp -s <(awk '{print $1,$2,$3,$4,$5,$6,$7}' $D/$name-spec.txt) <(awk '{print $1,$2,$3,$4,$5,$6,$7}' $W/runs/tg105v/${pn}_v1-spec.txt) && say "$name GLOG_SAME" || stop "$name GLOG_DIFFER"; }
T0=$(date +%s); LIMIT=$((105*60))
p3=$W/prompts/p3k-ids.txt; p10=$W/prompts/p10k-ids.txt; x34=$W/prompts/xl/x34k-ids.txt; x95=$W/prompts/xl/x95k-ids.txt
m34=$(( ( $(wc -l < $x34) + 256 + 1023 ) / 1024 * 1024 )); m95=$(( ( $(wc -l < $x95) + 256 + 1023 ) / 1024 * 1024 ))
for cy in 1 2 3 4 5 6 7 8 9; do
  [ $(( $(date +%s) - T0 )) -ge $LIMIT ] && break
  say "cycle $cy $(date +%T)"
  if [ $((cy % 2)) = 1 ]; then A=def; B=h1; AE=""; BE="$H1"; else A=h1; B=def; AE="$H1"; BE=""; fi
  run c${cy}_p3k_$A $p3 256 4096 -1 $W/runs/e52/p3kplain-ids.txt 256 $PL $P5 $AE
  run c${cy}_p3k_$B $p3 256 4096 -1 $W/runs/e52/p3kplain-ids.txt 256 $PL $P5 $BE
  run c${cy}_p10k_$B $p10 64 16384 -1 $W/runs/tg107/p10k_bcs-ids.txt 64 $PL $P5 $BE
  run c${cy}_p10k_$A $p10 64 16384 -1 $W/runs/tg107/p10k_bcs-ids.txt 64 $PL $P5 $AE
  run c${cy}_x34k_$A $x34 256 $m34 -1 $W/runs/e82/x34k_plain-ids.txt 256 $PL $P5 $AE
  run c${cy}_x34k_$B $x34 256 $m34 -1 $W/runs/e82/x34k_plain-ids.txt 256 $PL $P5 $BE
  spec c${cy}_code_$A code $AE
  spec c${cy}_analysis_$B analysis $BE
  run c${cy}_plain_$A $P1 128 4096 -1 $W/runs/ab1/base-speed-ids.txt 128 $PL $AE
  [ $(( $(date +%s) - T0 )) -ge $LIMIT ] && break
  run c${cy}_x95k_$A $x95 256 $m95 -1 $W/runs/e82/x95k_plain-ids.txt 256 $PL $P5 $AE
done
say "ALLDONE $(date '+%F %T'): $n fresh starts, all exits 0, every output the same as its reference, no fault line"
