#!/usr/bin/env bash
# Driver for the frozen launcher: wait until the packet's server answers
# /health (the load from the USB checkpoint takes 9-12 minutes; graph capture
# and warmup follow), then run the packet's frozen client, which sends the
# fixed cold realistic suite exactly once and writes realistic-suite-v1-result.json.
set -euo pipefail
attempt=${1:?attempt}; port=${2:?port}
repo="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd -P)"
client="$repo/experiments/qwen38-flash-next-fp8-b70/tools/run-tp4-mtp1-4352-ple-only-a${attempt}-fullgraphdet-w13n32-client.sh"
rc_file="/tmp/q38-mtp1-ple-only-a${attempt}.rc"
deadline=$(( $(date +%s) + 2700 ))
until curl -fsS --max-time 5 "http://127.0.0.1:${port}/health" >/dev/null 2>&1; do
  [[ -f "$rc_file" ]] && { echo "server exited before becoming healthy (rc $(cat "$rc_file"))"; exit 1; }
  (( $(date +%s) < deadline )) || { echo "server not healthy after 45 minutes"; exit 1; }
  sleep 15
done
echo "server healthy at $(date +%H:%M:%S); starting the frozen client"
"$client"
