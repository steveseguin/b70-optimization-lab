# Source only after the owner admits storage and chooses ONE arm. No launch here.
set -euo pipefail
cd /home/steve/llm-optimizations
: "${FN_ARM:?select graph-reference, graph-census or eager-census}"
FN_PACKET="$PWD/experiments/own-xpu-runtime/stage1/packet4-prep/a367-census"
FN_STAMP=$(date -u +%Y%m%dT%H%M%SZ)
FN_RECEIPTS="$PWD/data/2026-10-17-flash-next-a367-census-reseal/window-$FN_STAMP"
FN_OUTPUT="/mnt/raid-models/bench-results/a367c-$FN_STAMP"
FN_UNIT="fn-a367c-$FN_STAMP"
FN_PAYLOAD="$FN_RECEIPTS/payload.json"
FN_HEALTH="$FN_RECEIPTS/health.json"
FN_OWNER="$FN_RECEIPTS/owner-window.json"
export FN_PACKET FN_STAMP FN_RECEIPTS FN_OUTPUT FN_UNIT FN_PAYLOAD FN_HEALTH FN_OWNER FN_ARM
mkdir "$FN_RECEIPTS"
nice -n 19 taskset -c 4-15,20-31 python3 -B scripts/check-storage-headroom.py \
  "$FN_OUTPUT" --require-mount /mnt/raid-models --min-free-bytes 60GiB --planned-write-bytes 10GiB \
  > "$FN_RECEIPTS/storage.json"
mkdir -p /mnt/raid-models/bench-results
test ! -e "$FN_OUTPUT"
