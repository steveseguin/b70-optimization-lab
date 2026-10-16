#!/bin/bash
set -euo pipefail
: "${FN_PACKET:?source prepare.sh first}"
nice -n 19 taskset -c 4-15,20-31 python3 -B "$FN_PACKET/a367_census.py" \
  --plan --arm "$FN_ARM" --output "$FN_OUTPUT" > "$FN_RECEIPTS/plan.json"
nice -n 19 taskset -c 4-15,20-31 python3 -B "$FN_PACKET/ops.py" audit
