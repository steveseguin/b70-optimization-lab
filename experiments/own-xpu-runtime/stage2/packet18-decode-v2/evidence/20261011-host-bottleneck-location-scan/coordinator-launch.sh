#!/bin/bash
# Coordinator diagnostic: packet 18 sources with the per-launch profiling queries removed
# (scratch build, not sealed). Same command line as packet 18 W3/W2; the native program
# still stops at the first layer that differs from the v2 oracle. No NEO keys. One child, no retry.
cd /home/steve/llm-optimizations
export LD_LIBRARY_PATH='/opt/intel/oneapi/tcm/1.5/lib:/opt/intel/oneapi/umf/1.1/lib:/opt/intel/oneapi/tcm/1.5/env/../lib:/opt/intel/oneapi/tbb/2023.0/env/../lib/intel64/gcc4.8:/opt/intel/oneapi/pti/1.0/lib:/opt/intel/oneapi/mkl/2026.0/lib:/opt/intel/oneapi/dnnl/2026.0/lib:/opt/intel/oneapi/debugger/2026.0/opt/debugger/lib:/opt/intel/oneapi/compiler/2026.0/opt/compiler/lib:/opt/intel/oneapi/compiler/2026.0/lib'
B=/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/scratch-p18-notiming/build/device/own-rt-iq3
P18=/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet18-decode-v2
OUT=/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/scratch-p18-notiming/build/run-$1
GEMV=$2
[ -e "$OUT" ] && { echo "output exists"; exit 2; }
mkdir -p "$OUT"
echo "start $(date -u +%FT%TZ) gemv=$GEMV" > "$OUT/coordinator.log"
grep -E 'MemAvailable|GPUActive' /proc/meminfo > "$OUT/meminfo-before.txt"
env -i HOME=$HOME LANG=C.UTF-8 PATH=/usr/bin:/bin OMP_NUM_THREADS=2 LD_LIBRARY_PATH="$LD_LIBRARY_PATH" nice -n 19 ionice -c 3 $B --authorized-device-window --card 2 --cards 2 --memory resident --stage decode --nongemv parallel --gemv $GEMV --prompt-tokens $P18/build/input/tokens.txt --max-new 64 --context 256 --plan $P18/build/input/plan.tsv --identity $P18/build/input/identity.tsv --model-dir /mnt/usb-models/llm-models/unsloth-Qwen3.8-Flash-Next-GGUF-766911a6/UD-IQ3_XXS --oracle /home/steve/llm-optimizations/experiments/qwen38-flash-next-ud-iq3xxs-b70/packet3-runtime-oracle/runs/arithmetic-v2-detmath-20261011/incident-retrospective --output $OUT/run --seconds 3600 > "$OUT/stdout.txt" 2>&1 &
PID=$!; echo $PID > "$OUT/pid"; SINCE=$(date +%s)
while kill -0 $PID 2>/dev/null; do
  sleep 5
  if journalctl -k --since "@$SINCE" --no-pager | grep -Eiq 'xe .*(reset|timedout|fault response|wedged)|hard lockup'; then
    echo "kernel fault line $(date -u +%FT%TZ); one cooperative SIGINT" >> "$OUT/coordinator.log"; kill -INT $PID; break
  fi
done
wait $PID; RC=$?
journalctl -k --since "@$SINCE" --no-pager > "$OUT/kernel-window.txt"
echo "rc=$RC $(date -u +%FT%TZ)" >> "$OUT/coordinator.log"
echo $RC > "$OUT/rc"
