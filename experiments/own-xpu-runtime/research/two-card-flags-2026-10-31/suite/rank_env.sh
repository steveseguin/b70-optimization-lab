#!/usr/bin/env bash
# Record both rank processes' OWNRT_* keys and card (FilterBdfPath) from /proc/<pid>/environ of a running lab server.
# Usage: rank_env.sh NAME (e.g. twoB-r1); writes logs/rank-env-NAME.txt. Read-only.
set -eu
D=$(cd "$(dirname "$0")" && pwd); n=$(echo "$1" | tr A-Z a-z)
run=$(ls -d /dev/shm/tp-svc-tc-20261031/arm-$n-c65536/control/run-*/ranks | head -1)
out=$D/logs/rank-env-$1.txt; : >"$out"
for r in 0 1; do
  pid=$(python3 -c "import json;print(json.load(open('$run/rank$r-launch.json'))['pid'])")
  echo "# rank$r pid $pid $(cat /proc/$pid/comm) at $(date -Is)" >>"$out"
  tr '\0' '\n' </proc/$pid/environ | grep -E '^(OWNRT_|FilterBdfPath=|ZE_AFFINITY_MASK=|NEOReadDebugKeys=|EnableDeferBacking=)' | sort >>"$out"
done
echo "$out: $(grep -c . "$out") lines"
