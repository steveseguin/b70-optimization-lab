#!/bin/bash
# Launch packet 117 (continuation stream) as a user unit. Usage: launch-117.sh <frames> <anchor> <dg> <ad> <bo> <pa> <receipt> [--check-only]
set -euo pipefail
FR=${1:?frames}; AN=${2:?anchor}; DG=${3:?dg}; AD=${4:?ad full|cone}; BO=${5:?bo}; PA=${6:?pa}; REC=${7:?health receipt}; MODE=${8:-launch}
R=/mnt/fast-ai/bench-results/ltx25-baseline-20260913
P=$R/prepared-continuation-stream-117
MAN=5826174ee3a3965d033758de006552742878f624800dadb90423879b3f0802c9
NAME=encoder-server-continuation-stream-117-${AN}-dg${DG}-ad${AD}-bo${BO}-pa${PA}-two-way20-28-w1-b1-p1-dxpu2-s256x256-f${FR}
UNIT=ltx117-stream-server-20261008
PY=/home/steve/.venvs/ltx25-baseline/bin/python
[ -e $R/FAULT.json ] && { echo "REFUSE: FAULT.json present"; exit 2; }
for L in decoder-graph-116-refused.json anchor-decode-117-refused.json precompute-117-refused.json; do [ -e $R/$L ] && { echo "REFUSE: latch $L"; exit 2; }; done
ss -ltn | grep -q ':8188 ' && { echo "REFUSE: port 8188 busy"; exit 2; }
systemctl --user is-active --quiet $UNIT && { echo "REFUSE: unit $UNIT active"; exit 2; }
[ -e $R/$NAME ] && { echo "REFUSE: run dir exists $NAME"; exit 2; }
COLL=$(cd $R && ls output output/validation requests 2>/dev/null | grep -c "^stream117-" || true); [ "$COLL" = 0 ] || { echo "REFUSE: $COLL stream117 names present"; exit 2; }
PYC=$(find $P -name __pycache__ | wc -l); [ "$PYC" = 0 ] || { echo "REFUSE: $PYC __pycache__ in packet"; exit 2; }
[ -s "$REC" ] || { echo "REFUSE: receipt missing"; exit 2; }
$PY -B $P/launch/check-storage-headroom.py $R/$NAME --min-free-bytes 50GiB --planned-write-bytes 3GiB
ENVS=(EnableDeferBacking=0 LTX_ANCHOR=$AN LTX_DECODER_GRAPH=$DG LTX_ANCHOR_DECODE=$AD LTX_BENCODE_OVERLAP=$BO LTX_PREP_AHEAD=$PA LTX_BUSY_WINDOWS=0 LTX_DECODE_REPLICAS=1 LTX_DECODE_REPLICA_DEVICE=xpu:2 LTX_OUTPUT_SIZE=256x256 LTX_SAMPLER_BATCH=1 LTX_SAMPLER_PLACEMENT=two-way20-28 LTX_SAMPLER_SHARED_POOL=1 LTX_SAMPLER_WORKERS=1 LTX_STREAM_FRAMES=$FR LTX_STREAM_TEXT_REUSE=1 NEOReadDebugKeys=1)
ARGS=(-B $P/launch/serve-encoder.py --packet $P --manifest-sha256 $MAN --run-name $NAME --health-receipt "$REC")
if [ "$MODE" = --check-only ]; then
  ulimit -Sn 65536
  cd /home/steve/llm-optimizations && exec env "${ENVS[@]}" $PY "${ARGS[@]}" --check-only
fi
systemctl --user reset-failed $UNIT 2>/dev/null || true
exec systemd-run --user --unit=$UNIT --property=Restart=no --property=SendSIGKILL=no --property=KillSignal=SIGINT \
  --property=TimeoutStopSec=180 --property=LimitNOFILE=65536:1048576 --property=WorkingDirectory=/home/steve/llm-optimizations \
  /usr/bin/env --default-signal=INT "${ENVS[@]}" $PY "${ARGS[@]}"
