#!/bin/bash
# Prepared command only: run by the coordinator at an authorized launch.
# Usage: start-client-138.sh <frames> <dg> <ad> <bo> <pa> <sm> <cap|none> <display> <read-ahead> <snapshots> <display-device> [client args]
set -euo pipefail
FR=${1:?frames}; DG=${2:?dg 0|1}; AD=${3:?ad}; BO=${4:?bo}; PA=${5:?pa}; SM=${6:?snapshot mode}; CAP=${7:?cap GB or none}
DS=${8:?sampler-a|sampler-b|eager-display}; AR=${9:?anchor read-ahead 0|1}; SS=${10:?full|a-xpu3-sync}; DD=${11:?display device xpu:3|xpu:2}; shift 11
WA=${LTX_RUN_WRITE_ALLOWANCE_GIB-3}
[[ "$WA" =~ ^([1-9]|[1-5][0-9]|6[0-4])$ ]] || { echo 'REFUSE: LTX_RUN_WRITE_ALLOWANCE_GIB must be integer GiB 1..64'; exit 2; }
W=${LTX_STREAM_WORKDIR:-/home/steve/ltx-stream/s138-live01}
DW=${LTX_DISPLAY_WORKER:-serial}
[[ "$DW" == serial || "$DW" == parallel ]] || { echo 'REFUSE: LTX_DISPLAY_WORKER must be serial or parallel'; exit 2; }
GC=${LTX_GC_INTERVAL_SECONDS:-10}
[[ "$GC" == 10 || "$GC" == 60 ]] || { echo 'REFUSE: LTX_GC_INTERVAL_SECONDS must be 10 or 60'; exit 2; }
SCAN=${LTX_STORAGE_SCAN_MODE:-request}
[[ "$SCAN" == request || "$SCAN" == background ]] || { echo 'REFUSE: LTX_STORAGE_SCAN_MODE must be request or background'; exit 2; }
CACHE=${LTX_SNAPSHOT_DIGEST_CACHE:-0}
[[ "$CACHE" == 0 || "$CACHE" == 1 ]] || { echo 'REFUSE: LTX_SNAPSHOT_DIGEST_CACHE must be0 or1'; exit 2; }
MAINT=${LTX_MAINTENANCE_MODE:-parent}
[[ "$MAINT" == parent || "$MAINT" == idle ]] || { echo 'REFUSE: LTX_MAINTENANCE_MODE must be parent or idle'; exit 2; }
RELEASE=${LTX_DISPLAY_ALLOCATOR_RELEASE:-off}
[[ "$RELEASE" == off || "$RELEASE" == before-admission ]] || { echo 'REFUSE: LTX_DISPLAY_ALLOCATOR_RELEASE must be off or before-admission'; exit 2; }
CONE=${LTX_CONE_GRAPH_MEMORY:-off}
[[ "$CONE" == off || "$CONE" == replica-release || "$CONE" == text-shift ]] || { echo 'REFUSE: LTX_CONE_GRAPH_MEMORY must be off, replica-release or text-shift'; exit 2; }
AUDIO=${LTX_AUDIO_RESIDENCY:-legacy}
[[ "$AUDIO" == legacy || "$AUDIO" == xpu2 ]] || { echo 'REFUSE: LTX_AUDIO_RESIDENCY must be legacy or xpu2'; exit 2; }
RESERVE=${LTX_CONE_CAPTURE_RESERVE:-parent}
[[ "$RESERVE" == parent ]] || { echo 'REFUSE: capture reserve requires parent; scaled-476 awaits measured145 evidence'; exit 2; }
TEXT=${LTX_TEXT_RESIDENCY:-legacy}
[[ "$TEXT" == legacy || "$TEXT" == split36 ]] || { echo 'REFUSE: LTX_TEXT_RESIDENCY must be legacy or split36'; exit 2; }
F32=${LTX_EXPECT_F32_SCAN:-parent}
[[ "$F32" == parent || "$F32" == bulk ]] || { echo 'REFUSE: LTX_EXPECT_F32_SCAN must be parent or bulk'; exit 2; }
PACING=${LTX_CLIENT_PACING_LOG:-precise}
[[ "$PACING" == legacy || "$PACING" == precise ]] || { echo 'REFUSE: LTX_CLIENT_PACING_LOG must be legacy or precise'; exit 2; }
PREFETCH=${LTX_EXPECT_TEXT_PREFETCH:-off}
[[ "$PREFETCH" == off || "$PREFETCH" == scheduled ]] || { echo 'REFUSE: LTX_EXPECT_TEXT_PREFETCH must be off or scheduled'; exit 2; }
EXTRA=(--expect-text-prefetch "$PREFETCH" --pacing-log "$PACING" --expect-f32-scan "$F32" --expect-text-residency "$TEXT" --expect-audio-residency "$AUDIO" --expect-cone-capture-reserve "$RESERVE" --expected-cone-graph-memory "$CONE" --expect-display-allocator-release "$RELEASE" --expect-maintenance-mode "$MAINT" --expect-snapshot-digest-cache "$CACHE" --expect-storage-scan-mode "$SCAN" --expect-gc-interval-seconds "$GC" --expect-display-worker "$DW" --expect-run-write-allowance-gib "$WA" --expect-aux-residency "${LTX_AUX_RESIDENCY:-legacy}")
if [[ -n "${LTX_DISPLAY_REPLICA_TRANSIENT_GIB:-}" ]]; then
  EXTRA+=(--expect-display-transient-gib "$LTX_DISPLAY_REPLICA_TRANSIENT_GIB")
fi
mkdir -p "$W"
exec systemd-run --user --unit=ltx138-stream-client-20261010 --property=Restart=no --property=KillSignal=SIGINT --property=SendSIGKILL=no --property=KillMode=control-group --property=TimeoutStopSec=960 \
  --property=WorkingDirectory=/home/steve/llm-optimizations/experiments/ltx25-b70/stream \
  --property="StandardOutput=append:$W/client.log" --property="StandardError=append:$W/client.log" \
  --setenv=OMP_NUM_THREADS=2 --setenv=MKL_NUM_THREADS=2 --setenv=PYTHONDONTWRITEBYTECODE=1 \
  /home/steve/.venvs/ltx25-baseline/bin/python -B ltx_continuation_client.py --packet 138 --work-dir "$W" \
  --expect-frames "$FR" --expect-placement two-way20-28 --expect-text-reuse 1 --expect-anchor frame --expect-decoder-graph "$DG" \
  --expect-anchor-decode "$AD" --expect-bencode-overlap "$BO" --expect-prep-ahead "$PA" \
  --expect-snapshot-mode "$SM" --expect-pool-cap-gb "$CAP" \
  --expect-display-device "$DD" --expect-display-schedule "$DS" --expect-anchor-read-ahead "$AR" --expect-snapshot-schedule "$SS" \
  --scenes /home/steve/llm-optimizations/experiments/ltx25-b70/data/stream/kittens-01.json \
  --sink-stats "$W/sink-stats.json" --max-ahead-seconds 60 --delete-consumed-previews --poll 0.05 "${EXTRA[@]}" "$@"
