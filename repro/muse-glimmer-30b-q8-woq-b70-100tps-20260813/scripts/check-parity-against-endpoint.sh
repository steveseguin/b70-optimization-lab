#!/usr/bin/env bash
set -euo pipefail

base_url=${1:?usage: $0 BASE_URL OUTPUT_JSON [N_PREDICT] [PROMPT]}
output=${2:?usage: $0 BASE_URL OUTPUT_JSON [N_PREDICT] [PROMPT]}
n_predict=${3:-256}
prompt=${4:-}
args=(--base-url "$base_url" --out "$output" --n-predict "$n_predict")
if [[ -n $prompt ]]; then
    args+=(--prompt "$prompt")
fi
exec python3 "$(dirname "$0")/check-spec-parity.py" "${args[@]}"
