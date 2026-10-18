#!/usr/bin/env bash
# 2026-10-17 the two-card exchange at the server's sizes (registered in notes/2026-10-17-hang-repro.md before it
# ran): scripts/stress-xccl-allgather.py under torch.distributed.run, one process per card, the context-lane server's
# oneCCL/libfabric environment, R314 image, no model. Arms, MINUTES each, in order, stopping at the first hang:
#   A  the exchange alone
#   B  the same while scripts/load-card-bursts.py loads card 03:00.0 in bursts (the desktop's card)
#   C  B plus CCL_SYCL_ALLGATHERV_CHUNKING_THRESHOLD=1048576 (every LL256 ring call within oneCCL's 1 MiB default)
# Waits for the packed first-step stress unit to end; refuses if containers run or the kernel logged a fault since
# that unit started (read the evidence first). On a STALL line from the client: every thread's kernel state and both
# cards' engine registers; on the first kernel fault line: every card's device coredump.
#   SUDO_ASKPASS=... [ARMS="A B"] [MINUTES=20] systemd-run --user --unit=ctx-xccl-stress ... bash run-20261017-xccl-stress.sh
set -uo pipefail
LAB=/home/steve/b70-optimization-lab
S=$LAB/experiments/qwen38-27b-b70/scripts
D=$LAB/experiments/qwen38-27b-b70/data/2026-10-17-xccl-stress
export SUDO_ASKPASS=${SUDO_ASKPASS:?set SUDO_ASKPASS}
FAULT_RE='(xe [0-9a-f:.]+|drm\]).*(Fault response|CAT error|engine reset|gt reset|GPU reset|coredump has been created|Timedout job|timed out|wedged|device lost|failed to respond)|soft lockup'
IMAGE=neural-download/vllm-openai-xpu:qwen38-fp8-v0290-r314-state-stride
say() { echo "### $(date +%H:%M:%S) $*"; }
mkdir -p "$D"
for i in $(seq 1 1800); do systemctl --user is-active --quiet ctx-hang-repro2 || break; sleep 5; done
systemctl --user is-active --quiet ctx-hang-repro2 && { say "ctx-hang-repro2 still running; nothing run"; exit 1; }
[[ -n $(docker ps -q) ]] && { say "containers running; nothing run"; docker ps --format '{{.Names}} {{.Image}}'; exit 1; }
F=$(sudo -A journalctl -k --since "2026-10-17 13:39:00" --no-pager 2>/dev/null | grep -Ei "$FAULT_RE")
[[ -n $F ]] && { say "kernel fault lines since the stress started; nothing run (read them first)"; echo "$F" | head -5; exit 1; }
ARMS=${ARMS:-A B}
MIN=${MINUTES:-20}
START=$(date '+%F %T')
say "exchange stress: arms $ARMS, $MIN min each; MemAvailable $(awk '/MemAvailable/{print int($2/1024)}' /proc/meminfo) MiB"
faults() { sudo -A journalctl -k --since "$START" --no-pager 2>/dev/null | grep -Ei "$FAULT_RE"; }
watch_arm() {  # arm: STALL -> thread states once; kernel fault -> coredumps once
  local arm=$1 stalled=0
  while [[ ! -e $D/.done-$arm ]]; do
    if (( ! stalled )) && grep -q '^STALL' "$D/xccl-$arm.log" 2>/dev/null; then
      stalled=1
      sudo -A bash -c 'for p in $(docker top xccl-stress -eo pid,args | awk "NR>1 && /python3/ {print \$1}"); do
        for t in /proc/$p/task/*; do echo "$p ${t##*/} $(cat $t/comm) wchan=$(cat $t/wchan) syscall=$(cut -d" " -f1-3 $t/syscall)"
          head -12 $t/stack | sed "s/^/    /"; done; done' > "$D/stall-tasks-$arm.txt" 2>&1
      sudo -A cat /sys/kernel/debug/dri/0000:03:00.0/gt0/hw_engines > "$D/stall-hw-03-$arm.txt" 2>/dev/null
      sudo -A cat /sys/kernel/debug/dri/0000:e3:00.0/gt0/hw_engines > "$D/stall-hw-e3-$arm.txt" 2>/dev/null
      say "STALL on $arm: thread states and engine registers saved"
    fi
    if [[ -n $(faults) ]]; then
      sleep 4
      for c in /sys/class/drm/card*/device; do
        p=$(basename "$(readlink -f "$c")")
        [[ -e $c/devcoredump/data ]] && sudo -A cat "$c/devcoredump/data" > "$D/devcoredump-$p-$arm.txt" 2>/dev/null
      done
      sudo -A journalctl -k --since "$START" --no-pager -o short-precise > "$D/kernel-$arm.txt" 2>/dev/null
      say "kernel fault on $arm: coredumps copied ($(ls "$D" | grep -c "devcoredump-.*-$arm") files)"
      break
    fi
    sleep 2
  done
}
COMMON_ENV=(-e CCL_ATL_TRANSPORT=ofi -e CCL_RECV=direct -e CCL_SEND=direct
  -e CCL_SYCL_ALLGATHERV_SIMPLE_THRESHOLD=4294967296 -e CCL_SYCL_ALLREDUCE_SIMPLE_THRESHOLD=4294967296
  -e CCL_SYCL_REDUCE_SCATTER_SIMPLE_THRESHOLD=4294967296 -e CCL_TOPO_P2P_ACCESS=1 -e CCL_ZE_IPC_EXCHANGE=pidfd
  -e FI_PROVIDER=tcp -e FI_TCP_IFACE=lo -e PYTORCH_ALLOC_CONF=expandable_segments:True)
rc=0
for arm in $ARMS; do
  extra=()
  [[ $arm == C ]] && extra=(-e CCL_SYCL_ALLGATHERV_CHUNKING_THRESHOLD=1048576)
  LOADER=
  if [[ $arm == B || $arm == C ]]; then
    docker run --rm --name card03-load --device /dev/dri:/dev/dri --group-add render --memory 3g --ulimit core=0 \
      --network none -e ONEAPI_DEVICE_SELECTOR=level_zero:0 -e ZE_AFFINITY_MASK=0 \
      -v "$S/load-card-bursts.py:/tmp/l.py:ro" --workdir /tmp --entrypoint python3 "$IMAGE" /tmp/l.py --device 0 \
      --minutes "$((MIN + 2))" > "$D/load-$arm.log" 2>&1 &
    LOADER=$!
    sleep 20
    grep -m1 'LOAD on' "$D/load-$arm.log" || { say "card 03 load did not start on $arm"; cat "$D/load-$arm.log" | tail -3; }
  fi
  say "arm $arm start"
  watch_arm "$arm" &
  WD=$!
  docker run --rm --name xccl-stress --device /dev/dri:/dev/dri --group-add render --ipc host --memory 8g --memory-swap 8g \
    --ulimit core=0 --network bridge --cap-add SYS_PTRACE --security-opt label=disable --shm-size 8g "${COMMON_ENV[@]}" "${extra[@]}" \
    -e ONEAPI_DEVICE_SELECTOR=level_zero:0,1 -e ZE_AFFINITY_MASK=0,1 \
    -v "$S/stress-xccl-allgather.py:/tmp/s.py:ro" -v "$D:/out" --workdir /tmp --entrypoint python3 "$IMAGE" \
    -m torch.distributed.run --nproc-per-node 2 --master-addr 127.0.0.1 --master-port 29511 /tmp/s.py --minutes "$MIN" --out "/out/xccl-$arm.jsonl" \
    > "$D/xccl-$arm.log" 2>&1
  rc=$?
  touch "$D/.done-$arm"; sleep 3; kill $WD 2>/dev/null
  if [[ -n $LOADER ]]; then docker stop -t 5 card03-load >/dev/null 2>&1; wait $LOADER 2>/dev/null; tail -1 "$D/load-$arm.log"; fi
  grep -E '^XCCL-STRESS|^STALL' "$D/xccl-$arm.log" | tail -3
  say "arm $arm finished, rc $rc"
  if (( rc != 0 )) || grep -q '^STALL' "$D/xccl-$arm.log" || [[ -n $(faults) ]]; then
    say "arm $arm did not finish cleanly: stopping here (evidence in $D)"; break
  fi
done
F=$(faults)
[[ -n $F ]] && { say "GPU FAULT LINES since $START"; echo "$F" | head -8; } || say "kernel log clean since $START"
say "exchange stress done; cards left empty"
