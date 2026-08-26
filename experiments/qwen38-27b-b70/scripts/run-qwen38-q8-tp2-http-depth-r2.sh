#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)

PROFILE=q8 exec "${script_dir}/run-qwen38-q4km-tp2-http-depth-r1.sh"
