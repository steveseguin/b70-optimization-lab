#!/usr/bin/env bash
# Archive finished rank-harness runs from /dev/shm to the RAID (xtail-2026-10-31, copy of hc-split's): sha256 list of the sources, copy
# (cp -r --preserve=timestamps: the NTFS RAID refuses POSIX ACLs), verify every hash at the destination, then remove the
# /dev/shm copies. Usage: archive_runs.sh NAME RUN... (run names under /dev/shm/xtail-2026-10-31/runs).
set -eu
RUNS=/dev/shm/xtail-2026-10-31/runs; A=/mnt/raid-models/ownrt-experiment-archives/${ARCHIVE_DAY:-2026-10-31}
NAME=$1; shift; DST=$A/xtail-$NAME
[ -e "$DST" ] && { echo "$DST exists"; exit 1; }
mkdir -p "$DST"
(cd "$RUNS" && find "$@" -type f -print0 | sort -z | xargs -0 sha256sum) > "$DST.sha256"
for r in "$@"; do cp -r --preserve=timestamps "$RUNS/$r" "$DST/"; done
if ! (cd "$DST" && sha256sum --quiet -c "$DST.sha256"); then echo "verify FAILED: $DST (sources kept)"; exit 1; fi
echo "verified $(wc -l <"$DST.sha256") files in $DST"
for r in "$@"; do rm -rf "${RUNS:?}/$r"; done
