#!/bin/bash
# Only the future admitted Screen 1b launch invokes --execute. No installs/build.
set -euo pipefail
if [[ "${1:-}" != --execute ]]; then
    printf '%s\n' 'DRY RUN: verify/apply the pinned Screen 1b Python overlay, record versions, then exec vLLM.'
    exit 0
fi
shift
[[ "${1:-}" == serve && "${2:-}" == /model ]] || exit 2
# NEO reads these in each process before device initialization. This changes
# allocation backing only, never host settings or peer-sharing policy.
[[ "${NEOReadDebugKeys:-}" == 1 && "${EnableDeferBacking:-}" == 0 ]] || {
    echo 'Screen 1b requires NEOReadDebugKeys=1 EnableDeferBacking=0' >&2; exit 2;
}
[[ "${B70_SCREEN1B:-}" == 1 ]] || { echo 'Screen 1b guard must be enabled' >&2; exit 2; }
# All aliases agree before any Python import, including image-level defaults.
for allocator_env in PYTORCH_ALLOC_CONF PYTORCH_CUDA_ALLOC_CONF PYTORCH_HIP_ALLOC_CONF; do
    [[ "${!allocator_env:-}" == pinned_max_round_threshold_mb:1,pinned_max_cached_size_mb:1 ]] || {
        echo "Screen 1b requires exact large pinned allocations: $allocator_env" >&2; exit 2;
    }
done
[[ ! -e /screen/STOP ]] || { echo 'Screen 1b cancellation is latched' >&2; exit 2; }
# Required native-FP8 mmap contract is sealed with the overlay. No table rewrite.
[[ "${VLLM_USE_V2_MODEL_RUNNER:-}" == 1 ]] || { echo 'mmap PLE needs the V2 pre-forward hook' >&2; exit 2; }
# Apply before any vLLM import. Official container Python tree only, never a host venv.
/opt/venv/bin/python /screen-package/apply_overlay.py \
    --root /opt/venv/lib/python3.12/site-packages > /screen/overlay-application.json
/opt/venv/bin/python - <<'PY' > /screen/runtime-versions.json
import importlib.metadata as m
import json
from packaging.version import Version
names = ['vllm', 'torch', 'triton', 'vllm-xpu-kernels', 'transformers']
versions = {name: m.version(name) for name in names}
assert Version(versions['torch']).release[:2] == (2, 13), versions
assert Version(versions['vllm']).release[:2] == (0, 30), versions
assert Version(versions['vllm-xpu-kernels']) >= Version('0.1.14.1'), versions
print(json.dumps(versions, indent=2))
PY
[[ ! -e /screen/STOP ]] || exit 2
exec /opt/venv/bin/vllm "$@"
