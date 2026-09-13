#!/usr/bin/env bash
set -euo pipefail
here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd); repo=$(cd -- "${here}/../../.." && pwd)
export PACKAGE_DIR=packages/qwen38-27b-int4-fixed-k-tp2-b70 SERVED_NAME=qwen38-27b-int4 PACKET_NAME="devan-carlin/Qwen3.8-27B-int4-AutoRound relabelled to plain GPTQ (R212) B70 packet" MODEL_GIB=20
exec "${repo}/tools/container-packet/smoke-test.sh" "$@"
