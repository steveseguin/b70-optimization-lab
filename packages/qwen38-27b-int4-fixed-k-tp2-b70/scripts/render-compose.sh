#!/usr/bin/env bash
set -euo pipefail
here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd); repo=$(cd -- "${here}/../../.." && pwd)
PACKAGE_DIR=packages/qwen38-27b-int4-fixed-k-tp2-b70 LAUNCHER=repro/qwen38-27b-autoround-int4-b70/scripts/run-fixed-k-mtp-server.sh SERVED_NAME=qwen38-27b-int4 MODEL_DESC="devan-carlin/Qwen3.8-27B-int4-AutoRound (gptq relabel)" MTP_DEPTH=4 PROFILES="one two" \
exec "${repo}/tools/render-container-packet.sh"
