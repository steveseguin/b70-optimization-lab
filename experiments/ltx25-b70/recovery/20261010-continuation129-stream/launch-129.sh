#!/bin/bash
# Launch packet 129 (continuation stream) as a user unit. Coordinator only; one launch, no retry, no restart loop.
# Usage: launch-129.sh <frames> <anchor> <dg> <ad full|cone> <bo> <pa> <sm walk|fingerprint> <pool cap GB|-> <display sampler-a|sampler-b|eager-display> <read-ahead 0|1> <snapshot full|a-xpu3-sync> <display-device xpu:3|xpu:2> <receipt> [--check-only]
set -euo pipefail
FR=${1:?frames}; AN=${2:?anchor}; DG=${3:?dg}; AD=${4:?ad full|cone}; BO=${5:?bo}; PA=${6:?pa}
SM=${7:?sm walk|fingerprint}; CAP=${8:?pool cap GB or -}; DS=${9:?display schedule}; RA=${10:?read ahead}; SS=${11:?snapshot schedule}; DD=${12:?display device}; REC=${13:?health receipt}; MODE=${14:-launch}
case "$MODE" in launch|--check-only) ;; *) echo "REFUSE: mode must be launch or --check-only"; exit 2 ;; esac
# Optional LTX_DISPLAY_REPLICA_TRANSIENT_GIB increases the length-specific reserve (GiB).
WA=${LTX_RUN_WRITE_ALLOWANCE_GIB-3}
[[ "$WA" =~ ^([1-9]|[1-5][0-9]|6[0-4])$ ]] || { echo 'REFUSE: LTX_RUN_WRITE_ALLOWANCE_GIB must be integer GiB 1..64'; exit 2; }
R=/mnt/fast-ai/bench-results/ltx25-baseline-20260913
P=$R/prepared-continuation-stream-129
MAN=42e6a7452e11873f33c78a953105754605121f2a96dfca1954b1d55966a4886c
case "$FR" in 49|97|121|145|169) ;; *) echo "REFUSE: frames must be 49,97,121,145,169"; exit 2 ;; esac
case "$SM" in walk) SMT=walk ;; fingerprint) SMT=fp ;; *) echo "REFUSE: sm must be walk or fingerprint"; exit 2 ;; esac
NAME=encoder-server-continuation-stream-129-${AN}-dg${DG}-ad${AD}-bo${BO}-pa${PA}-sm${SMT}-two-way20-28-w1-b1-p1-dxpu2-s256x256-f${FR}
case "$DS" in sampler-a|sampler-b|eager-display) ;; *) echo "REFUSE: invalid display schedule"; exit 2 ;; esac
case "$RA" in 0|1) ;; *) echo "REFUSE: invalid read ahead"; exit 2 ;; esac
case "$SS" in full|a-xpu3-sync) ;; *) echo "REFUSE: invalid snapshot schedule"; exit 2 ;; esac
[ "$SS" = a-xpu3-sync ] && [ "$SM" != fingerprint ] && { echo "REFUSE: sparse barriers require fingerprint"; exit 2; }
if [ "$DS/$RA/$SS" != sampler-a/0/full ]; then NAME=${NAME}-ds${DS}-ra${RA}-ss${SS}; fi
case "$DD" in xpu:3|xpu:2) ;; *) echo "REFUSE: invalid display device"; exit 2 ;; esac
if [ "$DD" = xpu:2 ]; then
  case "$FR" in 121|145|169) ;; *) echo "REFUSE: xpu:2 frame scope"; exit 2 ;; esac
  [ "$AN/$AD/$DS" = frame/cone/eager-display ] || { echo "REFUSE: xpu:2 requires frame/cone/eager-display"; exit 2; }
  [ -e $R/display-replica-120-refused.json ] && { echo "REFUSE: display replica latch"; exit 2; }
  NAME=${NAME}-ddxpu2
fi
AUX=${LTX_AUX_RESIDENCY:-legacy}
case "$AUX" in legacy|xpu2) ;; *) echo 'REFUSE: auxiliary residency'; exit 2 ;; esac
if [ "$AUX" = xpu2 ]; then
  [ "$DD" = xpu:3 ] || { echo "REFUSE: auxiliary plus replica workspace"; exit 2; }
  case "$FR/$AN/$DG/$AD" in 145/frame/0/cone|169/frame/0/cone) ;; *) echo 'REFUSE: auxiliary scope'; exit 2 ;; esac
  NAME=${NAME}-auxxpu2
fi
if [ "$FR" = 169 ] && [ "$AUX" != xpu2 ]; then
  [ "$AN/$DG/$AD/$DD/$DS" = frame/0/cone/xpu:2/eager-display ] || { echo 'REFUSE:169 legacy requires dg0 replica'; exit 2; }
fi
[ "$FR" -ge 145 ] && [ "$DG/$DD" = 1/xpu:2 ] && { echo 'REFUSE: graph replica memory'; exit 2; }
DW=${LTX_DISPLAY_WORKER:-serial}
case "$DW" in serial) ;; parallel)
  case "$FR/$AN/$DG/$AD/$DD/$DS/$AUX" in 145/frame/0/cone/xpu:2/eager-display/legacy|169/frame/0/cone/xpu:2/eager-display/legacy) ;;
    *) echo 'REFUSE: parallel display scope'; exit 2 ;; esac
  NAME=${NAME}-dwparallel ;;
  *) echo 'REFUSE: display worker'; exit 2 ;; esac
GC=${LTX_GC_INTERVAL_SECONDS:-10}
case "$GC" in 10) ;; 60)
  [ "$FR/$AN/$DG/$AD/$BO/$PA/$DS/$RA/$SS/$DD/$DW" = 145/frame/0/cone/1/1/sampler-a/0/full/xpu:3/serial ] || { echo 'REFUSE: GC60 scope'; exit 2; }
  NAME=${NAME}-gc60 ;;
  *) echo 'REFUSE: GC interval'; exit 2 ;; esac
SCAN=${LTX_STORAGE_SCAN_MODE:-request}
case "$SCAN" in request) ;; background) NAME=${NAME}-ssbackground ;; *) echo 'REFUSE: storage scan mode'; exit 2 ;; esac
SDC=${LTX_SNAPSHOT_DIGEST_CACHE:-0}
case "$SDC" in 0) ;; 1)
  [ "$FR/$AN/$DG/$AD/$BO/$PA/$SM/$DS/$RA/$SS/$DD/$DW/$AUX" = 145/frame/0/cone/1/1/fingerprint/sampler-a/0/full/xpu:3/serial/legacy ] || { echo 'REFUSE: snapshot digest cache scope'; exit 2; }
  NAME=${NAME}-sdc1 ;;
  *) echo 'REFUSE: snapshot digest cache'; exit 2 ;; esac
MM=${LTX_MAINTENANCE_MODE:-parent}
case "$MM" in parent) ;; idle)
  case "$FR/$AN/$DG/$AD/$BO/$PA/$SM/$RA/$SS/$AUX" in 145/frame/0/cone/1/1/fingerprint/0/full/legacy|169/frame/0/cone/1/1/fingerprint/0/full/legacy) ;;
    *) echo 'REFUSE: idle maintenance scope'; exit 2 ;; esac
  case "$DW/$DD/$DS" in serial/xpu:3/sampler-a|parallel/xpu:2/eager-display) ;;
    *) echo 'REFUSE: idle maintenance display scope'; exit 2 ;; esac
  NAME=${NAME}-mi ;;
  *) echo 'REFUSE: maintenance mode'; exit 2 ;; esac
UNIT=ltx129-stream-server-20261010
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
COLL=$(cd $R && ls output output/validation requests 2>/dev/null | grep -c "^stream129-" || true); [ "$COLL" = 0 ] || { echo "REFUSE: $COLL stream129 names present"; exit 2; }
PYC=$(find $P -name __pycache__ | wc -l); [ "$PYC" = 0 ] || { echo "REFUSE: $PYC __pycache__ in packet"; exit 2; }
[ -s "$REC" ] || { echo "REFUSE: receipt missing"; exit 2; }
$PY -B $P/launch/check-storage-headroom.py $R/$NAME --min-free-bytes 50GiB --planned-write-bytes "${WA}GiB"
ENVS=(LTX_MAINTENANCE_MODE=$MM LTX_SNAPSHOT_DIGEST_CACHE=$SDC LTX_STORAGE_SCAN_MODE=$SCAN LTX_GC_INTERVAL_SECONDS=$GC LTX_DISPLAY_WORKER=$DW LTX_RUN_WRITE_ALLOWANCE_GIB=$WA LTX_AUX_RESIDENCY=$AUX EnableDeferBacking=0 LTX_ANCHOR=$AN LTX_DECODER_GRAPH=$DG LTX_ANCHOR_DECODE=$AD LTX_BENCODE_OVERLAP=$BO LTX_PREP_AHEAD=$PA LTX_SNAPSHOT_MODE=$SM LTX_DISPLAY_SCHEDULE=$DS LTX_DISPLAY_DEVICE=$DD LTX_ANCHOR_READ_AHEAD=$RA LTX_SNAPSHOT_SCHEDULE=$SS OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 LTX_BUSY_WINDOWS=0 LTX_DECODE_REPLICAS=1 LTX_DECODE_REPLICA_DEVICE=xpu:2 LTX_OUTPUT_SIZE=256x256 LTX_SAMPLER_BATCH=1 LTX_SAMPLER_PLACEMENT=two-way20-28 LTX_SAMPLER_SHARED_POOL=1 LTX_SAMPLER_WORKERS=1 LTX_STREAM_FRAMES=$FR LTX_STREAM_TEXT_REUSE=1 NEOReadDebugKeys=1)
if [ "${LTX_DISPLAY_REPLICA_TRANSIENT_GIB+x}" = x ]; then
  [ "$DD" = xpu:2 ] || { echo "REFUSE: replica budget requires xpu:2"; exit 2; }
  ENVS+=(LTX_DISPLAY_REPLICA_TRANSIENT_GIB=$LTX_DISPLAY_REPLICA_TRANSIENT_GIB)
fi
[ "$CAP" != - ] && ENVS+=(LTX_DECODER_GRAPH_POOL_CAP_GB=$CAP)
ARGS=(-B $P/launch/serve-encoder.py --packet $P --manifest-sha256 $MAN --run-name $NAME --health-receipt "$REC")
if [ "$MODE" = --check-only ]; then
  ulimit -Sn 65536
  cd /home/steve/llm-optimizations && exec env -u LTX_DISPLAY_REPLICA_TRANSIENT_GIB -u LTX_DECODER_GRAPH_POOL_CAP_GB "${ENVS[@]}" $PY "${ARGS[@]}" --check-only
fi
systemctl --user reset-failed $UNIT 2>/dev/null || true
exec systemd-run --user --unit=$UNIT --property=Restart=no --property=SendSIGKILL=no --property=KillSignal=SIGINT \
  --property=TimeoutStopSec=180 --property=LimitNOFILE=65536:1048576 --property=WorkingDirectory=/home/steve/llm-optimizations \
  /usr/bin/env --default-signal=INT -u LTX_DISPLAY_REPLICA_TRANSIENT_GIB -u LTX_DECODER_GRAPH_POOL_CAP_GB "${ENVS[@]}" $PY "${ARGS[@]}"
