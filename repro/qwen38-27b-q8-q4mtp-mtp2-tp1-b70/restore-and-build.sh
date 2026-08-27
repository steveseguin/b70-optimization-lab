#!/usr/bin/env bash
set -euo pipefail

repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
exec "${repo}/repro/qwen38-27b-q8-tp1-b70/restore-and-build.sh" "$@"
