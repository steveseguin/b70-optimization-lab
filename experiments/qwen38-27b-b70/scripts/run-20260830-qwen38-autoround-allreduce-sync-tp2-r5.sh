#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo=$(cd -- "${script_dir}/../../.." && pwd)

exec env \
  CAMPAIGN=qwen38-autoround-allreduce-sync-tp2-20260830-r5 \
  PREREG="${repo}/experiments/qwen38-27b-b70/notes/2026-08-30-qwen38-autoround-allreduce-sync-tp2-r5-prereg.md" \
  "${script_dir}/run-20260830-qwen38-autoround-allreduce-sync-tp2-r4.sh"
