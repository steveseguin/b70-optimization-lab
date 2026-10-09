#!/bin/bash
# Start the packet-117 continuation client as a user unit. Usage: start-client-117.sh <frames> <ad> <bo> <pa> [extra client args]
FR=${1:?frames}; AD=${2:?ad}; BO=${3:?bo}; PA=${4:?pa}; shift 4
W=/home/steve/ltx-stream/s117-stream01; mkdir -p $W
systemctl --user reset-failed ltx117-stream-client-20261008 2>/dev/null
exec systemd-run --user --unit=ltx117-stream-client-20261008 --property=Restart=no --property=KillSignal=SIGINT --property=TimeoutStopSec=960 \
  --property=WorkingDirectory=/home/steve/llm-optimizations/experiments/ltx25-b70/stream \
  --property=StandardOutput=append:$W/client.log --property=StandardError=append:$W/client.log \
  /home/steve/.venvs/ltx25-baseline/bin/python -B ltx_continuation_client.py --packet 117 --work-dir $W \
  --expect-frames $FR --expect-placement two-way20-28 --expect-text-reuse 1 --expect-anchor frame --expect-decoder-graph 1 \
  --expect-anchor-decode $AD --expect-bencode-overlap $BO --expect-prep-ahead $PA \
  --scenes /home/steve/llm-optimizations/experiments/ltx25-b70/data/stream/kittens-01.json \
  --sink-stats $W/sink-stats.json --max-ahead-seconds 60 --delete-consumed-previews --poll 0.05 "$@"
