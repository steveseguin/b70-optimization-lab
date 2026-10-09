#!/bin/bash
# Passes --host-umd-overlay through to the hash-validating command printer.
# PRINT ONLY: no eval, Docker operation, device open, or execution switch.
set -euo pipefail
probe_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
exec python3 -B "$probe_dir/container_command.py" "$@"
