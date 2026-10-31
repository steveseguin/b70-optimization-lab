#!/usr/bin/env bash
# Archive the AOT end-gate servers' work directories (research/aot-tp-2026-10-31/suite; copy of
# two-card-flags-2026-10-31/suite/archive_endgate.sh, paths only; the AOT build and its tree are archived by
# ../archive_build.sh). sha256 list, copy, verify at the destination, then remove the /dev/shm copy.
set -eu
SRC=/dev/shm/tp-svc-aot-20261031; A=/mnt/raid-models/ownrt-experiment-archives/2026-10-31; DST=$A/aot-tp-endgate${1:+-$1}
[ -e "$DST" ] && { echo "$DST exists"; exit 1; }
mkdir -p "$DST"
(cd "$SRC" && find . -type f -print0 | sort -z | xargs -0 sha256sum) > "$DST.sha256"
for r in "$SRC"/*; do cp -r --preserve=timestamps "$r" "$DST/"; done
if ! (cd "$DST" && sha256sum --quiet -c "$DST.sha256"); then echo "verify FAILED: $DST (sources kept)"; exit 1; fi
echo "verified $(wc -l <"$DST.sha256") files in $DST"
rm -rf "${SRC:?}"/*; rmdir "$SRC"; echo "removed $SRC"
