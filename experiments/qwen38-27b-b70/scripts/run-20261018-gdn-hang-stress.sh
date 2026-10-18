#!/usr/bin/env bash
# GDN prompt-kernel hang stress (2026-10-18, registered in notes/2026-10-17-hang-repro.md before any run): one container
# per card at the same time, each calling the fused `_xpu_C.gdn_attention` prompt kernel in layer-50 shapes (TP2
# split, 300-600 new tokens from a cached state) for MINUTES minutes, in the context server's own image. Cards must be
# empty (the mask leaves one device, numbered 0, so the selector is always level_zero:0). A kernel that never finishes shows as `STUCK` in the card's log, then as a driver timeout in the kernel log.
set -uo pipefail
LAB=/home/steve/b70-optimization-lab
S=$LAB/experiments/qwen38-27b-b70/scripts
OUT=${OUT:?set OUT}
MINUTES=${MINUTES:-20}
IMAGE=neural-download/vllm-openai-xpu:qwen38-fp8-v0290-r314-state-stride
FAULT_RE='(xe [0-9a-f:.]+|drm\]).*(Fault response|CAT error|engine reset|gt reset|GPU reset|coredump has been created|Timedout job|timed out|wedged|device lost|failed to respond)'
say() { echo "### $(date +%H:%M:%S) $*"; }
[[ -e $OUT ]] && { say "ABORT: $OUT exists"; exit 2; }
[[ -n $(docker ps -q) ]] && { say "ABORT: a container is running"; exit 2; }
mkdir -p "$OUT"
START=$(date '+%F %T')
say "GDN hang stress: $MINUTES min per card, both cards at once, image $IMAGE; MemAvailable $(awk '/^MemAvailable:/ {printf "%d", $2/1024}' /proc/meminfo) MiB"
pids=()
for c in 0 1; do
  docker run --rm --name gdn-hang-stress-$c --device /dev/dri:/dev/dri --group-add render --memory 4g --memory-swap 4g \
    --ulimit core=0 -e ONEAPI_DEVICE_SELECTOR=level_zero:0 -e ZE_AFFINITY_MASK=$c -e VLLM_TARGET_DEVICE=xpu \
    -v "$S/qwen38-gdn-prefill-hang-stress.py:/stress.py:ro" -v "$OUT:/out" --workdir / --entrypoint python3 "$IMAGE" \
    /stress.py --out /out/card$c.json --minutes "$MINUTES" --seed $((20261018 + c)) > "$OUT/card$c.log" 2>&1 &
  pids+=($!)
done
wait "${pids[@]}"
for c in 0 1; do say "card $c: $(tail -1 "$OUT/card$c.log")"; grep -E "STUCK|SLOW|ERROR" "$OUT/card$c.log" | head -5 | sed 's/^/   /'; done
F=$(sudo -A journalctl -k --since "$START" --no-pager -o short-iso 2>/dev/null | grep -Ei "$FAULT_RE")
if [[ -n $F ]]; then say "GPU FAULT LINES since $START:"; echo "$F" | head -10 | cut -c1-220; echo "$F" > "$OUT/kernel-faults.txt"; else say "kernel log clean since $START"; fi
say "done"
