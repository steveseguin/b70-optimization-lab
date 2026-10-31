#!/usr/bin/env bash
# Gate 2 timing + exactness phase g1 (rank harness at 131072, 1100 rows, A/B/U/D x2 per rank, rank-0 pattern m with B).
set -eu
D=/home/steve/llm-optimizations/experiments/own-xpu-runtime/research/tp/prefill-shexp-split-2026-10-31
R1T='batched,rows=256,qs,cc,pair=0.3,ctx=131072,mn,xz,ep,rd,sr,hc,gx,eb=rank1,ht'
R0T='rows=256,nw,gs,rb,qs,cc,ctx=131072,lb,dc,mn,xz,ko,ep,rd,sr,lt=4,st,gr,rc,hc,db,gx,lp,ht'
R0M='rows=256,nw,gs,rb,qs,cc,ctx=131072,lb,dc,mn,xz,ko,ep,rd,sr,lt=4,st,gr,rc,hc,db,gx,lp'
ARMS=()
for i in 1 2; do
  ARMS+=("g-r1-a$i:1:tpt:16:1100:n:$R1T")
  ARMS+=("g-r1-b$i:1:tpt:16:1100:n:$R1T,ss=1$([ $i = 1 ] && echo ,keep || true)")
  ARMS+=("g-r1-u$i:1:tpt:16:1100:n:$R1T,ss=gateup")
  ARMS+=("g-r1-d$i:1:tpt:16:1100:n:$R1T,ss=down")
done
for i in 1 2; do
  ARMS+=("g-r0-a$i:0:tps:16:1100:hmcn:$R0T")
  ARMS+=("g-r0-b$i:0:tps:16:1100:hmcn:$R0T,ss=1$([ $i = 1 ] && echo ,keep || true)")
  ARMS+=("g-r0-u$i:0:tps:16:1100:hmcn:$R0T,ss=gateup")
  ARMS+=("g-r0-d$i:0:tps:16:1100:hmcn:$R0T,ss=down")
done
ARMS+=("g-r0-bm:0:tps:16:1100:m:$R0M,ss=1,keep")
systemd-run --user --unit=tp-pss-g1-20261031 --collect -p Restart=no -p KillMode=process -p LimitNOFILE=1048576 \
  -E DS_RUNS=/dev/shm/prefill-shexp-split-20261031/runs-g1 -E DS_BIN=37ee90a428cd \
  flock -w 60 -E 75 /dev/shm/card23.lock flock -w 60 -E 75 /dev/shm/card27.lock flock -w 60 -E 75 /dev/shm/card43.lock \
  flock -w 60 -E 75 /dev/shm/card47.lock taskset -c 0-3,16-19 bash $D/run_phase.sh g1 "${ARMS[@]}"
