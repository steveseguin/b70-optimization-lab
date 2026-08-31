#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
disallowed_boot_id=4136985e-4d03-45f1-8ecd-5b465b32e8d1
current_boot_id=$(</proc/sys/kernel/random/boot_id)
if [[ "$current_boot_id" == "$disallowed_boot_id" ]]; then
  printf 'D62 is forbidden in the D61 device-loss boot; reboot first\n' >&2
  exit 2
fi

export CAMPAIGN_ID=qwen38-prefill-projection-repair-tp2-mtp1-sync-20260831-d62
export CONTAINER_NAME=q38-prefill-projection-repair-tp2-mtp1-sync-d62
export PORT=18363
export TENSOR_PARALLEL_SIZE=2
export GPU_MASK=0,1
export ONEAPI_SELECTOR=level_zero:0,1
export CONTAINER_MEMORY=13g
export MAX_NUM_BATCHED_TOKENS=256
export VLLM_XPU_QWEN38_PREFILL_PROJECTION_SYNCHRONIZE=1
export VLLM_XPU_QWEN38_PREFILL_SMALL_PAD_TOKENS=512
export SPECULATIVE_CONFIG_JSON='{"method":"qwen3_next_mtp","num_speculative_tokens":1}'
export PREREG_PATH="$script_dir/../notes/2026-08-31-qwen38-prefill-projection-repair-tp2-mtp1-sync-d62-prereg.md"
export REFERENCE_PERFORMANCE=/mnt/fast-ai/bench-results/qwen38-prefill-projection-repair-tp2-strict-20260831-d59r/performance.json
exec "$script_dir/run-20260831-qwen38-prefill-projection-repair-strict-d54.sh"
