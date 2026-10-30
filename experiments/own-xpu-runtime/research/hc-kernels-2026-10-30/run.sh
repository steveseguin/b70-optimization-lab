#!/usr/bin/env bash
# Usage: run.sh CARD BINARY TAG [ARGS...]   CARD is 43 or 47 (0000:CARD:00.0).
# One microbenchmark on ONE card, holding /dev/shm/cardCARD.lock only while it runs (waits for the lock).
# Kernel log is checked before and after (sudo, password from the file on stdin, never printed). Any fault line, or
# a HALT file from an earlier fault, stops all device work: evidence is saved and nothing is retried.
set -u
CARD=$1; BIN=$2; TAG=$3; shift 3
D=$(cd "$(dirname "$0")" && pwd)
H=/dev/shm/hc-kernels-2026-10-30
LOG=$D/logs/$TAG.log
mkdir -p "$D/logs" "$D/results" "$H/cache"
[ -e "$H/HALT" ] && { echo "HALT present: $(cat "$H/HALT")"; exit 3; }
case $CARD in 43|47) ;; *) echo "card must be 43 or 47"; exit 2;; esac
klog() { sudo -S -p '' journalctl -k --since "@$1" --no-pager < /home/steve/SUDOPASSWORD.txt 2>/dev/null |
         grep -iE "fault response|cat error|engine reset|coredump|devcoredump|xe .*(fault|reset|timed out|error)|GuC.*(fail|error|reset)" ; }
echo "wait-lock $(date -Is)" > "$LOG"
exec 9>"/dev/shm/card$CARD.lock"
flock 9
[ -e "$H/HALT" ] && { echo "HALT present" >> "$LOG"; flock -u 9; exit 3; }
PRE=$(date +%s)
B=$(klog $((PRE-600)) | wc -l)
echo "lock $(date -Is) card 0000:$CARD:00.0 bin $(sha256sum "$BIN" | cut -c1-12) pre-window-faults $B" >> "$LOG"
if [ "$B" != "0" ]; then echo "pre-run fault lines in the last 10 min: refusing" >> "$LOG"; klog $((PRE-600)) >> "$LOG"; flock -u 9; exit 4; fi
START=$(date +%s)
env NEOReadDebugKeys=1 EnableDeferBacking=0 FilterBdfPath=0000:$CARD:00.0 ZE_ENABLE_PCI_ID_DEVICE_ORDER=1 \
  ONEAPI_DEVICE_SELECTOR=level_zero:0 SYCL_CACHE_DIR=$H/cache/sycl NEO_CACHE_DIR=$H/cache/neo \
  LD_LIBRARY_PATH=/opt/intel/oneapi/tcm/1.5/lib:/opt/intel/oneapi/umf/1.1/lib:/opt/intel/oneapi/compiler/2026.0/opt/compiler/lib:/opt/intel/oneapi/compiler/2026.0/lib \
  nice -n 5 taskset -c 8-15,24-31 "$BIN" "$@" > "$D/results/$TAG.json" 2>> "$LOG" &
P=$!
NODES=""
for i in $(seq 1 300); do
  sleep 0.1
  n=$(ls -l /proc/$P/fd 2>/dev/null | grep -o 'renderD[0-9]*' | sort -u | tr '\n' ' ')
  [ -n "$n" ] && { NODES=$n; break; }
  kill -0 $P 2>/dev/null || break
done
wait $P; RC=$?
sleep 2
F=$(klog "$START")
echo "end $(date -Is) rc $RC nodes [$NODES] faults [$(echo -n "$F" | wc -l)]" >> "$LOG"
if [ -n "$F" ]; then
  echo "$F" >> "$LOG"
  echo "FAULT after $TAG (card $CARD) at $(date -Is)" > "$H/HALT"
  ls -l /sys/class/devcoredump/ >> "$LOG" 2>&1
fi
flock -u 9
cat "$LOG"
exit $RC
