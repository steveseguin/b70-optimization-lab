#!/usr/bin/env bash
set -euo pipefail

repo="0xSero/DeepSeek-V4-Flash-180B"
revision="7c360e1cd4a5168099dbc54d16d929bf6df04990"
target="${DEEPSEEK_K160_DIR:-/mnt/usb-models/models/deepseek-v4-flash-k160-${revision}}"
hf_home="${HF_HOME:-/mnt/usb-models/llm-cache/hf}"
token_file="${HF_TOKEN_FILE:-/home/steve/.config/huggingface/token}"
hf_cli="${HF_CLI:-/home/steve/.venvs/vllm-xpu/bin/hf}"

test -x "${hf_cli}"
test -s "${token_file}"
mkdir -p "${target}" "${hf_home}"

HF_TOKEN="$(<"${token_file}")" \
HF_HOME="${hf_home}" \
HF_XET_HIGH_PERFORMANCE=1 \
exec "${hf_cli}" download "${repo}" \
  --revision "${revision}" \
  --local-dir "${target}" \
  --max-workers "${HF_MAX_WORKERS:-8}" \
  --quiet
