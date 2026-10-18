#!/usr/bin/env bash
# 2026-10-17 check of the device progress marks in scripts/stress-xccl-allgather.py (notes/2026-10-17-hang-repro.md):
#   M1  2 minutes with --marks: the steps per second against arm A's first two minutes (same seed, same steps)
#   M2  --marks --mismatch-test, 1 minute: rank 1 runs one step that rank 0 never joins, a known hang; the STALL lines
#       must show rank 0 with every issued gather completed and rank 1 stuck at the first gather of the extra step
# Same container, image and oneCCL environment as run-20261017-xccl-stress.sh. Refuses if containers run. After M2:
# both cards' engine registers (no context may be left loaded) and the kernel log since the start.
#   SUDO_ASKPASS=... systemd-run --user --unit=ctx-xccl-marks ... bash run-20261017-xccl-marks.sh
set -uo pipefail
LAB=/home/steve/b70-optimization-lab
S=$LAB/experiments/qwen38-27b-b70/scripts
D=$LAB/experiments/qwen38-27b-b70/data/2026-10-17-xccl-stress
export SUDO_ASKPASS=${SUDO_ASKPASS:?set SUDO_ASKPASS}
FAULT_RE='(xe [0-9a-f:.]+|drm\]).*(Fault response|CAT error|engine reset|gt reset|GPU reset|coredump has been created|Timedout job|timed out|wedged|device lost|failed to respond)|soft lockup'
IMAGE=neural-download/vllm-openai-xpu:qwen38-fp8-v0290-r314-state-stride
say() { echo "### $(date +%H:%M:%S) $*"; }
for i in $(seq 1 720); do systemctl --user is-active --quiet ctx-xccl-stress6 || break; sleep 5; done
systemctl --user is-active --quiet ctx-xccl-stress6 && { say "ctx-xccl-stress6 still running; nothing run"; exit 1; }
[[ -n $(docker ps -q) ]] && { say "containers running; nothing run"; docker ps --format '{{.Names}} {{.Image}}'; exit 1; }
START=$(date '+%F %T')
faults() { sudo -A journalctl -k --since "$START" --no-pager 2>/dev/null | grep -Ei "$FAULT_RE"; }
COMMON_ENV=(-e CCL_ATL_TRANSPORT=ofi -e CCL_RECV=direct -e CCL_SEND=direct
  -e CCL_SYCL_ALLGATHERV_SIMPLE_THRESHOLD=4294967296 -e CCL_SYCL_ALLREDUCE_SIMPLE_THRESHOLD=4294967296
  -e CCL_SYCL_REDUCE_SCATTER_SIMPLE_THRESHOLD=4294967296 -e CCL_TOPO_P2P_ACCESS=1 -e CCL_ZE_IPC_EXCHANGE=pidfd
  -e FI_PROVIDER=tcp -e FI_TCP_IFACE=lo -e PYTORCH_ALLOC_CONF=expandable_segments:True)
run() {  # name minutes args...
  local name=$1 min=$2; shift 2
  say "$name start ($*)"
  docker run --rm --name xccl-stress --device /dev/dri:/dev/dri --group-add render --ipc host --memory 8g --memory-swap 8g \
    --ulimit core=0 --network bridge --cap-add SYS_PTRACE --security-opt label=disable --shm-size 8g "${COMMON_ENV[@]}" \
    -e ONEAPI_DEVICE_SELECTOR=level_zero:0,1 -e ZE_AFFINITY_MASK=0,1 \
    -v "$S/stress-xccl-allgather.py:/tmp/s.py:ro" -v "$D:/out" --workdir /tmp --entrypoint python3 "$IMAGE" \
    -m torch.distributed.run --nproc-per-node 2 --master-addr 127.0.0.1 --master-port 29511 /tmp/s.py --minutes "$min" \
    --report-s 30 --out "/out/xccl-$name.jsonl" "$@" > "$D/xccl-$name.log" 2>&1
  local rc=$?
  grep -E '^XCCL-STRESS|^STALL' "$D/xccl-$name.log" | tail -4
  say "$name finished, rc $rc"
}
run M1 2 --marks
[[ -n $(faults) ]] && { say "kernel fault lines after M1; M2 not run"; faults | head -5; exit 1; }
run M2 1 --marks --mismatch-test
sleep 3
for c in 03 e3; do sudo -A cat /sys/kernel/debug/dri/0000:$c:00.0/gt0/hw_engines > "$D/after-M2-hw-$c.txt" 2>/dev/null; done
for c in 03 e3; do
  echo "card $c: $(awk '/^[a-z]+[0-9]+ \(physical/{e=$1} /CURRENT_LRCA/{printf "%s %s  ", e, $2}' "$D/after-M2-hw-$c.txt")"
done
F=$(faults)
[[ -n $F ]] && { say "GPU FAULT LINES since $START"; echo "$F" | head -8; } || say "kernel log clean since $START"
say "marks check done; cards left empty"
