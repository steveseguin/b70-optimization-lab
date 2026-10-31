set -eu
SRC=/dev/shm/tp-svc-hs-20261030; A=/mnt/raid-models/ownrt-experiment-archives/2026-10-30; DST=$A/hc-split-endgate
[ -e "$DST" ] && { echo "$DST exists"; exit 1; }
mkdir -p "$DST"
(cd "$SRC" && find . -type f -print0 | sort -z | xargs -0 sha256sum) > "$DST.sha256"
for r in "$SRC"/*; do cp -r --preserve=timestamps "$r" "$DST/"; done
if ! (cd "$DST" && sha256sum --quiet -c "$DST.sha256"); then echo "verify FAILED: $DST (sources kept)"; exit 1; fi
echo "verified $(wc -l <"$DST.sha256") files in $DST"
B=$A/engine-builds/hc-split-r1; [ -e "$B" ] && { echo "$B exists"; exit 1; }; mkdir -p "$B"
cp -r --preserve=timestamps /dev/shm/hcsplit-2026-10-30/build-r1 /dev/shm/hcsplit-2026-10-30/tree "$B/"
(cd /dev/shm/hcsplit-2026-10-30 && find build-r1 tree -type f -print0 | sort -z | xargs -0 sha256sum) > "$B.sha256"
(cd "$B" && sha256sum --quiet -c "$B.sha256") && echo "verified $(wc -l <"$B.sha256") files in $B" || { echo "build archive verify FAILED"; exit 1; }
rm -rf "${SRC:?}"/*; rmdir "$SRC"; echo "removed $SRC"
