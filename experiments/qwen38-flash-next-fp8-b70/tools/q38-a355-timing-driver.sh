#!/usr/bin/env bash
# A355 driver: MTP1 promoted line + VLLM_XPU_GDN_SERIAL_SPEC_DECODE_VIEWS=1, step timing.
set -Eeuo pipefail
exec "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/q38-timing-driver.sh" 355 19968 mtp1 3
