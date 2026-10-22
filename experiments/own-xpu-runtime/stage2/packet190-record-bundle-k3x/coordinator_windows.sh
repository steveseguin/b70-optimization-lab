#!/usr/bin/env bash
# Coordinator only: admitted packet190-chain-a user unit, no retries.
set -euo pipefail
HERE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
exec /usr/bin/env -i PATH=/usr/bin:/bin OMP_NUM_THREADS=2 LD_LIBRARY_PATH="${LD_LIBRARY_PATH:?closed library path required}" /usr/bin/python3 -B "$HERE/../../ops/packet190-orchestration/chain_entry.py" queue --authorized-device-window "$@"
