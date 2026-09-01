#!/usr/bin/env bash
set -euo pipefail

# Profile-neutral front door for the strict natural-512 suite. The historical
# filename is retained behind this wrapper so existing experiment receipts do
# not break.
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
exec "${script_dir}/bench-w8a16-mtp1-strict.sh" "$@"
