#!/bin/bash
# Invoked only by the future admitted one-launch runner. No installs/compilation.
set -euo pipefail
if [[ "${1:-}" != --execute ]]; then
    printf '%s\n' 'DRY RUN: record installed package versions, then exec /opt/venv/bin/vllm with the supplied serve arguments.'
    exit 0
fi
shift
[[ "${1:-}" == serve && "${2:-}" == /model ]] || exit 2
/opt/venv/bin/python - <<'PY' > /screen/runtime-versions.json
import importlib.metadata as m
import json
from packaging.version import Version
names = ['vllm', 'torch', 'triton', 'vllm-xpu-kernels', 'transformers']
versions = {name: m.version(name) for name in names}
assert Version(versions['vllm']).release[:2] == (0, 30), versions
assert Version(versions['vllm-xpu-kernels']) >= Version('0.1.14.1'), versions
print(json.dumps(versions, indent=2))
PY
exec /opt/venv/bin/vllm "$@"
