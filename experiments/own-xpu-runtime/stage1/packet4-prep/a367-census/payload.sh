#!/bin/bash
set -euo pipefail
: "${FN_PAYLOAD:?source prepare.sh first}"
nice -n 19 taskset -c 4-15,20-31 python3 -B \
  scripts/verify-flash-next-a367-launch-payload.py --receipt "$FN_PAYLOAD" > "$FN_RECEIPTS/payload.log"
