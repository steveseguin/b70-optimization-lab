#!/usr/bin/env bash
set -euo pipefail

revision="7c360e1cd4a5168099dbc54d16d929bf6df04990"
archive="${DEEPSEEK_K160_ARCHIVE:-/mnt/usb-models/models/deepseek-v4-flash-k160-${revision}}"
hot_root="${DEEPSEEK_HOT_ROOT:-/mnt/fast-ai/llm-models/deepseek-v4-flash-xpu}"
hot="${hot_root}/k160-${revision}"
verifier="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/verify-k160-artifact.sh"

DEEPSEEK_HF_VERIFY=1 DEEPSEEK_FULL_HASH=1 "${verifier}" "${archive}"
mkdir -p "${hot}"
rsync -a --delete --partial --info=progress2 --exclude='.cache/' "${archive}/" "${hot}/"
DEEPSEEK_HF_VERIFY=0 "${verifier}" "${hot}"

link="${hot_root}/current-k160"
if [[ -e "${link}" && ! -L "${link}" ]]; then
  printf 'refusing to replace non-symlink: %s\n' "${link}" >&2
  exit 1
fi
ln -sfn "${hot}" "${link}"
printf 'hot_model=%s\n' "${hot}"
printf 'current_link=%s\n' "${link}"
