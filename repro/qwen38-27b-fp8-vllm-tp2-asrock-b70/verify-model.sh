#!/usr/bin/env bash
set -euo pipefail

model_dir="${1:-${MODEL_DIR:-}}"
[[ -n "${model_dir}" ]] || {
    printf 'pass the model directory or set MODEL_DIR\n' >&2
    exit 1
}
expected_count=66
expected_bytes=30866866928
expected_manifest=82fb8f84fa117c81c3e8639c4675709dfb667d70ddaa2fd097d35fc37d95453a

[[ -d "${model_dir}" ]] || { printf 'Missing model directory: %s\n' "${model_dir}" >&2; exit 1; }
[[ -f "${model_dir}/config.json" ]] || { printf 'Missing config.json\n' >&2; exit 1; }

count=$(find "${model_dir}" -maxdepth 1 -type f -name '*.safetensors' -printf '.' | wc -c)
bytes=$(find "${model_dir}" -maxdepth 1 -type f -name '*.safetensors' -printf '%s\n' | awk '{n += $1} END {print n + 0}')
manifest=$(cd "${model_dir}" && sha256sum -- *.safetensors | LC_ALL=C sort -k2,2 | sha256sum | awk '{print $1}')

[[ "${count}" == "${expected_count}" ]] || { printf 'Weight-file count mismatch: %s\n' "${count}" >&2; exit 1; }
[[ "${bytes}" == "${expected_bytes}" ]] || { printf 'Weight-byte count mismatch: %s\n' "${bytes}" >&2; exit 1; }
[[ "${manifest}" == "${expected_manifest}" ]] || { printf 'Weight manifest mismatch: %s\n' "${manifest}" >&2; exit 1; }

printf 'model_weight_files=%s\nmodel_weight_bytes=%s\nmodel_manifest_sha256=%s\n' "${count}" "${bytes}" "${manifest}"
