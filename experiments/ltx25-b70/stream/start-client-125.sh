#!/bin/bash
# Prepared command only: run by the coordinator at an authorized launch.
# Usage: start-client-125.sh <frames> <dg> <ad> <bo> <pa> <sm> <cap|none> <display> <read-ahead> <snapshots> <display-device> [client args]
set -euo pipefail
FR=${1:?frames}; DG=${2:?dg 0|1}; AD=${3:?ad}; BO=${4:?bo}; PA=${5:?pa}; SM=${6:?snapshot mode}; CAP=${7:?cap GB or none}
DS=${8:?sampler-a|sampler-b|eager-display}; AR=${9:?anchor read-ahead 0|1}; SS=${10:?full|a-xpu3-sync}; DD=${11:?display device xpu:3|xpu:2}; shift 11
WA=${LTX_RUN_WRITE_ALLOWANCE_GIB-3}
[[ "$WA" =~ ^([1-9]|[1-5][0-9]|6[0-4])$ ]] || { echo 'REFUSE: LTX_RUN_WRITE_ALLOWANCE_GIB must be integer GiB 1..64'; exit 2; }
W=${LTX_STREAM_WORKDIR:-/home/steve/ltx-stream/s125-live01}
DW=${LTX_DISPLAY_WORKER:-serial}
[[ "$DW" == serial || "$DW" == parallel ]] || { echo 'REFUSE: LTX_DISPLAY_WORKER must be serial or parallel'; exit 2; }
GC=${LTX_GC_INTERVAL_SECONDS:-10}
[[ "$GC" == 10 || "$GC" == 60 ]] || { echo 'REFUSE: LTX_GC_INTERVAL_SECONDS must be 10 or 60'; exit 2; }
EXTRA=(--expect-gc-interval-seconds "$GC" --expect-display-worker "$DW" --expect-run-write-allowance-gib "$WA" --expect-aux-residency "${LTX_AUX_RESIDENCY:-legacy}")
if [[ -n "${LTX_DISPLAY_REPLICA_TRANSIENT_GIB:-}" ]]; then
  EXTRA+=(--expect-display-transient-gib "$LTX_DISPLAY_REPLICA_TRANSIENT_GIB")
fi
mkdir -p "$W"
exec systemd-run --user --unit=ltx125-stream-client-20261010 --property=Restart=no --property=KillSignal=SIGINT --property=TimeoutStopSec=960 \
  --property=WorkingDirectory=/home/steve/llm-optimizations/experiments/ltx25-b70/stream \
  --property="StandardOutput=append:$W/client.log" --property="StandardError=append:$W/client.log" \
  --setenv=OMP_NUM_THREADS=2 --setenv=MKL_NUM_THREADS=2 --setenv=PYTHONDONTWRITEBYTECODE=1 \
  /home/steve/.venvs/ltx25-baseline/bin/python -B ltx_continuation_client.py --packet 125 --work-dir "$W" \
  --expect-frames "$FR" --expect-placement two-way20-28 --expect-text-reuse 1 --expect-anchor frame --expect-decoder-graph "$DG" \
  --expect-anchor-decode "$AD" --expect-bencode-overlap "$BO" --expect-prep-ahead "$PA" \
  --expect-snapshot-mode "$SM" --expect-pool-cap-gb "$CAP" \
  --expect-display-device "$DD" --expect-display-schedule "$DS" --expect-anchor-read-ahead "$AR" --expect-snapshot-schedule "$SS" \
  --scenes /home/steve/llm-optimizations/experiments/ltx25-b70/data/stream/kittens-01.json \
  --sink-stats "$W/sink-stats.json" --max-ahead-seconds 60 --delete-consumed-previews --poll 0.05 "${EXTRA[@]}" "$@"
