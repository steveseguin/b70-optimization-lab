#!/usr/bin/env bash
# Run only after WS128 finishes. No GPU, service operation or real submission.
set -euo pipefail
HERE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
REPO=$(git -C "$HERE" rev-parse --show-toplevel)
cd "$REPO"
if (( $# > 1 )); then
    echo 'Usage: prepare_submission.sh [new-output-directory-under-submission]' >&2
    exit 2
fi
OUTPUT=${1:-$HERE/prepared}
CPU=(nice -n 19 taskset -c 4-15,20-31 python3 -B)
"${CPU[@]}" scripts/packet49_submission.py --output "$OUTPUT"
"${CPU[@]}" scripts/submit_localmaxxing_results.py --payloads "$OUTPUT/payload-queue.json" --dry-run
"${CPU[@]}" scripts/submit_localmaxxing_results.py --payloads "$OUTPUT/payload-queue.json" --server-dry-run
printf '%s\n' 'Preparation and both dry-runs complete. No real submission performed. Coordinator owns submission.'
