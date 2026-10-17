# FUTURE coordinator only. Source once for control, then once for candidate.
set -euo pipefail
cd /home/steve/llm-optimizations
: "${FN_ARM:?select control or candidate}"
FN_PACKET="$PWD/experiments/own-xpu-runtime/stage1/packet4-prep/a367-glue01"
FN_BUILD="$PWD/data/2026-10-17-flash-next-a367-glue01-build"
FN_CAMPAIGN="$FN_BUILD/campaign.json"
export FN_PACKET FN_BUILD FN_CAMPAIGN FN_ARM
nice -n 19 taskset -c 4-15,20-31 python3 -B "$FN_PACKET/ops.py" prepare
# Values come from the fixed two-arm campaign, never arbitrary shell evaluation.
FN_OUTPUT=$(nice -n 19 taskset -c 4-15,20-31 python3 -B "$FN_PACKET/ops.py" output)
FN_RECEIPTS="$FN_BUILD/window-$(basename "$FN_OUTPUT")"
FN_UNIT="fn-$(basename "$FN_OUTPUT")"
FN_PAYLOAD="$FN_RECEIPTS/payload.json"
FN_HEALTH="$FN_RECEIPTS/health.json"
FN_OWNER="$FN_RECEIPTS/owner-window.json"
export FN_OUTPUT FN_RECEIPTS FN_UNIT FN_PAYLOAD FN_HEALTH FN_OWNER
mkdir "$FN_RECEIPTS"
nice -n 19 taskset -c 4-15,20-31 python3 -B scripts/check-storage-headroom.py \
  "$FN_OUTPUT" --require-mount /mnt/raid-models --min-free-bytes 60GiB --planned-write-bytes 10GiB \
  > "$FN_RECEIPTS/storage.json"
mkdir -p /mnt/raid-models/bench-results
test ! -e "$FN_OUTPUT"
