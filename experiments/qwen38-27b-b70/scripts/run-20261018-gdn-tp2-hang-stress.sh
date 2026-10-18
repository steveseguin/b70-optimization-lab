#!/usr/bin/env bash
# Two-card GDN hang stress (2026-10-18, registered in notes/2026-10-17-hang-repro.md before any run): one container
# with both cards, two torchrun ranks, the context server's image, docker flags and oneCCL environment; each step runs
# LAYERS GDN-layer stand-ins (projection, fused prompt kernel, projection, all-gather all-reduce) on 300-600 tokens.
# Compute queues have no job timeout, so a hung step never ends by itself: on the first `STUCK` line the runner reads
# both cards' engine states (debugfs, read-only), copies any coredump, then kills the container. Cards must be empty.
set -uo pipefail
LAB=/home/steve/b70-optimization-lab
S=$LAB/experiments/qwen38-27b-b70/scripts
OUT=${OUT:?set OUT}
MINUTES=${MINUTES:-20}
LAYERS=${LAYERS:-16}
IMAGE=neural-download/vllm-openai-xpu:qwen38-fp8-v0290-r314-state-stride
NAME=gdn-tp2-hang-stress
FAULT_RE='(xe [0-9a-f:.]+|drm\]).*(Fault response|CAT error|engine reset|gt reset|GPU reset|coredump has been created|Timedout job|timed out|wedged|device lost|failed to respond)'
say() { echo "### $(date +%H:%M:%S) $*"; }
[[ -e $OUT ]] && { say "ABORT: $OUT exists"; exit 2; }
[[ -n $(docker ps -q) ]] && { say "ABORT: a container is running"; exit 2; }
mkdir -p "$OUT"
START=$(date '+%F %T')
say "GDN TP2 hang stress: $MINUTES min, $LAYERS layers per step, image $IMAGE; MemAvailable $(awk '/^MemAvailable:/ {printf "%d", $2/1024}' /proc/meminfo) MiB"
docker run -d --rm --name $NAME --network bridge --device /dev/dri --group-add render --ipc host --cap-add SYS_PTRACE \
  --shm-size 8g --memory 8g --memory-swap 8g --ulimit core=0 --security-opt label=disable \
  -e ONEAPI_DEVICE_SELECTOR=level_zero:0,1 -e ZE_AFFINITY_MASK=0,1 -e VLLM_TARGET_DEVICE=xpu \
  -e CCL_ATL_TRANSPORT=ofi -e CCL_RECV=direct -e CCL_SEND=direct -e CCL_TOPO_P2P_ACCESS=1 -e CCL_ZE_IPC_EXCHANGE=pidfd \
  -e CCL_SYCL_ALLGATHERV_SIMPLE_THRESHOLD=4294967296 -e CCL_SYCL_ALLREDUCE_SIMPLE_THRESHOLD=4294967296 \
  -e CCL_SYCL_REDUCE_SCATTER_SIMPLE_THRESHOLD=4294967296 -e FI_PROVIDER=tcp -e FI_TCP_IFACE=lo \
  -e PYTORCH_ALLOC_CONF=expandable_segments:True \
  -v "$S/qwen38-gdn-tp2-hang-stress.py:/stress.py:ro" -v "$OUT:/out" --workdir / --entrypoint python3 "$IMAGE" \
  -m torch.distributed.run --nproc-per-node 2 --master-addr 127.0.0.1 --master-port 29511 \
  /stress.py --out /out/rank.json --minutes "$MINUTES" --layers "$LAYERS" > "$OUT/container-id.txt" || { say "docker run failed"; exit 1; }
# each rank writes /out/rank<r>.json
docker logs -f $NAME > "$OUT/stress.log" 2>&1 &
deadline=$((SECONDS + 60 * MINUTES + 300))
result=ended
while docker ps -q --filter name=^/$NAME$ | grep -q .; do
  if grep -qE "STUCK rank|ERROR rank" "$OUT/stress.log"; then
    result=stuck; say "STUCK or ERROR line: reading engine states"
    for c in /sys/kernel/debug/dri/0000:03:00.0 /sys/kernel/debug/dri/0000:e3:00.0; do
      sudo -A cat "$c/gt0/hw_engines" > "$OUT/hw_engines-$(basename $c).txt" 2>&1
    done
    sleep 20
    for c in /sys/kernel/debug/dri/0000:03:00.0 /sys/kernel/debug/dri/0000:e3:00.0; do
      sudo -A cat "$c/gt0/hw_engines" > "$OUT/hw_engines-$(basename $c)-plus20s.txt" 2>&1
    done
    docker kill $NAME > /dev/null 2>&1; break
  fi
  (( SECONDS > deadline )) && { result=overtime; say "past the deadline; killing"; docker kill $NAME > /dev/null 2>&1; break; }
  sleep 2
done
sleep 5
say "result: $result"
grep -E "(STUCK|SLOW|ERROR|done) rank" "$OUT/stress.log" | head -10 | sed 's/^/   /'
for d in /sys/class/drm/card*/device/devcoredump/data; do  # only dumps taken during this run (older ones linger)
  [[ -e $d ]] || continue
  snap=$(sudo -A grep -m1 -oP 'Snapshot time: \K[0-9]+' "$d")
  (( ${snap:-0} >= $(date -d "$START" +%s) )) && sudo -A cat "$d" > "$OUT/devcoredump-$(echo $d | grep -oE 'card[0-9]+').txt"
done
F=$(sudo -A journalctl -k --since "$START" --no-pager -o short-iso 2>/dev/null | grep -Ei "$FAULT_RE")
if [[ -n $F ]]; then say "GPU FAULT LINES since $START:"; echo "$F" | head -10 | cut -c1-220; echo "$F" > "$OUT/kernel-faults.txt"; else say "kernel log clean since $START"; fi
say "done"
