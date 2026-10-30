#!/usr/bin/env bash
# Move finished run directories to the RAID archive: rsync, then sha256 of every file on both sides; the /dev/shm
# copy is removed only when the lists are identical. Usage: archive_runs.sh SRC_DIR DEST_DIR
set -eu
src=$1; dst=$2
[ -e "$dst" ] && { echo "destination $dst exists"; exit 1; }
mkdir -p "$(dirname "$dst")"
rsync -a "$src/" "$dst/"
( cd "$src" && find . -type f -print0 | sort -z | xargs -0 sha256sum ) >"$dst.src.sha256"
( cd "$dst" && find . -type f -print0 | sort -z | xargs -0 sha256sum ) >"$dst.dst.sha256"
if cmp -s "$dst.src.sha256" "$dst.dst.sha256"; then
  n=$(wc -l <"$dst.dst.sha256"); b=$(du -sb "$dst" | cut -f1)
  echo "verified $n files, $b bytes: $src -> $dst"; rm -rf "$src"; mv "$dst.dst.sha256" "$dst.sha256"; rm "$dst.src.sha256"
else echo "MISMATCH between $src and $dst; source kept"; exit 1; fi
