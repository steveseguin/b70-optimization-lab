#!/usr/bin/env bash
# Bounded multi-GPU Level Zero context probe for community PR #9.
#
# Scope: this probe does NOT run the contributed recipe. It loads no model,
# serves no endpoint, and produces no throughput number. It answers one
# question only: does the container's Level Zero runtime create a context over
# two B70s on this host, which is the failure another contributor reported at
# `urContextCreate(.DeviceCount = 2) -> UR_RESULT_ERROR_UNKNOWN`.
#
# Three arms:
#   A  control, single GPU  (ZE_AFFINITY_MASK=0)   expected to succeed
#   B  candidate, two GPUs  (ZE_AFFINITY_MASK=0,1) the reported failure
#   C  arm B again under SYCL_UR_TRACE=2 to localize the failing UR call
#
# `--privileged` is deliberately NOT used; the recipe's own use of it is a
# review finding. Device access is granted with --device and keep-groups only.

set -uo pipefail

IMAGE="docker.io/intel/llm-scaler-vllm:0.21.0-b1"
OUT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_TAG="probe-$(date -u +%Y%m%dT%H%M%SZ)"

run_arm() {
  local name="$1" mask="$2" trace="$3" script="$4"
  echo "=== ARM ${name} | ZE_AFFINITY_MASK=${mask} | SYCL_UR_TRACE=${trace} ==="
  timeout 600 podman run --rm \
    --device /dev/dri \
    --group-add keep-groups \
    --ipc=host \
    -e ZE_AFFINITY_MASK="${mask}" \
    -e ONEAPI_DEVICE_SELECTOR="level_zero:*" \
    -e SYCL_UR_TRACE="${trace}" \
    --entrypoint /bin/bash \
    "${IMAGE}" -lc "${script}" 2>&1
  echo "ARM ${name} EXIT=$?"
}

PY_PROBE='python3 -c "
import torch
print(\"torch\", torch.__version__)
print(\"xpu available:\", torch.xpu.is_available())
n = torch.xpu.device_count()
print(\"xpu device_count:\", n)
for i in range(n):
    print(\"  device\", i, torch.xpu.get_device_name(i))
if n >= 2:
    a = torch.ones(1024, device=\"xpu:0\")
    b = torch.ones(1024, device=\"xpu:1\")
    torch.xpu.synchronize()
    print(\"two-device alloc OK:\", float(a.sum()), float(b.sum()))
"'

{
  echo "probe run: ${RUN_TAG}"
  echo "image: ${IMAGE}"
  echo "host kernel: $(uname -r)"
  echo "host driver module: $(lsmod | awk '/^(xe|i915) /{print $1}' | tr '\n' ' ')"
  echo "host runtime: $(dpkg -l 2>/dev/null | awk '/libze-intel-gpu1|intel-opencl-icd/{print $2"="$3}' | tr '\n' ' ')"
  echo "podman: $(podman --version)"
  echo

  echo "--- container runtime identity ---"
  timeout 300 podman run --rm --entrypoint /bin/bash "${IMAGE}" -lc \
    'dpkg -l 2>/dev/null | grep -E "libze-intel-gpu1|intel-opencl-icd|level-zero" | awk "{print \$2, \$3}"' 2>&1
  echo

  run_arm A "0"   "0" "${PY_PROBE}"
  echo
  run_arm B "0,1" "0" "${PY_PROBE}"
  echo
  run_arm C "0,1" "2" 'python3 -c "import torch; print(torch.xpu.device_count())" 2>&1 | grep -E "urDeviceGet|urContextCreate|urPlatformGet|UR_RESULT|Error|error" | head -40'
} | tee "${OUT}/${RUN_TAG}.log"

echo
echo "log written to ${OUT}/${RUN_TAG}.log"
