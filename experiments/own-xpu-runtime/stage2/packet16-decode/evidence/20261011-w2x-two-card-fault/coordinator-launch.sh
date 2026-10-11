#!/bin/bash
# Coordinator speed diagnostic: packet 16 W2 command line without --oracle (the v1 CPU oracle
# cannot match device arithmetic, and the native binary stops at the first differing layer).
# Exactness is checked afterwards against the packet 13 device fixtures. One child, no retry.
cd /home/steve/llm-optimizations
set +u; source /opt/intel/oneapi/setvars.sh --force >/dev/null 2>&1; set -u
P=/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet16-decode
OUT=$P/build/w2x-cards23-speed-$1
GEMV=$2
[ -e "$OUT" ] && { echo "output exists"; exit 2; }
mkdir -p "$OUT"
journalctl -k -b --no-pager | tail -n 50 > "$OUT/preflight-kernel.txt"
grep MemAvailable /proc/meminfo > "$OUT/meminfo-before.txt"; grep -i gpuactive /proc/meminfo >> "$OUT/meminfo-before.txt" || true
echo "start $(date -u +%FT%TZ) gemv=$GEMV" | tee "$OUT/coordinator.log"
env NEOReadDebugKeys=1 EnableDeferBacking=0 OMP_NUM_THREADS=2 nice -n 19 ionice -c 3 $P/build/device/own-rt-iq3 --authorized-device-window --card 2 --cards 2 --memory resident --stage decode --nongemv parallel --gemv $GEMV --prompt-tokens $P/build/input/tokens.txt --max-new 64 --context 256 --plan $P/build/input/plan.tsv --identity $P/build/input/identity.tsv --model-dir /mnt/usb-models/llm-models/unsloth-Qwen3.8-Flash-Next-GGUF-766911a6/UD-IQ3_XXS --output $OUT/run --seconds 5400 > "$OUT/stdout.txt" 2>&1 &
PID=$!; echo $PID > "$OUT/pid"
SINCE=$(date +%s)
while kill -0 $PID 2>/dev/null; do
  sleep 10
  if journalctl -k --since "@$SINCE" --no-pager | grep -Eiq 'xe .*(reset|timedout|fault|wedged)|hard lockup'; then
    echo "kernel fault line seen $(date -u +%FT%TZ); one cooperative SIGINT" >> "$OUT/coordinator.log"
    kill -INT $PID; journalctl -k --since "@$SINCE" --no-pager > "$OUT/kernel-window.txt"; wait $PID; echo "rc=$? after fault" >> "$OUT/coordinator.log"; exit 3
  fi
  { grep MemAvailable /proc/meminfo; grep -i gpuactive /proc/meminfo; } | tr '\n' ' ' >> "$OUT/meminfo-trace.txt"; echo >> "$OUT/meminfo-trace.txt"
done
wait $PID; RC=$?
journalctl -k --since "@$SINCE" --no-pager > "$OUT/kernel-window.txt"
echo "rc=$RC $(date -u +%FT%TZ)" | tee -a "$OUT/coordinator.log"
exit $RC
