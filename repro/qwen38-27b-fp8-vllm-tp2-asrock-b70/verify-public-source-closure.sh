#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(git -C "${script_dir}" rev-parse --show-toplevel 2>/dev/null) || {
  printf 'ERROR: this verifier must run from a Git clone of b70-optimization-lab\n' >&2
  exit 2
}

required_files=(
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/build-pinned-mtp1-stack.sh
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/verify-image-contract.sh
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/Dockerfile.mtp1-serial-attention
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/build-mtp1-serial-attention-image.sh
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/Dockerfile.mtp1-rebuilt-gdn
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/build-mtp1-rebuilt-gdn-image.sh
  experiments/qwen38-27b-b70/patches/vllm-qwen38-xpu-serial-spec-flash-attn-r38-20260828.patch
  experiments/qwen38-27b-b70/patches/vllm-xpu-kernels-qwen38-dynamic-active-width-serial-gdn-r35-20260828.patch
  experiments/qwen38-27b-b70/patches/vllm-xpu-kernels-qwen38-gdn-split-serial-gates-r50-20260901.patch
  experiments/qwen38-27b-b70/patches/vllm-qwen38-fp8-draft-only-int4-lm-head-r62-20260901.patch
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/Dockerfile.draft-int4-r62
  repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/build-draft-int4-r62-image.sh
  experiments/qwen38-27b-b70/scripts/run-20260901-qwen38-fp8-mtp1-draft-int4-r62-server.sh
  experiments/qwen38-27b-b70/data/2026-09-01-qwen38-fp8-mtp1-draft-int4-r62-prereg.json
  experiments/qwen38-27b-b70/data/2026-09-01-qwen38-fp8-mtp1-draft-int4-r62-diagnostic-result.json
  experiments/qwen38-27b-b70/notes/2026-09-01-qwen38-fp8-mtp1-draft-int4-r62-diagnostic.md
)

failed=0
for relative_path in "${required_files[@]}"; do
  if [[ ! -f "${repo_root}/${relative_path}" ]]; then
    printf 'MISSING %s\n' "${relative_path}" >&2
    failed=1
    continue
  fi
  if ! git -C "${repo_root}" ls-files --error-unmatch -- "${relative_path}" \
      >/dev/null 2>&1; then
    printf 'UNTRACKED %s\n' "${relative_path}" >&2
    failed=1
  fi
done

check_sha256() {
  local expected=$1
  local relative_path=$2
  local actual
  [[ -f "${repo_root}/${relative_path}" ]] || return
  actual=$(sha256sum "${repo_root}/${relative_path}" | awk '{print $1}')
  if [[ "${actual}" != "${expected}" ]]; then
    printf 'HASH MISMATCH %s\n  expected %s\n  actual   %s\n' \
      "${relative_path}" "${expected}" "${actual}" >&2
    failed=1
  fi
}

check_sha256 \
  127b4bc1dc9096e630698202bbc06f74ce4e87f603f3bdc64d09a0dfcc26fe30 \
  experiments/qwen38-27b-b70/patches/vllm-qwen38-xpu-serial-spec-flash-attn-r38-20260828.patch
check_sha256 \
  ad583014c92b8611a9e4e87868a3d492c3b6802ee557814b9ec794f147cd973e \
  experiments/qwen38-27b-b70/patches/vllm-xpu-kernels-qwen38-dynamic-active-width-serial-gdn-r35-20260828.patch
check_sha256 \
  08a3de4f26119c50a23be87004708508eb444fed168175fb65a565e9a90e4033 \
  experiments/qwen38-27b-b70/patches/vllm-xpu-kernels-qwen38-gdn-split-serial-gates-r50-20260901.patch
check_sha256 \
  594ee1a38fef377bba34db98f2fd7f51641ea9697b4bb622c9a54634b0bd87ab \
  experiments/qwen38-27b-b70/patches/vllm-qwen38-fp8-draft-only-int4-lm-head-r62-20260901.patch

if (( failed )); then
  printf '\nSOURCE CLOSURE FAILED\n' >&2
  printf 'Refresh the clone with: git pull --ff-only origin main\n' >&2
  exit 1
fi

printf 'PUBLIC SOURCE CLOSURE PASS\n'
printf 'commit=%s\n' "$(git -C "${repo_root}" rev-parse HEAD)"
printf 'tracked_files=%d\n' "${#required_files[@]}"
printf 'patch_hashes=pass\n'
