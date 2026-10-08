#!/usr/bin/env bash
# One two-card R314 server (262K window, drafting, exact prefix cache, tool calling) + the re-verification plan.
# Mirrors the plan-A/E owner argv of 2026-10-06 (context-planA-a1/tp2-planA-w262144-owner.command.json).
set -e
cd /home/steve/b70-optimization-lab
exec systemd-run --user --unit ctx-lme-stage1 --collect -p WorkingDirectory=/home/steve/b70-optimization-lab \
  -E CAMPAIGN_OUT=/mnt/fast-ai/bench-results/context-longmemeval-20261007/campaign \
  -E MU_MODE=serve_run -E MU_RUN_NAME=lme1 -E MU_LONG_MML=131072 -E MU_BATCHED=832 \
  -E MU_IMAGE=neural-download/vllm-openai-xpu:qwen38-fp8-v0290-r314-state-stride \
  -E MU_SPEC_RESUME=1 -E MU_STATE_WIDTH=1 \
  -E MU_SERVE_ARGS="--enable-auto-tool-choice --tool-call-parser=qwen3_coder --reasoning-parser=qwen3" \
  -E MU_LAUNCH_ARGS="--prefix-cache align --overlay b70-prefix-cache-exact --extra-env B70_PREFIX_CACHE_EXACT=1 --serve-arg=--prefix-cache-retention-interval=13312" \
  -E MU_RUN_SCRIPT=/mnt/fast-ai/bench-results/context-longmemeval-20261007/client.sh \
  -E MU_RUN_TIMEOUT=36000 \
  /usr/bin/python3 experiments/qwen38-27b-b70/scripts/run-20261004-fp8-multiuser-campaign.py
