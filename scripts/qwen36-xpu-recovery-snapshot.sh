#!/usr/bin/env bash
set -u

OUT_DIR=""
KILL_VLLM=0
COPY_SMOKE=0
WAIT_SECONDS=5
PYTHON_BIN="${PYTHON_BIN:-/home/steve/.venvs/vllm-xpu/bin/python}"

usage() {
  cat <<'USAGE'
Usage: scripts/qwen36-xpu-recovery-snapshot.sh --out-dir DIR [--kill-vllm] [--copy-smoke] [--wait-seconds N]

Capture XPU/vLLM process state after a runtime failure. By default this is
read-only. Pass --kill-vllm to terminate vLLM serve and worker processes.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --out-dir)
      OUT_DIR="${2:-}"
      shift 2
      ;;
    --kill-vllm)
      KILL_VLLM=1
      shift
      ;;
    --copy-smoke)
      COPY_SMOKE=1
      shift
      ;;
    --wait-seconds)
      WAIT_SECONDS="${2:-5}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ -z "$OUT_DIR" ]]; then
  echo "--out-dir is required" >&2
  usage >&2
  exit 2
fi

mkdir -p "$OUT_DIR"

run_capture() {
  local name="$1"
  shift
  {
    echo "\$ $*"
    "$@"
    local status=$?
    echo "exit_status=$status"
    return "$status"
  } >"$OUT_DIR/$name.txt" 2>&1
}

run_shell_capture() {
  local name="$1"
  shift
  {
    echo "\$ $*"
    bash -lc "$*"
    local status=$?
    echo "exit_status=$status"
    return "$status"
  } >"$OUT_DIR/$name.txt" 2>&1
}

date -Is >"$OUT_DIR/timestamp.txt"
uname -a >"$OUT_DIR/uname.txt" 2>&1 || true

run_capture xpu-smi-version xpu-smi --version || true
run_capture xpu-smi-discovery xpu-smi discovery || true
run_capture xpu-smi-ps xpu-smi ps || true
run_capture xpu-smi-ps-json xpu-smi ps -j || true
run_capture xpu-smi-health-list xpu-smi health -l || true
run_capture xpu-smi-health-list-json xpu-smi health -l -j || true
run_capture xpu-smi-stats xpu-smi stats || true

for device in 0 1 2 3; do
  run_capture "xpu-smi-health-device-${device}-json" xpu-smi health -d "$device" -j || true
  run_capture "xpu-smi-stats-device-${device}-json" xpu-smi stats -d "$device" -j || true
  run_capture "xpu-smi-stats-device-${device}-ras-json" xpu-smi stats -d "$device" -r -j || true
done

run_shell_capture pgrep-before "pgrep -af 'vllm serve|VLLM::Worker|multiprocessing.resource_tracker|qwen36|run-qwen36' || true" || true
run_shell_capture tmux-before "tmux ls 2>/dev/null || true" || true

if [[ "$KILL_VLLM" -eq 1 ]]; then
  run_shell_capture kill-vllm-term "pkill -TERM -f 'vllm serve|VLLM::Worker' || true" || true
  sleep "$WAIT_SECONDS"
  run_shell_capture kill-vllm-kill "pkill -KILL -f 'vllm serve|VLLM::Worker' || true" || true
  sleep 2
fi

run_shell_capture pgrep-after "pgrep -af 'vllm serve|VLLM::Worker|multiprocessing.resource_tracker|qwen36|run-qwen36' || true" || true
run_capture xpu-smi-ps-after xpu-smi ps || true
run_capture xpu-smi-ps-after-json xpu-smi ps -j || true

if [[ "$COPY_SMOKE" -eq 1 ]]; then
  {
    echo "\$ $PYTHON_BIN - <<'PY'"
    "$PYTHON_BIN" - <<'PY'
import json
import time

import torch

started = time.perf_counter()
result = {
    "torch": torch.__version__,
    "xpu_available": torch.xpu.is_available(),
    "device_count": torch.xpu.device_count(),
    "devices": [],
}

for index in range(torch.xpu.device_count()):
    device = torch.device(f"xpu:{index}")
    tensor = torch.arange(4096, dtype=torch.float32, device=device)
    clone = torch.empty_like(tensor)
    clone.copy_(tensor)
    torch.xpu.synchronize(device)
    result["devices"].append({
        "index": index,
        "sum": float(clone.sum().cpu()),
        "last_value": float(clone[-1].cpu()),
    })

result["elapsed_s"] = time.perf_counter() - started
print(json.dumps(result, indent=2, sort_keys=True))
PY
    status=$?
    echo "exit_status=$status"
  } >"$OUT_DIR/xpu-copy-smoke.txt" 2>&1
fi

echo "Wrote XPU recovery snapshot to $OUT_DIR"
