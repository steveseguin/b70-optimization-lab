#!/bin/bash
# PRINT ONLY. No Docker execution, device open, server or automatic next arm.
set -euo pipefail
probe_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
exec python3 -B "$probe_dir/first_forward_command.py" "$@"
