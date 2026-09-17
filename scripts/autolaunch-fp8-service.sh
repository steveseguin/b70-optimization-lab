#!/usr/bin/env bash
# One-shot restore of the two-card FP8 service after a boot: waits for the model mount and Docker, runs the bounded
# XPU/XCCL health probe, then starts the package launcher once. No retry. Run it by hand after a reboot:
#   nohup scripts/autolaunch-fp8-service.sh &
set -uo pipefail
repo=/home/steve/b70-optimization-lab
out=/mnt/fast-ai/bench-results/service-autolaunch-$(date +%Y%m%dT%H%M%S)
log=/mnt/fast-ai/bench-results/service-autolaunch.log
{
  echo "[$(date -Is)] autolaunch: waiting for mount and docker"
  for i in $(seq 1 60); do mountpoint -q /mnt/fast-ai && docker info >/dev/null 2>&1 && break; sleep 5; done
  echo "[$(date -Is)] autolaunch: health probe"
  if PYTHON=/home/steve/.venvs/vllm-xpu/bin/python timeout 900 bash "$repo/scripts/check-qwen36-xpu-xccl-health.sh"; then
    echo "[$(date -Is)] autolaunch: starting the two-card FP8 service (state $out)"
    cd "$repo" && exec python3 packages/qwen38-27b-fp8-tp2-b70/scripts/serve.py start --model-dir /mnt/fast-ai/llm-models/qwen3.8-27b-fp8 --state-dir "$out" --port 18124
  else
    echo "[$(date -Is)] autolaunch: health probe failed; not starting (user decision)"
  fi
} >> "$log" 2>&1
