#!/bin/bash
# Launch packet 120 (continuation stream) as a user unit. Coordinator only; one launch, no retry, no restart loop.
# Usage: launch-120.sh <frames> <anchor> <dg> <ad full|cone> <bo> <pa> <sm walk|fingerprint> <pool cap GB|-> <display sampler-a|sampler-b|eager-display> <read-ahead 0|1> <snapshot full|a-xpu3-sync> <display-device xpu:3|xpu:2> <receipt> [--check-only]
set -euo pipefail
FR=${1:?frames}; AN=${2:?anchor}; DG=${3:?dg}; AD=${4:?ad full|cone}; BO=${5:?bo}; PA=${6:?pa}
SM=${7:?sm walk|fingerprint}; CAP=${8:?pool cap GB or -}; DS=${9:?display schedule}; RA=${10:?read ahead}; SS=${11:?snapshot schedule}; DD=${12:?display device}; REC=${13:?health receipt}; MODE=${14:-launch}
case "$MODE" in launch|--check-only) ;; *) echo "REFUSE: mode must be launch or --check-only"; exit 2 ;; esac
R=/mnt/fast-ai/bench-results/ltx25-baseline-20260913
P=$R/prepared-continuation-stream-120
MAN=9af9330b7b9f08ad5c3b88d38b5c3f66186fab583d3b810afad7f0d61c5c328e
case "$SM" in walk) SMT=walk ;; fingerprint) SMT=fp ;; *) echo "REFUSE: sm must be walk or fingerprint"; exit 2 ;; esac
NAME=encoder-server-continuation-stream-120-${AN}-dg${DG}-ad${AD}-bo${BO}-pa${PA}-sm${SMT}-two-way20-28-w1-b1-p1-dxpu2-s256x256-f${FR}
case "$DS" in sampler-a|sampler-b|eager-display) ;; *) echo "REFUSE: invalid display schedule"; exit 2 ;; esac
case "$RA" in 0|1) ;; *) echo "REFUSE: invalid read ahead"; exit 2 ;; esac
case "$SS" in full|a-xpu3-sync) ;; *) echo "REFUSE: invalid snapshot schedule"; exit 2 ;; esac
[ "$SS" = a-xpu3-sync ] && [ "$SM" != fingerprint ] && { echo "REFUSE: sparse barriers require fingerprint"; exit 2; }
if [ "$DS/$RA/$SS" != sampler-a/0/full ]; then NAME=${NAME}-ds${DS}-ra${RA}-ss${SS}; fi
case "$DD" in xpu:3|xpu:2) ;; *) echo "REFUSE: invalid display device"; exit 2 ;; esac
if [ "$DD" = xpu:2 ]; then
  [ "$FR/$AN/$AD/$DS" = 121/frame/cone/eager-display ] || { echo "REFUSE: xpu:2 requires frame/cone/eager-display"; exit 2; }
  [ -e $R/display-replica-120-refused.json ] && { echo "REFUSE: display replica latch"; exit 2; }
  NAME=${NAME}-ddxpu2
fi
UNIT=ltx120-stream-server-20261010
PY=/home/steve/.venvs/ltx25-baseline/bin/python
[ -e $R/FAULT.json ] && { echo "REFUSE: FAULT.json present"; exit 2; }
# Latches (the server's check_control_environment repeats these per lever, also in --check-only).
[ "$DG" = 1 ] && [ -e $R/decoder-graph-116-refused.json ] && { echo "REFUSE: latch decoder-graph-116-refused.json"; exit 2; }
if [ "$AD" = cone ]; then for L in anchor-decode-117-refused.json anchor-decode-118-refused.json; do
  [ -e $R/$L ] && { echo "REFUSE: latch $L"; exit 2; }; done; fi
if [ "$BO" = 1 ] || [ "$PA" = 1 ]; then for L in precompute-117-refused.json precompute-118-refused.json; do
  [ -e $R/$L ] && { echo "REFUSE: latch $L"; exit 2; }; done; fi
[ "$SM" = fingerprint ] && [ -e $R/snapshot-118-refused.json ] && { echo "REFUSE: latch snapshot-118-refused.json"; exit 2; }
if [ "$CAP" != - ] && [ "$DG" != 1 ]; then echo "REFUSE: a pool cap needs dg1"; exit 2; fi
ss -ltn | grep -q ':8188 ' && { echo "REFUSE: port 8188 busy"; exit 2; }
systemctl --user is-active --quiet $UNIT && { echo "REFUSE: unit $UNIT active"; exit 2; }
[ -e $R/$NAME ] && { echo "REFUSE: run dir exists $NAME"; exit 2; }
# Collision preflight on the RESULTS ROOT (where the server creates names), not on the packet.
COLL=$(cd $R && ls output output/validation requests 2>/dev/null | grep -c "^stream120-" || true); [ "$COLL" = 0 ] || { echo "REFUSE: $COLL stream120 names present"; exit 2; }
PYC=$(find $P -name __pycache__ | wc -l); [ "$PYC" = 0 ] || { echo "REFUSE: $PYC __pycache__ in packet"; exit 2; }
[ -s "$REC" ] || { echo "REFUSE: receipt missing"; exit 2; }
$PY -B $P/launch/check-storage-headroom.py $R/$NAME --min-free-bytes 50GiB --planned-write-bytes 3GiB
ENVS=(EnableDeferBacking=0 LTX_ANCHOR=$AN LTX_DECODER_GRAPH=$DG LTX_ANCHOR_DECODE=$AD LTX_BENCODE_OVERLAP=$BO LTX_PREP_AHEAD=$PA LTX_SNAPSHOT_MODE=$SM LTX_DISPLAY_SCHEDULE=$DS LTX_DISPLAY_DEVICE=$DD LTX_ANCHOR_READ_AHEAD=$RA LTX_SNAPSHOT_SCHEDULE=$SS OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 LTX_BUSY_WINDOWS=0 LTX_DECODE_REPLICAS=1 LTX_DECODE_REPLICA_DEVICE=xpu:2 LTX_OUTPUT_SIZE=256x256 LTX_SAMPLER_BATCH=1 LTX_SAMPLER_PLACEMENT=two-way20-28 LTX_SAMPLER_SHARED_POOL=1 LTX_SAMPLER_WORKERS=1 LTX_STREAM_FRAMES=$FR LTX_STREAM_TEXT_REUSE=1 NEOReadDebugKeys=1)
[ "$CAP" != - ] && ENVS+=(LTX_DECODER_GRAPH_POOL_CAP_GB=$CAP)
ARGS=(-B $P/launch/serve-encoder.py --packet $P --manifest-sha256 $MAN --run-name $NAME --health-receipt "$REC")
if [ "$MODE" = --check-only ]; then
  ulimit -Sn 65536
  cd /home/steve/llm-optimizations && exec env -u LTX_DECODER_GRAPH_POOL_CAP_GB "${ENVS[@]}" $PY "${ARGS[@]}" --check-only
fi
systemctl --user reset-failed $UNIT 2>/dev/null || true
exec systemd-run --user --unit=$UNIT --property=Restart=no --property=SendSIGKILL=no --property=KillSignal=SIGINT \
  --property=TimeoutStopSec=180 --property=LimitNOFILE=65536:1048576 --property=WorkingDirectory=/home/steve/llm-optimizations \
  /usr/bin/env --default-signal=INT -u LTX_DECODER_GRAPH_POOL_CAP_GB "${ENVS[@]}" $PY "${ARGS[@]}"
