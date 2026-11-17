#!/bin/bash
# c132 (2026-11-17): tp132 = tp131 + pb-2 (opt-in) + obpad-1 (OWN_OB_PAD, opt-in: the block's head rows qh * hd + pad
# floats apart per token, not 128 KiB) + ifldiag-1c. 1. obpad bench on card 1 (output-a at the 128 KiB and padded
# strides, bitwise + time; the pad = the fastest padded stride if >= 5 % faster than 32,768 at 256 tokens); 2. identity
# (tp132 defaults, then with the pad: 3K, plain, guessing GLOG); 3. read A/B without / with the pad at 34K and 95K (the
# prompt levers c131 proved); 4. the filter diagnostic s200k_dg2 (194K guessing, OWN_IDX_FILT_CK=1, OWN_IFL_DIAG=1;
# soft); 5. 1M read with every lever + the pad against c131's s1m_fps. Stable mode, preflight, first fault /
# difference = STOP.
set -u
W=/home/steve/dsv41-work; L=/home/steve/b70-optimization-lab; B=$W/own_run_v41_tp132
TS=$(date +%Y%m%dT%H%M); D=$W/runs/c132-$TS; mkdir -p $D
sum=$D/summary.txt; marks=$D/marks.txt
say() { echo "$*" >> $sum; sync -f $sum 2>/dev/null || sync; }
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib ZES_ENABLE_SYSMAN=1
g=$(cat $W/six.active 2>/dev/null); case "$g" in ""|c132) ;; *) say "STOP six.active held by $g"; exit 1;; esac
ls $W/locks/ | grep -q . && { say "STOP a lock is held: $(ls $W/locks)"; exit 1; }
echo c132 > $W/six.active; sync
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
systemd-run --user --unit=vram-c132-$TS $W/vramlog.sh $D/vram.txt 8 >/dev/null 2>&1
trap 'touch $D/vram.txt.stop; kill $JF $SY $MS $MS2 2>/dev/null; rm -f $W/six.active; sync' EXIT
source $W/stable/stable.env
say "c132 start $(date '+%F %T') source $(grep "source commit" $W/build-tp132.log | tail -1) boot $(cut -c1-8 /proc/sys/kernel/random/boot_id) binary $(sha256sum $B | cut -c1-16)"
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
C1=$(ls -td $W/runs/c131-*/ 2>/dev/null | head -1)summary.txt
x34=$W/prompts/xl/x34k-ids.txt; R34=$W/runs/e82/x34k_plain-ids.txt
x95=$W/prompts/xl/x95k-ids.txt; R95=$W/runs/e82/x95k_plain-ids.txt
x200=$W/prompts/lc/x200k-ids.txt; R200=$W/runs/lc1-20261115T1936/x200k_def-ids.txt
x1m=$W/prompts/lc/x1m-ids.txt; A=$(ls -td $W/runs/ck1m-*/ | head -1)x1m_a-ids.txt
# c131's proven prompt levers: the filter (+ survivors-only selects + candidate layers if c131's 1M read passed with them)
SL=""; grep -q "^s1m_fps IDS1024_SAME" $C1 2>/dev/null && grep -q "^x200k_fsb IDS64_SAME" $C1 && SL="OWN_IDX_FILT_SEL=1 OWN_IDX_FILT_BC=1"
LP="OWN_IDX_FILT=1 $SL"
GS="$SPEC OWN_SPEC_TAU=0.5 $VOC OWN_KV_SHARD=1 OWN_HOST_FLOOR_MIB=1600"
say "prompt levers from c131: $LP"
# 1. obpad bench
OB=0
if grep -q "^obpad bench build exit 0" $W/build-tp132.log; then
  pre; t0=$(date '+%F %T')
  (cd $W/densews && timeout 1500 env LD_LIBRARY_PATH=$LD_LIBRARY_PATH ONEAPI_DEVICE_SELECTOR=level_zero:1 ZES_ENABLE_SYSMAN=1 ONLY=o_a,o_b MS=256,192,129 CH128=32,64 CH256=32,64 REPS=7 ./bin/bench_obpad > $D/obpad.log 2>&1); r=$?
  f=$(journalctl -k --since "$t0" -o cat | grep -iE "$J" | head -3); [ -n "$f" ] && stop "obpad bench kernel: $f"
  say "obpad bench: exit $r, $(grep -c '^bitwise' $D/obpad.log) bitwise, $(grep -c '^DIFFERS' $D/obpad.log) DIFFERS"
  OB=$(python3 -I - $D/obpad.log 2>>$sum <<'PY'
import re, sys, collections
best = collections.defaultdict(lambda: 1e9) # (fmt, rows, xs, M) -> best T16 R2 time
bad = False
for l in open(sys.argv[1], errors='replace'):
    if l.startswith('DIFFERS'): bad = True
    m = re.match(r'bitwise (q[68]) (o_[ab]) (\d+)x(\d+)(?: xs(\d+))? +M=(\d+) +.+? +[0-9.]+ us \| (T16 R2.*?) +([0-9.]+) us', l)
    if m:
        f, w, rows, cols, xs, M, _, t = m.groups()
        if w == 'o_b': rows = 'b' + rows
        k = (f, rows, int(xs or cols), int(M)); best[k] = min(best[k], float(t))
for xs in (8208, 8256): # output-b (information: obpad-1 pads output-a's x only)
    for M in (256, 129):
        print('obpad o_b xs %d at %d tokens: q8 %.1f / q6 %.1f us vs 8192: q8 %.1f / q6 %.1f us' % (xs, M, best[('q8', 'b864', xs, M)], best[('q6', 'b864', xs, M)], best[('q8', 'b864', 8192, M)], best[('q6', 'b864', 8192, M)]), file=sys.stderr)
out = []
for xs in (32784, 32832, 33024):
    a = [best[(f, '1024', 32768, 256)] for f in ('q8', 'q6')]; b = [best[(f, '1024', xs, 256)] for f in ('q8', 'q6')]
    if max(a + b) < 1e9: out.append((sum(b) / sum(a), xs))
    print('obpad xs %d at 256 tokens: q8 %.1f / q6 %.1f us vs 32768: q8 %.1f / q6 %.1f us' % (xs, b[0], b[1], a[0], a[1]), file=sys.stderr)
r, xs = min(out) if out else (1, 32768)
print(xs - 32768 if not bad and r <= 0.95 else 0)
PY
)
  grep -h "^DIFFERS" $D/obpad.log | head -5 | cut -c1-200 | sed "s/^/obpad: /" >> $sum
else say "obpad bench not built: $(grep '^obpad' $W/build-tp132.log)"; fi
case "$OB" in ''|*[!0-9]*) OB=0;; esac
say "obpad: OWN_OB_PAD=$OB (0 = not >= 5 % faster in the bench, or not built / not bitwise)"
# 2. identity (defaults), then with the pad
run p3k $W/prompts/p3k-ids.txt 256 4096 $W/runs/e52/p3kplain-ids.txt 256 $PL $P5
spec code code
if [ $OB != 0 ]; then
  run p3k_ob $W/prompts/p3k-ids.txt 256 4096 $W/runs/e52/p3kplain-ids.txt 256 $PL $P5 OWN_OB_PAD=$OB
  run plain_ob $P1 128 4096 $W/runs/ab1/base-speed-ids.txt 128 $PL OWN_OB_PAD=$OB
  spec code_ob code OWN_OB_PAD=$OB
  spec analysis_ob analysis OWN_OB_PAD=$OB
  # 3. read A/B (same session, same levers)
  run x34k_b $x34 64 $(mx $x34 64) $R34 64 $PL $P5 $LP
  run x34k_ob $x34 64 $(mx $x34 64) $R34 64 $PL $P5 $LP OWN_OB_PAD=$OB
  run x95k_b $x95 64 $(mx $x95 64) $R95 64 $PL $P5 $LP
  run x95k_ob $x95 64 $(mx $x95 64) $R95 64 $PL $P5 $LP OWN_OB_PAD=$OB
  OBE=$(python3 -I - $D 2>>$sum <<'PY'
import re, sys
def t(n):
    for l in open(sys.argv[1] + '/' + n + '.log', errors='replace'):
        m = re.search(r'prompt: (\d+) tokens read on the cards in ([0-9.]+)s', l)
        if m: return float(m.group(2))
    return None
a, b, c, d = t('x34k_b'), t('x34k_ob'), t('x95k_b'), t('x95k_ob')
print('obpad read: 34K %.2f -> %.2f s (%+.2f %%), 95K %.2f -> %.2f s (%+.2f %%)' % (a, b, 100 * (b / a - 1), c, d, 100 * (d / c - 1)), file=sys.stderr)
print(1 if b < a and d < c else 0)
PY
)
  [ "$OBE" = 1 ] || { say "obpad: not faster in the engine; the 1M read runs without it"; OB=0; }
fi
OBV=""; [ $OB != 0 ] && OBV="OWN_OB_PAD=$OB"
# 4. the filter diagnostic (c131 s200k_dg: 18 check layer-20 differences per card, nothing printed: ifldiag-1c)
soft s200k_dg2 $x200 1024 $(mx $x200 1024) $R200 1024 $PL $P5 $SPEC OWN_SPEC_TAU=0.5 $VOC OWN_KV_SHARD=1 OWN_HOST_FLOOR_MIB=1600 OWN_SPEC_LOG=$D/s200k_dg2-spec.txt OWN_VERIFY_REF=$R200 OWN_IDX_FILT=2 OWN_IDX_FILT_MIN=8192 OWN_IDX_FILT_CK=1 OWN_IDX_FILT_CK_MIN=4096 OWN_IFL_DIAG=1
grep -h "OWN_IDX_FILT=2 check" $D/s200k_dg2.log | sed "s/^/s200k_dg2: /" >> $sum
grep -h "^IFLDIAG" $D/s200k_dg2.log | head -200 | cut -c1-300 | sed "s/^/s200k_dg2: /" >> $sum
# 4b. the long-context writing budget: guessing-check timelines at 194K (every lever, the pad) and at a short prompt
# (code), compared by kernel on card 2 (what grows with context: index scores / selects, kvshard pulls, the rest)
soft tl_s200 $x200 128 $(mx $x200 128) $R200 128 $PL $P5 $GS $LP $OBV OWN_SPEC_LOG=$D/tl_s200-spec.txt OWN_VERIFY_REF=$R200 OWN_TIMELINE=$D/tl_s200.txt OWN_TIMELINE_CHECKS=30-37
run tl_code $PP/code-ids.txt 128 4096 $W/runs/e57/code_plain-ids.txt 127 $PL $SPEC OWN_SPEC_TAU=0.5 $VOC $OBV OWN_SPEC_LOG=$D/tl_code-spec.txt OWN_TIMELINE=$D/tl_code.txt OWN_TIMELINE_CHECKS=30-37
python3 -I $W/perf/tlcmp.py $D/tl_code.txt $D/tl_s200.txt 2 > $D/cmp-ck-code-s200.txt 2>&1
head -40 $D/cmp-ck-code-s200.txt | cut -c1-200 | sed "s/^/tlcmp code vs 194K: /" >> $sum
# 5. 1M read with every prompt lever + the pad (against c131's s1m_fps)
if [ $OB != 0 ]; then
  soft s1m_ob $x1m 1024 $(mx $x1m 1024) $A 1024 $PL $P5 OWN_KV_SHARD=1 OWN_HOST_FLOOR_MIB=1600 $LP $OBV
  grep -h "free after load" $D/s1m_ob.log | head -6 | cut -c1-300 | sed "s/^/s1m_ob: /" >> $sum
  grep -q "^s1m_ob IDS1024_SAME" $sum || stop "s1m_ob: not identical (or did not run): see its log"
fi
say "ALLDONE $(date '+%F %T'): $n fresh starts identical to their references"
