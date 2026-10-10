#!/bin/bash
# Prepared command only: run by the coordinator at an authorized launch.
# Usage: start-client-119.sh <frames> <dg> <ad> <bo> <pa> <sm> <cap|none> <display> <read-ahead> <snapshots> [client args]
set -euo pipefail
FR=${1:?frames}; DG=${2:?dg 0|1}; AD=${3:?ad}; BO=${4:?bo}; PA=${5:?pa}; SM=${6:?snapshot mode}; CAP=${7:?cap GB or none}
DS=${8:?sampler-a|sampler-b|eager-display}; AR=${9:?anchor read-ahead 0|1}; SS=${10:?full|a-xpu3-sync}; shift 10
W=${LTX_STREAM_WORKDIR:-/home/steve/ltx-stream/s119-live01}
mkdir -p "$W"
exec systemd-run --user --unit=ltx119-stream-client-20261010 --property=Restart=no --property=KillSignal=SIGINT --property=TimeoutStopSec=960 \
  --property=WorkingDirectory=/home/steve/llm-optimizations/experiments/ltx25-b70/stream \
  --property="StandardOutput=append:$W/client.log" --property="StandardError=append:$W/client.log" \
  --setenv=OMP_NUM_THREADS=4 --setenv=MKL_NUM_THREADS=4 --setenv=PYTHONDONTWRITEBYTECODE=1 \
  /home/steve/.venvs/ltx25-baseline/bin/python -B ltx_continuation_client.py --packet 119 --work-dir "$W" \
  --expect-frames "$FR" --expect-placement two-way20-28 --expect-text-reuse 1 --expect-anchor frame --expect-decoder-graph "$DG" \
  --expect-anchor-decode "$AD" --expect-bencode-overlap "$BO" --expect-prep-ahead "$PA" \
  --expect-snapshot-mode "$SM" --expect-pool-cap-gb "$CAP" \
  --expect-display-schedule "$DS" --expect-anchor-read-ahead "$AR" --expect-snapshot-schedule "$SS" \
  --scenes /home/steve/llm-optimizations/experiments/ltx25-b70/data/stream/kittens-01.json \
  --sink-stats "$W/sink-stats.json" --max-ahead-seconds 60 --delete-consumed-previews --poll 0.05 "$@"
