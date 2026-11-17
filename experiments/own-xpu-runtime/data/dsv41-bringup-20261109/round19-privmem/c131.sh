#!/bin/bash
# c131 (2026-11-17): tp131 = tp130 + rux9-1 (OWN_RUX9=1..4, opt-in: prompt IQ2_S gate + up on RoutedS9, x staged once in
# local memory) + idxfilt-3 (OWN_IDX_FILT_SEL=1, opt-in: the filtered index layers' selects over the survivors only)
# + idxfilt-4 (OWN_IDX_FILT_BC=1, opt-in: the candidate index layers 24-36 by the same pre-filter).
# 1. test_idxfilt on card 1: TopKSelF's lists / block lists / marks against the full selects on the same filtered
# scores (43 tokens at 95K / 352K / 993K) + its time; 2. identity at 3K / plain / guessing; 3. rux9 in the engine (the
# fastest form of c130's bench if it passed bitwise and was >= 15 % faster): 3K identity, guessing GLOG, 34K read A/B;
# 4. idxfilt-3: check mode at 95K (ALL SAME), 194K read A/B against the filter alone; 5. 1M read with every prompt lever
# against c129's s1m_fp; 6. 1M + guessing with everything if c130's s1m_w passed. Stable mode, preflight, first fault /
# difference = STOP.
set -u
W=/home/steve/dsv41-work; L=/home/steve/b70-optimization-lab; B=$W/own_run_v41_tp131
TS=$(date +%Y%m%dT%H%M); D=$W/runs/c131-$TS; mkdir -p $D
sum=$D/summary.txt; marks=$D/marks.txt
say() { echo "$*" >> $sum; sync -f $sum 2>/dev/null || sync; }
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib ZES_ENABLE_SYSMAN=1
g=$(cat $W/six.active 2>/dev/null); case "$g" in ""|c131) ;; *) say "STOP six.active held by $g"; exit 1;; esac
ls $W/locks/ | grep -q . && { say "STOP a lock is held: $(ls $W/locks)"; exit 1; }
echo c131 > $W/six.active; sync
pgrep -f "^/home/steve/dsv41-work/own_run_v41" > /dev/null && { say "STOP engine running"; exit 1; }
journalctl -k -f -o short-precise > $D/kernel-follow.txt 2>&1 & JF=$!
( while true; do sleep 5; sync -f $D/kernel-follow.txt $D/mem.txt $D/mem2.txt 2>/dev/null; done ) & SY=$!
( while true; do echo "$(date +%T.%N | cut -c1-10) $(awk '/MemAvailable/ {print int($2/1024)}' /proc/meminfo)"; sleep 0.5; done >> $D/mem.txt ) & MS=$!
# host detail every 0.5 s (mem2.txt): MiB of MemFree, Cached, AnonPages, Mapped, Shmem, Unevictable, Dirty, Writeback,
# PageTables, SUnreclaim; the engine's VmRSS (MiB); stall-time totals (us) from /proc/pressure: memory some/full, io
# some/full, cpu some - their growth between lines is the time tasks were held up on memory reclaim, disk or CPU
( while true; do
    e=$(pgrep -f "^/home/steve/dsv41-work/own_run_v41" | head -1)
    r=$([ -n "$e" ] && awk '/VmRSS/ {print int($2/1024)}' /proc/$e/status 2>/dev/null)
    echo "$(date +%T.%N | cut -c1-10) $(awk '/^(MemFree|Cached|AnonPages|Mapped|Shmem|Unevictable|Dirty|Writeback|PageTables|SUnreclaim):/ {printf "%s %d ", $1, $2/1024}' /proc/meminfo)rss ${r:-0} $(awk '{for (i=1;i<=NF;i++) if ($i ~ /^total=/) {sub("total=","",$i); printf "%s ", $i}}' /proc/pressure/memory /proc/pressure/io /proc/pressure/cpu)"
    sleep 0.5; done >> $D/mem2.txt ) & MS2=$!
systemd-run --user --unit=vram-c131-$TS $W/vramlog.sh $D/vram.txt 8 >/dev/null 2>&1
trap 'touch $D/vram.txt.stop; kill $JF $SY $MS $MS2 2>/dev/null; rm -f $W/six.active; sync' EXIT
source $W/stable/stable.env
say "c131 start $(date '+%F %T') source $(grep "source commit" $W/build-tp131.log | tail -1) boot $(cut -c1-8 /proc/sys/kernel/random/boot_id) binary $(sha256sum $B | cut -c1-16)"
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
  grep -h "OWN_IDX_DTOPK\|OWN_IDX_RP\|malloc_trim\|OWN_IDX_ROWS\|OWN_ROPE_WIN\|prompt:\|decode:\|spec decode\|tile 2 card.*free after load\|rror\|timed out\|exceeds\|MISMATCH\|DIFFER\|BAD:" $D/$name.log | sed "s/^/$name: /" >> $sum
  grep -h "^tpd" $D/$name.log | head -12 | cut -c1-700 | sed "s/^/$name: /" >> $sum
  say "$name exit $rc (case $n)"
  f=$(grep -iE "$J" $D/$name-kernel.txt | head -3); [ -n "$f" ] && stop "$name kernel: $f"
  [ $rc -eq 0 ] || stop "$name exit $rc"
  grep -qE "MISMATCH|DIFFERS from|DIFFERENT FROM|BAD:" $D/$name.log && stop "$name: a check line reports a difference"
  [ "$ref" = - ] && return 0
  cmp -s <(head -$rn $D/$name-ids.txt) <(head -$rn $ref) && say "$name IDS${rn}_SAME" || stop "$name IDS${rn}_DIFFER vs $ref"; }
spec() { local name=$1 pn=$2; shift 2
  run $name $PP/$pn-ids.txt 512 4096 $W/runs/e57/${pn}_plain-ids.txt 511 $PL $SPEC OWN_SPEC_TAU=0.5 $VOC OWN_SPEC_LOG=$D/$name-spec.txt OWN_VERIFY_REF=$W/runs/e57/${pn}_plain-ids.txt "$@"
  grep -q "SAME AS the plain" $D/$name.log || stop "$name: no SAME AS the plain line"
  cmp -s <(awk '{print $1,$2,$3,$4,$5,$6,$7}' $D/$name-spec.txt) <(awk '{print $1,$2,$3,$4,$5,$6,$7}' $W/runs/tg105v/${pn}_v1-spec.txt) && say "$name GLOG_SAME" || stop "$name GLOG_DIFFER"; }
# soft NAME PROMPT NTOK MAXCTX REF REFN [env...]: like run, but a non-zero exit or a difference is recorded, not a stop
# (a kernel fault line still stops everything)
soft() { local name=$1 pr=$2 nt=$3 m=$4 ref=$5 rn=$6; shift 6; local t0 rc f
  pre; memwait; n=$((n+1)); t0=$(date '+%F %T')
  echo "$name start $(date '+%T.%N' | cut -c1-12)" >> $marks; sync -f $marks
  env "$@" OWN_PROMPT=$pr OWN_EOS=-1 $B - $nt $D/$name-ids.txt $m > $D/$name.log 2>&1; rc=$?
  echo "$name end $(date '+%T.%N' | cut -c1-12) rc $rc" >> $marks; sync -f $marks
  journalctl -k --since "$t0" -o short-precise > $D/$name-kernel.txt 2>&1
  grep -h "prompt:\|decode:\|spec decode\|tile 2 card.*free after load\|rror\|fatal\|timed out\|MISMATCH\|DIFFER" $D/$name.log | cut -c1-1500 | sed "s/^/$name: /" >> $sum
  grep -h "^tpd" $D/$name.log | head -40 | cut -c1-700 | sed "s/^/$name: /" >> $sum
  say "$name exit $rc (case $n)"
  f=$(grep -iE "$J" $D/$name-kernel.txt | head -3); [ -n "$f" ] && stop "$name kernel: $f"
  [ $rc -eq 0 ] && { cmp -s <(head -$rn $D/$name-ids.txt) <(head -$rn $ref) && say "$name IDS${rn}_SAME" || say "$name IDS${rn}_DIFFER"; }
  grep -q "SAME AS the plain" $D/$name.log && say "$name SAME_AS_PLAIN" || say "$name no SAME AS the plain line"; }
nice -n 10 python3 -I $W/privmem_check.py $B 2>&1 | head -1 | sed "s/^/privmem: /" >> $sum
GS="$SPEC OWN_SPEC_TAU=0.5 $VOC OWN_KV_SHARD=1 OWN_HOST_FLOOR_MIB=1600"
E=$(grep -h "s1m_all levers:" $W/chainq118.txt 2>/dev/null | tail -1 | sed 's/.*s1m_all levers://; s/ none//')
C9=$(ls -td $W/runs/c129-*/ 2>/dev/null | head -1)summary.txt
TW=""; grep -q "^tpw identity at 3K / plain / guessing: PASS" $C9 2>/dev/null && ! grep -q "^s200k_w GLOG_DIFFER\|^s200k_w IDS1024_DIFFER" $C9 && TW="OWN_TP_WEIGHTS=30,29,29,30,29,29"
SC=0; grep -qE "source commit (a00da671bf|029e51952b|b956f44c23)" $W/build-tp131.log && [ -x $W/test_idxfilt_tp131 ] && SC=1 # idxfilt-3 in this build
BC=0; grep -qE "source commit (a00da671bf|029e51952b)" $W/build-tp131.log && [ $SC = 1 ] && BC=1 # idxfilt-4 in this build
DG=0; grep -q "source commit a00da671bf" $W/build-tp131.log && DG=1 # ifldiag-1 in this build
TY=0; grep -q "source commit a00da671bf (flags: OWN_RUX9_TY=1)" $W/build-tp131.log && grep -q "rux9 f7 bench build exit 0; sendcheck: .*PASS" $W/build-tp131.log && TY=1 # rux9-2
C0=$(ls -td $W/runs/c130-*/ 2>/dev/null | head -1)summary.txt
# rux9's engine form from c130's bench: 1 A1, 2 A1w, 3 A3, 4 B1 (the bench's names), the mean percent over its timing
# lines; only if c130's exactness step passed and the best mean is at least 15 % faster than production
RX9=$(python3 -I - "$C0" <<'PY'
import re, sys
s = open(sys.argv[1]).read().splitlines()
if not any(l.startswith('rux9 exact: exit 0, PASS') for l in s):
    print(0); sys.exit()
forms = {'S9 R2 E4/4 x0 xb2 wg1024': 1, 'S9 R2 E4/4 x0 xb2 wg1024 wpL1': 2, 'S9 R2 E4/4 x1 xb2 wg1024': 3, 'S9 R1 E8/8 x1 xb2 wg1024': 4}
acc = {}
for l in s:
    m = re.match(r'rux9 time\d: +(S9 .*?) +[0-9.]+ us .*\(\s*([-+]?[0-9.]+)%\)', l)
    if m and m.group(1).strip() in forms:
        acc.setdefault(forms[m.group(1).strip()], []).append(float(m.group(2)))
best = min(((sum(v) / len(v), k) for k, v in acc.items()), default=(0, 0))
print(best[1] if best[0] <= -15 else 0)
PY
)
say "idxfilt-3 / -4 in this build: $SC / $BC; rux9 engine form from c130's bench: ${RX9:-0} ($(grep -c '^rux9 time' $C0 2>/dev/null) timing lines; 0 = not passed / not faster)"
PYN=/home/steve/.venvs/neural-worker/bin/python3
tif() { local name=$1; shift; pre; env "$@" ONEAPI_DEVICE_SELECTOR=level_zero:1 timeout 1500 $W/test_idxfilt_tp131 > $D/$name.log 2>&1
  say "$name: $(tail -1 $D/$name.log)"; grep -E "^[12] |^selF|^bcf|^dump" $D/$name.log | cut -c1-400 | sed "s/^/$name: /" >> $sum
  tail -1 $D/$name.log | grep -q "^PASS"; }
# 1. the survivors-only selects in the bench (a difference closes the engine's idxfilt-3 cases, not the run)
if [ $SC = 1 ]; then
  tif tif_p BENCH_M=43 BENCH_LENS=95000,352000,993000 || { say "tif_p: the bench did not pass: idxfilt-3 / -4's engine cases are skipped"; SC=0; BC=0; }
  if [ $BC = 1 ]; then tif tif_c6 BENCH_M=6 BENCH_LENS=33000,166000 || { say "tif_c6: did not pass: idxfilt-4 skipped"; BC=0; }; fi
fi
# 1b. densews: the four-row dense-row forms (densews/bench_r4.cpp) on card 1: every candidate byte for byte against the
# production form, then timed beside today's picks (X16R2 / K16R2 / K16R2S); prompt halves of 256 and short ones
if grep -q "^densews bench build exit 0" $W/build-tp131.log; then
  grep "^densews isa" $W/build-tp131.log | cut -c1-220 | sed "s/^/densews /" >> $sum
  pre; t0=$(date '+%F %T')
  (cd $W/densews && timeout 2400 env LD_LIBRARY_PATH=$LD_LIBRARY_PATH ONEAPI_DEVICE_SELECTOR=level_zero:1 ZES_ENABLE_SYSMAN=1 MS=256,192,129 CH128=32,64 CH256=32,64 REPS=7 ./bin/bench_r4 > $D/densews.log 2>&1); r=$?
  f=$(journalctl -k --since "$t0" -o cat | grep -iE "$J" | head -3); [ -n "$f" ] && stop "densews bench kernel: $f"
  say "densews bench: exit $r, $(grep -c '^bitwise' $D/densews.log) bitwise, $(grep -c '^DIFFERS' $D/densews.log) DIFFERS"
  grep -h "^DIFFERS\|^bitwise.*M=256" $D/densews.log | cut -c1-200 | sed "s/^/densews: /" >> $sum
else say "densews: bench not built: $(grep '^densews' $W/build-tp131.log | head -2 | tr '\n' ' ')"; fi
# 2. identity (tp131 defaults)
run p3k $W/prompts/p3k-ids.txt 256 4096 $W/runs/e52/p3kplain-ids.txt 256 $PL $P5
run plain $P1 128 4096 $W/runs/ab1/base-speed-ids.txt 128 $PL
spec code code
spec analysis analysis
x34=$W/prompts/xl/x34k-ids.txt; R34=$W/runs/e82/x34k_plain-ids.txt
# ifldiag-1: c129 s200k_f2 (guessing 194K, OWN_IDX_FILT=2 + OWN_IDX_FILT_CK=1 from 4096) found 18 check layer-20 block
# results per card different (lists all same): the same case with OWN_IFL_DIAG=1 prints each difference (recorded, not
# a stop: the check line's MISMATCH is expected until fixed)
if [ $DG = 1 ]; then
  x200d=$W/prompts/lc/x200k-ids.txt; R200d=$W/runs/lc1-20261115T1936/x200k_def-ids.txt
  soft s200k_dg $x200d 1024 $(mx $x200d 1024) $R200d 1024 $PL $P5 $SPEC OWN_SPEC_TAU=0.5 $VOC OWN_KV_SHARD=1 OWN_HOST_FLOOR_MIB=1600 OWN_SPEC_LOG=$D/s200k_dg-spec.txt OWN_VERIFY_REF=$R200d OWN_IDX_FILT=2 OWN_IDX_FILT_MIN=8192 OWN_IDX_FILT_CK=1 OWN_IDX_FILT_CK_MIN=4096 OWN_IFL_DIAG=1
  grep -h "OWN_IDX_FILT=2 check" $D/s200k_dg.log | sed "s/^/s200k_dg: /" >> $sum
  grep -h "^IFLDIAG" $D/s200k_dg.log | head -150 | cut -c1-300 | sed "s/^/s200k_dg: /" >> $sum
fi
x95=$W/prompts/xl/x95k-ids.txt; R95=$W/runs/e82/x95k_plain-ids.txt
x200=$W/prompts/lc/x200k-ids.txt; R200=$W/runs/lc1-20261115T1936/x200k_def-ids.txt
x1m=$W/prompts/lc/x1m-ids.txt; A=$(ls -td $W/runs/ck1m-*/ | head -1)x1m_a-ids.txt
R9=""
# 3. rux9 in the engine
if [ "${RX9:-0}" != 0 ]; then
  run p3k_r9 $W/prompts/p3k-ids.txt 256 4096 $W/runs/e52/p3kplain-ids.txt 256 $PL $P5 OWN_RUX9=$RX9
  spec code_r9 code OWN_RUX9=$RX9
  run x34k_b $x34 64 $(mx $x34 64) $R34 64 $PL $P5
  run x34k_r9 $x34 64 $(mx $x34 64) $R34 64 $PL $P5 OWN_RUX9=$RX9
  R9="OWN_RUX9=$RX9"
  # rux9-2: the IQ2_XXS (bit 2) / IQ1_S (bit 4) gate + up in the bench (bitwise, then timing of the same form), each
  # type on in the engine only if bitwise and >= 15 % faster; then 3K identity and the 34K read with them
  if [ $TY = 1 ]; then
    RX=$W/rux9; RP7="env LD_LIBRARY_PATH=$LD_LIBRARY_PATH ONEAPI_DEVICE_SELECTOR=level_zero:1 ZES_ENABLE_SYSMAN=1 RUX_IDS=$W/runs/u84/p3k-ids-per-layer.txt"
    rxj() { local f; f=$(journalctl -k --since "$1" -o cat | grep -iE "$J" | head -3); [ -n "$f" ] && stop "rux9 f7 bench kernel: $f"; return 0; }
    TM=1
    for tt in xxs20:2 1s20:4; do o=${tt%%:*}; bit=${tt##*:}
      pre; t0=$(date '+%F %T'); (cd $RX && timeout 1800 $RP7 ONLY=$o CHECKM=16,64,256,512 NOTIME=1 ./bench_rux9_f7 > $D/rux9-$o-exact.log 2>&1); r=$?; rxj "$t0"
      say "rux9 $o exact: exit $r, $(tail -1 $D/rux9-$o-exact.log | cut -c1-200)"
      [ $r -eq 0 ] && tail -1 $D/rux9-$o-exact.log | grep -q "^PASS" || continue
      for k in 1 2; do t0=$(date '+%F %T'); (cd $RX && timeout 1800 $RP7 ONLY=$o RM=256 ROUNDS=3 NOCHECK=1 ./bench_rux9_f7 > $D/rux9-$o-time$k.log 2>&1); rxj "$t0"
        grep -h "%" $D/rux9-$o-time$k.log | head -20 | cut -c1-250 | sed "s/^/rux9 $o time$k: /" >> $sum; done
      ok=$(python3 -I - "$RX9" $D/rux9-$o-time1.log $D/rux9-$o-time2.log <<'PY'
import re, sys
forms = {1: 'S9 R2 E4/4 x0 xb2 wg1024', 2: 'S9 R2 E4/4 x0 xb2 wg1024 wpL1', 3: 'S9 R2 E4/4 x1 xb2 wg1024', 4: 'S9 R1 E8/8 x1 xb2 wg1024'}
want = forms.get(int(sys.argv[1]), '')
v = []
for fn in sys.argv[2:]:
    for l in open(fn, errors='replace'):
        m = re.match(r'\s+(S9 .*?) +[0-9.]+ us .*\(\s*([-+]?[0-9.]+)%\)', l)
        if m and m.group(1).strip() == want: v.append(float(m.group(2)))
print(1 if v and sum(v) / len(v) <= -15 else 0)
PY
)
      say "rux9 $o: form $RX9 mean of the timing lines >= 15 % faster: $ok"; [ "$ok" = 1 ] && TM=$((TM | bit))
    done
    if [ $TM != 1 ]; then
      run p3k_r9t $W/prompts/p3k-ids.txt 256 4096 $W/runs/e52/p3kplain-ids.txt 256 $PL $P5 OWN_RUX9=$RX9 OWN_RUX9_TY=$TM
      spec code_r9t code OWN_RUX9=$RX9 OWN_RUX9_TY=$TM
      run x34k_r9t $x34 64 $(mx $x34 64) $R34 64 $PL $P5 OWN_RUX9=$RX9 OWN_RUX9_TY=$TM
      R9="OWN_RUX9=$RX9 OWN_RUX9_TY=$TM"
    fi
    say "rux9-2 types on: OWN_RUX9_TY=$TM"
  fi
fi
# 4. idxfilt-3: the check mode from 8,192 rows (every filtered layer's lists against the unchanged path), then 194K
# read with the filter alone and with the survivors-only selects (same session)
if [ $SC = 1 ]; then
  BCE=""; [ $BC = 1 ] && BCE="OWN_IDX_FILT_BC=1"
  run x95k_f2s $x95 256 $(mx $x95 256) $R95 256 $PL $P5 OWN_IDX_FILT=2 OWN_IDX_FILT_MIN=8192 OWN_IDX_FILT_SEL=1 $BCE
  grep -h "OWN_IDX_FILT" $D/x95k_f2s.log | cut -c1-300 | sed "s/^/x95k_f2s: /" >> $sum
  grep -q "OWN_IDX_FILT=2 check: [1-9][0-9]* lists compared, 0 differ -> ALL SAME" $D/x95k_f2s.log || stop "x95k_f2s: the filter check did not end ALL SAME"
  run x200k_f $x200 64 $(mx $x200 64) $R200 64 $PL $P5 OWN_IDX_FILT=1
  run x200k_fs $x200 64 $(mx $x200 64) $R200 64 $PL $P5 OWN_IDX_FILT=1 OWN_IDX_FILT_SEL=1
  grep -h "OWN_IDX_FILT=1: card 0" $D/x200k_fs.log | cut -c1-300 | sed "s/^/x200k_fs: /" >> $sum
  SL="OWN_IDX_FILT_SEL=1"
  if [ $BC = 1 ]; then # idxfilt-4: the candidate layers too (read A/B against x200k_fs); guessing at 194K in check mode
    run x200k_fsb $x200 64 $(mx $x200 64) $R200 64 $PL $P5 OWN_IDX_FILT=1 OWN_IDX_FILT_SEL=1 OWN_IDX_FILT_BC=1
    grep -h "OWN_IDX_FILT_BC=1: card 0" $D/x200k_fsb.log | cut -c1-300 | sed "s/^/x200k_fsb: /" >> $sum
    run s200k_f2b $x200 256 $(mx $x200 256) $R200 256 $PL $P5 $GS OWN_SPEC_LOG=$D/s200k_f2b-spec.txt OWN_VERIFY_REF=$R200 OWN_IDX_FILT=2 OWN_IDX_FILT_MIN=8192 OWN_IDX_FILT_BC=1
    grep -h "OWN_IDX_FILT" $D/s200k_f2b.log | cut -c1-300 | sed "s/^/s200k_f2b: /" >> $sum
    grep -q "OWN_IDX_FILT=2 check: [1-9][0-9]* lists compared, 0 differ -> ALL SAME" $D/s200k_f2b.log || stop "s200k_f2b: the filter check did not end ALL SAME"
    grep -q "SAME AS the plain" $D/s200k_f2b.log || stop "s200k_f2b: no SAME AS the plain line"
    SL="$SL OWN_IDX_FILT_BC=1"
  fi
else SL=""; fi
# 5. 1M read, no draft, every prompt lever (c129 s1m_fp: the filter + kvshard)
soft s1m_fps $x1m 1024 $(mx $x1m 1024) $A 1024 $PL $P5 OWN_KV_SHARD=1 OWN_HOST_FLOOR_MIB=1600 OWN_IDX_FILT=1 $SL $R9
grep -h "free after load\|OWN_IDX_FILT=1: card" $D/s1m_fps.log | head -10 | cut -c1-300 | sed "s/^/s1m_fps: /" >> $sum
grep -q "^s1m_fps IDS1024_SAME" $sum || stop "s1m_fps: not identical (or did not run): see its log"
# 6. 1M + guessing with everything, if c130's s1m_w passed (same env + the two new levers)
if grep -q "^s1m_w IDS1024_SAME" $C0 2>/dev/null && grep -q "^s1m_w SAME_AS_PLAIN" $C0; then
  LV="$E OWN_IDX_FILT=1 OWN_DR_LAST=1 $TW $SL $R9" # (OWN_IDX_FILT_CK off until its block-list difference is fixed)
  soft s1m_w2 $x1m 1024 $(mx $x1m 1024) $A 1024 $PL $P5 $GS OWN_SPEC_LOG=$D/s1m_w2-spec.txt OWN_VERIFY_REF=$A $LV
  grep -h "^tpd-mem\|OWN_IDX_FILT=1: card 0\|OWN_DR_LAST" $D/s1m_w2.log | cut -c1-1500 | sed "s/^/s1m_w2: /" >> $sum
  grep -q "^s1m_w2 IDS1024_SAME" $sum && grep -q "^s1m_w2 SAME_AS_PLAIN" $sum || stop "s1m_w2: not identical (or did not run): see its log"
else say "s1m_w2 skipped: c130's s1m_w did not pass (or did not run)"; fi
say "ALLDONE $(date '+%F %T'): $n fresh starts identical to their references"
