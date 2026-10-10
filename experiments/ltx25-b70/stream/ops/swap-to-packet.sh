#!/bin/bash
# Coordinator command; never called automatically after a failure.
set -euo pipefail
HERE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]:?}")" && pwd)
export OMP_NUM_THREADS=2 PYTHONDONTWRITEBYTECODE=1
exec nice -n 19 python3 -B "${HERE:?}/stream_ops.py" swap "$@"
