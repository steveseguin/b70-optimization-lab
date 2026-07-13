#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
echo "run-gdn-qkvz-comparator.sh now delegates to the QKVZAB folded-gate superset" >&2
exec "${ROOT}/run-gdn-qkvzab-comparator.sh" "$@"
