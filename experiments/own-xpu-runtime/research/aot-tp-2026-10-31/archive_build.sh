#!/usr/bin/env bash
# Archive the AOT build and its source tree (research/aot-tp-2026-10-31) to the RAID: sha256 list, copy
# (cp -r --preserve=timestamps: the NTFS RAID refuses POSIX ACLs), verify at the destination. The /dev/shm copies stay in
# place, because the engine receipt results/engine-receipt-a1959e7ccf88.json pins their absolute paths (the lab adapter
# re-hashes every compiled source and object at launch), as hc-split-2026-10-30 kept r1's. Usage: archive_build.sh
set -eu
SRC=/dev/shm/aot-tp-2026-10-31; A=/mnt/raid-models/ownrt-experiment-archives/2026-10-31/engine-builds; DST=$A/aot-tp-r1
[ -e "$DST" ] && { echo "$DST exists"; exit 1; }
mkdir -p "$DST"
(cd "$SRC" && find build-r1 tree -type f -print0 | sort -z | xargs -0 sha256sum) > "$DST.sha256"
cp -r --preserve=timestamps "$SRC/build-r1" "$SRC/tree" "$DST/"
if ! (cd "$DST" && sha256sum --quiet -c "$DST.sha256"); then echo "verify FAILED: $DST"; exit 1; fi
echo "verified $(wc -l <"$DST.sha256") files in $DST (sources kept in $SRC: the receipt pins them)"
