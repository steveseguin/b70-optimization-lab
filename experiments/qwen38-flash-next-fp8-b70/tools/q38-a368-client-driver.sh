#!/usr/bin/env bash
# A368 driver: the certified frozen client checks the run directory and /health immediately, so
# when launched through q38-launch-frozen-attempt.sh it must be started only once the server is
# healthy. Wait (bounded) for the run directory and a 200 from /health, then exec the client.
set -Eeuo pipefail
here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
client="$here/run-tp4-mtp2-4352-ple-only-a368-fullgraphdet-w13n32-client.sh"
run_dir=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-fullgraphdet-mtp2-4352-ple-only-r1-attempt368
port=19981
for _ in $(seq 1 240); do
  if [[ -d "$run_dir" ]] && curl -fsS --max-time 5 "http://127.0.0.1:${port}/health" >/dev/null 2>&1; then
    echo "driver: server healthy at $(date +%H:%M:%S); starting the certified client"
    exec "$client"
  fi
  [[ -f /tmp/q38-mtp2-ple-only-a368.rc ]] && { echo "driver: server exited before healthy (rc $(cat /tmp/q38-mtp2-ple-only-a368.rc))"; exit 1; }
  sleep 15
done
echo "driver: server not healthy within 60 minutes"; exit 1
