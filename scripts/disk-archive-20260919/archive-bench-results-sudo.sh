#!/usr/bin/env bash
#
# archive-bench-results-sudo.sh -- second pass for the campaign directories the user-level run in
# archive-bench-results.sh could not read: copy as root, verify as root, remove as root.
#
# Why this exists: torch-compile caches and state dirs inside a bench-results campaign are written by the
# serving container, so they are owned by root. A user-level rsync/rm walks straight past them and the copy
# is silently partial. See experiments/qwen38-27b-b70/DO-NOT-REPEAT.md, "user-level rm/rsync over
# container-written state dirs".
#
# First run: 2026-09-19. 348 directories, 78 GB, 0 verify mismatches; /mnt/fast-ai went 412 -> 503 GB free.
#
# Reads the failure list the first pass wrote, writes to the SAME destination, and keeps the same
# rsync -> verify -> remove discipline. The sudo password comes from SUDO_PW (the lab convention) and is
# never printed or echoed.
#
#   DATE=20261101 ./archive-bench-results-sudo.sh
#
set -u

DATE="${DATE:-20260919}"
CUTOFF="${CUTOFF:-2026-09-14}"
COLD_ROOT="${COLD_ROOT:-/media/steve/extended-ssd/model-cold-storage}"
DEST="${DEST:-$COLD_ROOT/b70-host-$DATE/bench-results-pre-${CUTOFF//-/}}"
BENCH_DIR="${BENCH_DIR:-/mnt/fast-ai/bench-results}"
LIST="${LIST:-$BENCH_DIR/archive-failed-$DATE.txt}"
LOG="${LOG:-$BENCH_DIR/archive-bench-results-sudo-$DATE.log}"
PW="${SUDO_PW:-/home/steve/SUDO_PASSWORD.txt}"

[ -s "$LIST" ] || { echo "Nothing to do: no list at $LIST." >&2; exit 0; }
[ -r "$PW" ] || { echo "REFUSING: no readable sudo password file at $PW." >&2; exit 2; }
mkdir -p "$DEST"

{
echo "$(date -Is) start; $(wc -l < "$LIST") dirs; dest $DEST"
cd "$BENCH_DIR" || exit 1
while read -r d; do
  [ -d "$d" ] || continue
  # shellcheck disable=SC2024  # the redirect feeds sudo's OWN stdin, where -S reads the password
  sudo -S -p '' rsync -a --no-inc-recursive "$d/" "$DEST/$d/" < "$PW" || { echo "$(date -Is) rsync FAILED $d; kept"; continue; }
  # shellcheck disable=SC2024  # the redirect feeds sudo's OWN stdin, where -S reads the password
  n=$(sudo -S -p '' rsync -a -n -i "$d/" "$DEST/$d/" < "$PW" | grep -c "^>f" || true)
  if [ "$n" = 0 ]; then
    # shellcheck disable=SC2024  # the redirect feeds sudo's OWN stdin, where -S reads the password
    sudo -S -p '' rm -rf -- "$d" < "$PW"
    if [ -e "$d" ]; then echo "$(date -Is) REMOVE FAILED $d (copy is safe in $DEST/$d)"
    else echo "$(date -Is) archived $d"; fi
  else
    echo "$(date -Is) VERIFY MISMATCH ($n) $d; kept"
  fi
done < "$LIST"
echo "$(date -Is) done"; df -h "$BENCH_DIR" | tail -1
} >> "$LOG" 2>&1
