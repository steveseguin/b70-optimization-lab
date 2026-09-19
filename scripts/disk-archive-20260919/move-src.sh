#!/usr/bin/env bash
#
# move-src.sh -- move a source tree off the fast disk to cold storage, verified by a second rsync pass.
#
# First run: 2026-09-19, for /mnt/fast-ai/src -- 26 llama.cpp worktrees, 14 GB of sources left after
# `disk-cleanup-20260919.sh --tier 2` removed the 168 build directories inside them. The q8 llama.cpp lanes
# are not active; the recipes that produced them are in the repo.
#
# Discipline: rsync -> dry-run rsync verify -> remove. The source is kept if the verify pass lists anything.
# The mount point itself is kept; only its contents are removed.
#
#   DATE=20261101 SRC=/mnt/fast-ai/src DEST_NAME=src-llama-cpp-worktrees ./move-src.sh
#
set -u

DATE="${DATE:-20260919}"
SRC="${SRC:-/mnt/fast-ai/src}"
COLD_ROOT="${COLD_ROOT:-/media/steve/extended-ssd/model-cold-storage}"
DEST_NAME="${DEST_NAME:-src-llama-cpp-worktrees}"
DEST="${DEST:-$COLD_ROOT/b70-host-$DATE/$DEST_NAME}"
LOG="${LOG:-/mnt/fast-ai/bench-results/move-src-$DATE.log}"
SUDO_PW="${SUDO_PW:-/home/steve/SUDO_PASSWORD.txt}"   # lab convention; never printed
WAIT_UNIT="${WAIT_UNIT:-}"              # optional systemd --user unit to wait out first (same USB disk)

[ -d "$SRC" ] || { echo "Nothing to do: $SRC does not exist." >&2; exit 0; }
if [ -n "$WAIT_UNIT" ]; then
    until ! systemctl --user is-active "$WAIT_UNIT" >/dev/null 2>&1; do sleep 30; done
fi
mkdir -p "$DEST"

{
echo "$(date -Is) start ($(du -sh "$SRC" | cut -f1)) -> $DEST"
rsync -a --no-inc-recursive "$SRC/" "$DEST/" || { echo "$(date -Is) rsync FAILED; kept"; exit 1; }
n=$(rsync -a -n -i "$SRC/" "$DEST/" | grep -c "^>f" || true)
if [ "$n" = 0 ]; then
  find "$SRC" -mindepth 1 -maxdepth 1 -exec rm -rf -- {} + 2>/dev/null
  if [ -n "$(ls -A "$SRC" 2>/dev/null)" ] && [ -r "$SUDO_PW" ]; then
    # shellcheck disable=SC2024  # the redirect feeds sudo's OWN stdin, where -S reads the password
    sudo -S -p '' find "$SRC" -mindepth 1 -maxdepth 1 -exec rm -rf -- {} + < "$SUDO_PW" 2>/dev/null
  fi
  if [ -n "$(ls -A "$SRC" 2>/dev/null)" ]; then echo "$(date -Is) REMOVE INCOMPLETE; $SRC still has entries (copy is safe in $DEST)"
  else echo "$(date -Is) archived $SRC"; fi
else
  echo "$(date -Is) VERIFY MISMATCH ($n); kept"
fi
echo "$(date -Is) done"; df -h "$(dirname "$SRC")" | tail -1
} >> "$LOG" 2>&1
