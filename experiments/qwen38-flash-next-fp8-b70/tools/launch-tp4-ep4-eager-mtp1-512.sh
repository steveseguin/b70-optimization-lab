#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
export MTP=1
exec "${script_dir}/launch-tp4-ep4-eager-mtp0-512.sh" "$@"
