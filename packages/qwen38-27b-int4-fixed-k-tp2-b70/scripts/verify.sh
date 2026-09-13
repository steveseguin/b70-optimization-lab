#!/usr/bin/env bash
set -euo pipefail
here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd); repo=$(cd -- "${here}/../../.." && pwd)
export MODEL_MANIFEST=${MODEL_MANIFEST:-${repo}/repro/qwen38-27b-autoround-int4-b70/manifests/model-gptq-relabel-r212.json}
exec "${repo}/tools/container-packet/verify.sh" "$@"
