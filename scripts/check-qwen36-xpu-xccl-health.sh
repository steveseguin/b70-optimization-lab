#!/usr/bin/env bash
set -uo pipefail

ROOT="${ROOT:-/home/steve/llm-optimizations}"
PYTHON="${PYTHON:-/home/steve/.venvs/vllm-xpu/bin/python}"
PHYSICAL_DEVICES="${PHYSICAL_DEVICES:-0,1,2,3}"
XCCL_DEVICES="${XCCL_DEVICES:-$PHYSICAL_DEVICES}"
XCCL_NPROC="${XCCL_NPROC:-}"
TIMEOUT_S="${TIMEOUT_S:-90}"

IFS=',' read -r -a physical <<<"$PHYSICAL_DEVICES"
IFS=',' read -r -a xccl_devices <<<"$XCCL_DEVICES"
if [[ -z "$XCCL_NPROC" ]]; then
  XCCL_NPROC="${#xccl_devices[@]}"
fi

overall_rc=0

echo "[xpu-health] physical_devices=$PHYSICAL_DEVICES"
for dev in "${physical[@]}"; do
  echo "[xpu-health] single-device smoke level_zero:$dev"
  if ! ONEAPI_DEVICE_SELECTOR="level_zero:$dev" timeout 20s "$PYTHON" - <<'PY'; then
import torch

print("device_count", torch.xpu.device_count(), flush=True)
torch.xpu.set_device(0)
x = torch.ones((1024, 1024), device="xpu")
y = float((x + 1).sum().cpu().item())
torch.xpu.synchronize()
print("ok", y, flush=True)
PY
    echo "[xpu-health] single-device smoke FAILED for physical device $dev" >&2
    overall_rc=1
  fi
done

echo "[xpu-health] xccl_devices=$XCCL_DEVICES nproc=$XCCL_NPROC"
if ! ONEAPI_DEVICE_SELECTOR="level_zero:$XCCL_DEVICES" \
  ZE_AFFINITY_MASK="$XCCL_DEVICES" \
  CCL_ATL_TRANSPORT="${CCL_ATL_TRANSPORT:-ofi}" \
  CCL_TOPO_P2P_ACCESS="${CCL_TOPO_P2P_ACCESS:-1}" \
  FI_TCP_IFACE="${FI_TCP_IFACE:-eth1}" \
  CCL_KVS_IFACE="${CCL_KVS_IFACE:-eth1}" \
  timeout "$TIMEOUT_S"s "$PYTHON" -m torch.distributed.run \
    --standalone \
    --nproc_per_node="$XCCL_NPROC" \
    "$ROOT/tools/xccl_probe.py" allreduce; then
  echo "[xpu-health] XCCL all-reduce FAILED for devices $XCCL_DEVICES" >&2
  overall_rc=1
fi

exit "$overall_rc"
