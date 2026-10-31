#!/usr/bin/env bash
# Archive the two-card end-gate servers' work directories (research/two-card-flags-2026-10-31/suite; copy of
# hc-split-2026-10-30/suite/archive_endgate.sh without the build copy: build r1 and its tree are already archived at
# .../2026-10-30/engine-builds/hc-split-r1). sha256 list, copy, verify at the destination, then remove the /dev/shm copy.
set -eu
SRC=/dev/shm/tp-svc-tc-20261031; A=/mnt/raid-models/ownrt-experiment-archives/2026-10-31; DST=$A/two-card-flags-endgate
[ -e "$DST" ] && { echo "$DST exists"; exit 1; }
mkdir -p "$DST"
(cd "$SRC" && find . -type f -print0 | sort -z | xargs -0 sha256sum) > "$DST.sha256"
for r in "$SRC"/*; do cp -r --preserve=timestamps "$r" "$DST/"; done
if ! (cd "$DST" && sha256sum --quiet -c "$DST.sha256"); then echo "verify FAILED: $DST (sources kept)"; exit 1; fi
echo "verified $(wc -l <"$DST.sha256") files in $DST"
rm -rf "${SRC:?}"/*; rmdir "$SRC"; echo "removed $SRC"
