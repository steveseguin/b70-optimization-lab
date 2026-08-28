#!/usr/bin/env bash
set -euo pipefail

root="/home/steve/llm-optimizations"
launcher="${root}/experiments/deepseek-v4-flash-reap-xpu-b70/scripts/serve-0731-reap-tp4-target-canary.sh"

export DEEPSEEK_0731_TARGET_PROFILE=full
exec "${launcher}"
