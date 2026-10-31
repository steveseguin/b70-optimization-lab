#!/usr/bin/env bash
# Gate 3: decode-half hard gate, the new binary's default path (no OWNRT_PREFILL_SHEXP_SPLIT) vs r3 4128ad66dd3c,
# interleaved x2 per rank, 64 halves each, lane flags (tptsxqckhcbgl) on both.
set -eu
D=/home/steve/llm-optimizations/experiments/own-xpu-runtime/research/tp/prefill-shexp-split-2026-10-31
R1T='batched,rows=256,qs,cc,pair=0.3,ctx=131072,mn,xz,ep,rd,sr,hc,gx,eb=rank1,ht'
R0T='rows=256,nw,gs,rb,qs,cc,ctx=131072,lb,dc,mn,xz,ko,ep,rd,sr,lt=4,st,gr,rc,hc,db,gx,lp,ht'
ARMS=()
for i in 1 2; do
  ARMS+=("d-r1-r3-$i:1:tpt:64:1100:n:$R1T,launch=4128ad66dd3c" "d-r1-n-$i:1:tpt:64:1100:n:$R1T")
done
for i in 1 2; do
  ARMS+=("d-r0-r3-$i:0:tps:64:1100:hmcn:$R0T,launch=4128ad66dd3c" "d-r0-n-$i:0:tps:64:1100:hmcn:$R0T")
done
systemd-run --user --unit=tp-pss-d1-20261031 --collect -p Restart=no -p KillMode=process -p LimitNOFILE=1048576 \
  -E DS_RUNS=/dev/shm/prefill-shexp-split-20261031/runs-d1 -E DS_BIN=37ee90a428cd \
  flock -w 60 -E 75 /dev/shm/card23.lock flock -w 60 -E 75 /dev/shm/card27.lock flock -w 60 -E 75 /dev/shm/card43.lock \
  flock -w 60 -E 75 /dev/shm/card47.lock taskset -c 0-3,16-19 bash $D/run_phase.sh d1 "${ARMS[@]}"
