#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/../.." && pwd)

exec "${repo_root}/experiments/qwen38-27b-b70/scripts/build-w8a16-dynamic-mamba-allocation-image.sh"
