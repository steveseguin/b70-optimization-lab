#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
# Q8_0 was qualified with the same complete source identity as the Q4_K_M TP1
# package. Delegate by a repository-relative path so its patch order and hashes
# have one maintained source of truth.
exec "${script_dir}/../qwen38-27b-q4km-tp1-b70/restore-and-build.sh" "$@"
