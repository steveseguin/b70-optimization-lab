#!/usr/bin/env bash
set -euo pipefail
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
exec "${script_dir}/../qwen38-27b-q4km-tp1-b70/restore-and-build.sh" "$@"
