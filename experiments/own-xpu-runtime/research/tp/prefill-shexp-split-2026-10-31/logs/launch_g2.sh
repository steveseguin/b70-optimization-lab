#!/usr/bin/env bash
# Gate 2 two-request cases (phase g2): RESET then a second request of 600 / 64 rows, A vs B (OWNRT_PREFILL_SHEXP_SPLIT=1), both ranks.
set -eu
D=/home/steve/llm-optimizations/experiments/own-xpu-runtime/research/tp/prefill-shexp-split-2026-10-31
R1='batched,rows=256,qs,cc,pair=0.3,ctx=131072,mn,xz,ep,rd,sr,hc,gx,eb=rank1'
R0='rows=256,nw,gs,rb,qs,cc,ctx=131072,lb,dc,mn,xz,ko,ep,rd,sr,lt=4,st,gr,rc,hc,db,gx,lp'
ARMS=()
for sp in 600 64; do
  ARMS+=("t$sp-r1-a:1:tpt:16:1100:n:$R1,sp=$sp" "t$sp-r1-b:1:tpt:16:1100:n:$R1,sp=$sp,ss=1")
  ARMS+=("t$sp-r0-a:0:tps:16:1100:hmcn:$R0,sp=$sp" "t$sp-r0-b:0:tps:16:1100:hmcn:$R0,sp=$sp,ss=1")
done
systemd-run --user --unit=tp-pss-g2-20261031 --collect -p Restart=no -p KillMode=process -p LimitNOFILE=1048576 \
  -E DS_RUNS=/dev/shm/prefill-shexp-split-20261031/runs-g2 -E DS_BIN=37ee90a428cd \
  flock -w 60 -E 75 /dev/shm/card23.lock flock -w 60 -E 75 /dev/shm/card27.lock flock -w 60 -E 75 /dev/shm/card43.lock \
  flock -w 60 -E 75 /dev/shm/card47.lock taskset -c 0-3,16-19 bash $D/run_phase.sh g2 "${ARMS[@]}"
