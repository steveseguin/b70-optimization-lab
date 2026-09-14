#!/usr/bin/env bash
# CPU-only build. Caller owns GPU/service coordination. No pull, restart, or retry.
set -euo pipefail
recipe=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
if [[ -n "${KERNEL_ARTIFACTS_DIR:-}" ]]; then
  artifacts=${KERNEL_ARTIFACTS_DIR}
  python3 - "$artifacts" <<'PY'
import hashlib, json, pathlib, sys
root=pathlib.Path(sys.argv[1])
receipt=json.loads((root/'kernel-reuse-identity.json').read_text())
assert receipt['torch_and_native_dependency_hashes_equal'] is True
for name in ('_xpu_C.abi3.so','libgdn_attn_kernels_xe_2.so'):
    assert hashlib.sha256((root/name).read_bytes()).hexdigest()==receipt['kernel_artifact_sha256'][name]
PY
else
  build_root=${BUILD_ROOT:?set BUILD_ROOT to the completed new kernel build directory}
  artifacts="$build_root/compile/install/vllm_xpu_kernels"
fi
context=${CANDIDATE_CONTEXT:?set CANDIDATE_CONTEXT to a new empty directory}
image=${CANDIDATE_IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-amd-transfer-20260914-base}
[[ ! -e "$context" ]] || { echo "CANDIDATE_CONTEXT already exists: $context" >&2; exit 1; }
mkdir -p "$context/kernel-artifacts"
cp "$recipe/Dockerfile" "$recipe/accepted-overlay.patch" "$recipe/upstream-python.sha256" "$recipe/candidate-python.sha256" "$context/"
cp -a "$recipe/../rebase-v0290/draft-shortlists" "$context/"
cp "$artifacts/_xpu_C.abi3.so" "$artifacts/libgdn_attn_kernels_xe_2.so" "$context/kernel-artifacts/"
if [[ -f "$artifacts/kernel-reuse-identity.json" ]]; then
  cp "$artifacts/kernel-reuse-identity.json" "$context/"
fi
(cd "$context" && sha256sum kernel-artifacts/* > kernel-artifacts.sha256)
docker build --network none --pull=false --tag "$image" "$context"
docker image inspect "$image" > "$context/candidate-image-inspect.json"
echo "Unqualified candidate built: $image; identity: $context/candidate-image-inspect.json"
