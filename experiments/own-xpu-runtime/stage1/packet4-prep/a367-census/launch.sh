#!/bin/bash
set -euo pipefail
: "${FN_PACKET:?source prepare.sh first}"
nice -n 19 taskset -c 4-15,20-31 python3 -B scripts/check-storage-headroom.py \
  "$FN_OUTPUT" --require-mount /mnt/raid-models --min-free-bytes 60GiB --planned-write-bytes 10GiB \
  > "$FN_RECEIPTS/storage-at-launch.json"
# Start from the owner's normal-priority unrestricted shell. Do not wrap this unit in nice/taskset.
systemd-run --user --unit="$FN_UNIT" \
  --property=Restart=no --property=KillMode=process --property=KillSignal=SIGINT \
  --property=SendSIGKILL=no --property=TimeoutStopSec=infinity --property=RuntimeMaxSec=infinity \
  --working-directory="$PWD" /usr/bin/python3 -B "$FN_PACKET/a367_census.py" \
  --execute --arm "$FN_ARM" --owner-window "$FN_OWNER" --health-receipt "$FN_HEALTH" \
  --payload-receipt "$FN_PAYLOAD" --output "$FN_OUTPUT"
