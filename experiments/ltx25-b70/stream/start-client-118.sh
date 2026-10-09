#!/bin/bash
# Start the packet-118 continuation client as a user unit.
# Usage: start-client-118.sh <frames> <dg> <ad> <bo> <pa> <sm walk|fingerprint> <cap GB|none> [extra client args]
FR=${1:?frames}; DG=${2:?dg 0|1}; AD=${3:?ad}; BO=${4:?bo}; PA=${5:?pa}; SM=${6:?sm walk|fingerprint}; CAP=${7:?cap GB or none}; shift 7
W=/home/steve/ltx-stream/s118-stream01; mkdir -p $W
systemctl --user reset-failed ltx118-stream-client-20261009 2>/dev/null
exec systemd-run --user --unit=ltx118-stream-client-20261009 --property=Restart=no --property=KillSignal=SIGINT --property=TimeoutStopSec=960 \
  --property=WorkingDirectory=/home/steve/llm-optimizations/experiments/ltx25-b70/stream \
  --property=StandardOutput=append:$W/client.log --property=StandardError=append:$W/client.log \
  /home/steve/.venvs/ltx25-baseline/bin/python -B ltx_continuation_client.py --packet 118 --work-dir $W \
  --expect-frames $FR --expect-placement two-way20-28 --expect-text-reuse 1 --expect-anchor frame --expect-decoder-graph $DG \
  --expect-anchor-decode $AD --expect-bencode-overlap $BO --expect-prep-ahead $PA \
  --expect-snapshot-mode $SM --expect-pool-cap-gb $CAP \
  --scenes /home/steve/llm-optimizations/experiments/ltx25-b70/data/stream/kittens-01.json \
  --sink-stats $W/sink-stats.json --max-ahead-seconds 60 --delete-consumed-previews --poll 0.05 "$@"
