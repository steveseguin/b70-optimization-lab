#!/usr/bin/env bash
set -euo pipefail

llama_server=${LLAMA_SERVER:-}
model=${MODEL:-}
draft=${MTP_DRAFT_MODEL:-}
draft_sha=${DRAFT_SHA256:-}
expected_target_sha=50e180d69641e017d7e08a6f602988effde8232ff6bc0231e839636fdcc03d8f
expected_target_bytes=27636230944
expected_patch_sha=2dab9dce3d6a41cba8edad559eb754088c6f5ca1de6531f408c069e45b7f727a

fail() { printf 'PREFLIGHT FAIL: %s\n' "$*" >&2; exit 1; }
[[ -x ${llama_server} ]] || fail 'set LLAMA_SERVER to the reconstructed llama-server'
[[ -f ${model} ]] || fail 'set MODEL to the UD-Q8_K_XL target GGUF'
[[ -f ${draft} ]] || fail 'set MTP_DRAFT_MODEL to the local Q4_0 MTP GGUF'
[[ ${draft_sha} =~ ^[0-9a-f]{64}$ ]] || fail 'set DRAFT_SHA256 to the digest printed by prepare-draft.sh'
[[ $(stat -c '%s' "${model}") == "${expected_target_bytes}" ]] || fail 'target model byte-size mismatch'
printf '%s  %s\n' "${expected_target_sha}" "${model}" | sha256sum --check --status || fail 'target model SHA-256 mismatch'
printf '%s  %s\n' "${draft_sha}" "${draft}" | sha256sum --check --status || fail 'local draft SHA-256 mismatch'

build_dir=$(cd -- "$(dirname -- "${llama_server}")/.." && pwd)
receipt=${build_dir}/b70-gemma4-record-source.json
[[ -r ${receipt} ]] || fail "missing build receipt: ${receipt}"
command -v jq >/dev/null || fail 'jq is required to check the build receipt'
[[ $(jq -r '.base_commit' "${receipt}") == c926ad09857517978575d6a74d225b463f7417a0 ]] || fail 'build base commit mismatch'
[[ $(jq -r '.aggregate_patch_sha256' "${receipt}") == "${expected_patch_sha}" ]] || fail 'build aggregate patch mismatch'
[[ -r /opt/intel/oneapi/setvars.sh ]] || fail 'Intel oneAPI setvars.sh is missing'
pgrep -x llama-server >/dev/null && fail 'another llama-server is already running'

printf 'PREFLIGHT PASS\nserver=%s\ntarget=%s\ndraft=%s\ndraft_sha256=%s\n' \
  "${llama_server}" "${model}" "${draft}" "${draft_sha}"
