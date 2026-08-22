#!/usr/bin/env bash
set -euo pipefail

f16_draft=${F16_DRAFT:-}
q4_draft=${MTP_DRAFT_MODEL:-}
quantize=${LLAMA_QUANTIZE:-}
expected_f16_sha=36bf2f6710cf06ff1a5d026cca49ba88bd3451d8588a484ca5a79c5e30aa45f2
expected_f16_bytes=855228576
reference_q4_sha=1f6706e4a09524c7aa83cea45eec637cd3e2aa7ccfa80c2dbef7a092ec0fddbd
reference_q4_bytes=321126560

[[ -f ${f16_draft} ]] || { printf 'Set F16_DRAFT to the pinned F16 MTP GGUF.\n' >&2; exit 2; }
[[ -n ${q4_draft} ]] || { printf 'Set MTP_DRAFT_MODEL to a new Q4_0 output path.\n' >&2; exit 2; }
[[ -x ${quantize} ]] || { printf 'Set LLAMA_QUANTIZE to the reconstructed build binary.\n' >&2; exit 2; }
[[ ! -e ${q4_draft} ]] || { printf 'Refusing to overwrite: %s\n' "${q4_draft}" >&2; exit 2; }

[[ $(stat -c '%s' "${f16_draft}") == "${expected_f16_bytes}" ]] || {
    printf 'F16 draft byte-size mismatch.\n' >&2
    exit 1
}
printf '%s  %s\n' "${expected_f16_sha}" "${f16_draft}" | sha256sum --check --status || {
    printf 'F16 draft SHA-256 mismatch.\n' >&2
    exit 1
}
mkdir -p "$(dirname -- "${q4_draft}")"
"${quantize}" "${f16_draft}" "${q4_draft}" Q4_0

draft_sha=$(sha256sum "${q4_draft}" | awk '{print $1}')
draft_bytes=$(stat -c '%s' "${q4_draft}")
reference_match=false
if [[ ${draft_sha} == "${reference_q4_sha}" && ${draft_bytes} == "${reference_q4_bytes}" ]]; then
    reference_match=true
fi
printf 'MTP_DRAFT_MODEL=%s\nDRAFT_SHA256=%s\nDRAFT_BYTES=%s\n' \
  "${q4_draft}" "${draft_sha}" "${draft_bytes}"
printf 'RECONSTRUCTED_REFERENCE_MATCH=%s\n' "${reference_match}"
printf 'This identifies the reconstructed local draft; it does not prove historical byte identity.\n'
