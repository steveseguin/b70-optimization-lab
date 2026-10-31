#!/usr/bin/env bash
# Record both rank processes' OWNRT_* keys, card selection and launch keys from /proc/<pid>/environ of a running lab server
# (aot-tp-2026-10-31 copy of two-card-flags-2026-10-31/suite/rank_env.sh: the work directory is an argument, and the
# rank's --wait-seconds argument and executable are recorded too).
# Usage: rank_env.sh NAME WORKDIR; writes logs/rank-env-NAME.txt. Read-only.
set -eu
D=$(cd "$(dirname "$0")" && pwd)
run=$(ls -d "$2"/control/run-*/ranks | head -1)
out=$D/logs/rank-env-$1.txt; : >"$out"
for r in 0 1; do
  pid=$(python3 -c "import json;print(json.load(open('$run/rank$r-launch.json'))['pid'])")
  echo "# rank$r pid $pid $(cat /proc/$pid/comm) exe $(readlink /proc/$pid/exe) at $(date -Is)" >>"$out"
  echo "# argv --wait-seconds: $(tr '\0' '\n' </proc/$pid/cmdline | grep -A1 -x -- --wait-seconds | tail -1 | grep . || echo absent)" >>"$out"
  tr '\0' '\n' </proc/$pid/environ | grep -E '^(OWNRT_|FilterBdfPath=|ZE_AFFINITY_MASK=|NEOReadDebugKeys=|EnableDeferBacking=|SYCL_CACHE|NEO_CACHE)' | sort >>"$out"
done
echo "$out: $(grep -c . "$out") lines"
