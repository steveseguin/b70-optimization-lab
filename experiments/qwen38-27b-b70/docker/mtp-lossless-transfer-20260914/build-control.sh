#!/usr/bin/env bash
# CPU-only build. Caller owns GPU/service coordination. No pull, restart, or retry.
set -euo pipefail
recipe=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
if [[ -n "${KERNEL_ARTIFACTS_DIR:-}" ]]; then
  artifacts=${KERNEL_ARTIFACTS_DIR}
  python3 - "$artifacts" <<'PY'
import hashlib, json, pathlib, subprocess, sys
root=pathlib.Path(sys.argv[1])
receipt=json.loads((root/'kernel-reuse-identity.json').read_text())
assert receipt['torch_and_native_dependency_hashes_equal'] is True
base='vllm/vllm-openai-xpu@sha256:28915aadfe9665dd70f1cf36e6f7362e25df24e9035785dedd00559652bbef41'
actual=json.loads(subprocess.check_output(['docker','image','inspect',base]))[0]
assert receipt['identities']['new_base']['image_id']==actual['Id']
for name in ('_xpu_C.abi3.so','libgdn_attn_kernels_xe_2.so'):
    assert hashlib.sha256((root/name).read_bytes()).hexdigest()==receipt['kernel_artifact_sha256'][name]
PY
else
  build_root=${BUILD_ROOT:?set BUILD_ROOT to the completed new kernel build directory}
  artifacts="$build_root/compile/install/vllm_xpu_kernels"
fi
context=${CANDIDATE_CONTEXT:?set CANDIDATE_CONTEXT to a new empty directory}
image=${CANDIDATE_IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-mtp-lossless-transfer-20260914-control}
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
echo "Unqualified native-MTP/V1 control built: $image; identity: $context/candidate-image-inspect.json"
