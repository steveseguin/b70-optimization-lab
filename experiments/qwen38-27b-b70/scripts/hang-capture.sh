#!/usr/bin/env bash
# Evidence of a stuck TP server while its processes are still alive (notes/2026-10-17-hang-repro.md). At 06:23 the
# hang ran 42 s before the desktop's redraw on card 03 exposed it, and the TP1 worker left nothing in the log; this
# watcher fills that gap. Run as root (sudo -A) beside a server; it only reads.
#
#   sudo -A bash hang-capture.sh OUT_DIR [PROGRESS_FILE [SILENT_S]]
#
# Triggers, polled every second: a b70-step-breadcrumbs STALL/FAILED line in any running container's log, or
# PROGRESS_FILE (a client's or keeper's log that grows with every finished request) not growing for SILENT_S seconds
# (default 8) while it exists. On a trigger: two captures 10 s apart into OUT_DIR/capture-<time>/pass1|pass2, each
# with py-spy stacks (non-blocking) of every python process in the containers, every thread's kernel state (state,
# wait channel, syscall, kernel stack) and both cards' gt0/hw_engines. Re-armed when the progress file grows again;
# at most 5 captures. Stops when OUT_DIR/STOP exists. py-spy 0.4.0 is fetched once into /mnt/fast-ai/tools/py-spy.
set -uo pipefail
[[ $(id -u) == 0 ]] || { echo "run as root"; exit 1; }
OUT=${1:?OUT_DIR}; PROG=${2:-}; SILENT=${3:-8}
[[ $OUT == /home/steve/* || $OUT == /mnt/fast-ai/* ]] || { echo "OUT_DIR must be under /home/steve or /mnt/fast-ai"; exit 1; }
mkdir -p "$OUT"
T=/mnt/fast-ai/tools/py-spy; P=$T/py-spy
if [[ ! -x $P ]]; then
  mkdir -p "$T/dl" && chown -R 1000:1000 "$T" && sudo -u steve python3 -I -m pip download py-spy==0.4.0 --no-deps --only-binary=:all: -d "$T/dl" -q \
    && python3 -I -c "import zipfile,glob;z=zipfile.ZipFile(glob.glob('$T/dl/py_spy-0.4.0-*.whl')[0]);open('$P','wb').write(z.read('py_spy-0.4.0.data/scripts/py-spy'))" \
    && chmod +x "$P" || echo "py-spy not available: stacks will be missing"
fi
capture() {  # dir
  local o=$1; mkdir -p "$o"
  for c in $(docker ps -q); do docker top "$c" -eo pid,args 2>/dev/null | awk 'NR>1 && /python3|VLLM::/ {print $1}'; done > "$o/pids"
  for p in $(cat "$o/pids"); do
    [[ -x $P ]] && "$P" dump --pid "$p" --nonblocking > "$o/pyspy-$p.txt" 2>&1
    for t in /proc/$p/task/*; do
      printf '%s %s state=%s wchan=%s syscall=%s\n' "${t##*/}" "$(cat $t/comm 2>/dev/null)" \
        "$(awk '/^State/{print $2}' $t/status 2>/dev/null)" "$(cat $t/wchan 2>/dev/null)" "$(cut -d' ' -f1-3 $t/syscall 2>/dev/null)"
      head -12 $t/stack 2>/dev/null | sed 's/^/    /'
    done > "$o/tasks-$p.txt"
  done
  for g in /sys/kernel/debug/dri/0000:*/gt0/hw_engines; do
    [[ -e $g ]] && cat "$g" > "$o/hw-$(echo "$g" | cut -d/ -f6).txt" 2>/dev/null
  done
  journalctl -k --since "-3 min" --no-pager -o short-precise > "$o/kernel.txt" 2>/dev/null
  date '+%F %T.%N' > "$o/time"
  chown -R 1000:1000 "$o"
}
captures=0; armed=1; last_size=-1; last_capture=0
echo "hang-capture: watching containers' breadcrumbs${PROG:+ and $PROG (silent ${SILENT}s)} -> $OUT"
while [[ ! -e $OUT/STOP ]]; do
  why=
  for c in $(docker ps -q 2>/dev/null); do
    docker logs --since 3s "$c" 2>&1 | grep -qE 'b70_step_breadcrumbs rank .* (STALL|FAILED)' && why="breadcrumbs stall in $c"
  done
  if [[ -n $PROG && -f $PROG ]]; then
    size=$(stat -c %s "$PROG"); age=$(( $(date +%s) - $(stat -c %Y "$PROG") ))
    (( ! armed && size != last_size )) && { armed=1; echo "$(date +%T) progress again: re-armed"; }
    [[ -z $why ]] && (( age >= SILENT )) && why="$PROG silent ${age}s"
  elif [[ -z $PROG ]] && (( ! armed && $(date +%s) - last_capture > 120 )); then
    armed=1   # breadcrumbs only: re-arm two minutes after a capture
  fi
  if [[ -n $why ]] && (( armed && captures < 5 )); then
    d=$OUT/capture-$(date +%H%M%S); echo "$(date +%T) CAPTURE ($why) -> $d"
    capture "$d/pass1"; sleep 10; capture "$d/pass2"; chown -R 1000:1000 "$d"
    captures=$((captures + 1)); armed=0; last_capture=$(date +%s); [[ -n $PROG && -f $PROG ]] && last_size=$(stat -c %s "$PROG")
    echo "$(date +%T) CAPTURE done ($(ls "$d/pass1" | wc -l) files)"
  fi
  sleep 1
done
