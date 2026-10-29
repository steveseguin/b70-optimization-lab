#!/usr/bin/env bash
# Archive finished RAM run directories to the RAID (rsync, then verify file count, bytes and sha256 of every file),
# then remove the RAM copy. Usage: archive_runs.sh SRC_DIR DEST_NAME   (dest under /mnt/raid-models/ownrt-experiment-archives/2026-10-29/)
set -eu
SRC=$1; DEST=/mnt/raid-models/ownrt-experiment-archives/2026-10-29/$2
[ -d "$SRC" ] || { echo "no $SRC"; exit 1; }
mkdir -p "$(dirname "$DEST")"; [ -e "$DEST" ] && { echo "$DEST exists"; exit 1; }
rsync -a "$SRC/" "$DEST/"
a=$(cd "$SRC" && find . -type f -print0 | sort -z | xargs -0 sha256sum | sha256sum); b=$(cd "$DEST" && find . -type f -print0 | sort -z | xargs -0 sha256sum | sha256sum)
n=$(find "$SRC" -type f | wc -l); s=$(du -sb "$SRC" | cut -f1); n2=$(find "$DEST" -type f | wc -l); s2=$(du -sb --apparent-size "$DEST" | cut -f1); s1=$(du -sb --apparent-size "$SRC" | cut -f1)
[ "$a" = "$b" ] && [ "$n" = "$n2" ] && [ "$s1" = "$s2" ] || { echo "VERIFY FAILED $SRC -> $DEST"; exit 1; }
echo "archived $SRC -> $DEST: $n files, $s1 bytes, sha256 of per-file sums ${a%% *}"
rm -rf "$SRC"
