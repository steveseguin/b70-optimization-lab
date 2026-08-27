#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/../.." && pwd)
out_dir=${OUT_DIR:?set OUT_DIR to a new result directory}
base_url=${BASE_URL:-http://127.0.0.1:18128}
model=${MODEL_NAME:-qwen38-fp8-w8a16-mtp2-dynamic-mamba-r5}
concurrent_quality=${repo_root}/experiments/qwen38-27b-b70/scripts/qwen38-concurrent-quality-canary.py
replication_floor=1033.117768

[[ -f "${concurrent_quality}" ]] || {
  printf 'missing input: %s\n' "${concurrent_quality}" >&2
  exit 1
}

export MODEL_NAME=${model}
export CONTAINER_NAME=${CONTAINER_NAME:-qwen38-fp8-w8a16-mtp2-dynamic-mamba-r5}
"${script_dir}/bench-w8a16-mtp2-dynamic-mamba-r4.sh"

jq -e --argjson floor "${replication_floor}" \
  '.batches[0].aggregate_tok_s_wall >= $floor' \
  "${out_dir}/c64-screen.json" >/dev/null || {
    rate=$(jq -r '.batches[0].aggregate_tok_s_wall' "${out_dir}/c64-screen.json")
    printf 'CLOSED: replication %.6f tok/s is below %.6f\n' \
      "${rate}" "${replication_floor}" >&2
    exit 4
  }

python3 "${concurrent_quality}" \
  --base-url "${base_url}" --model "${model}" --concurrency 64 \
  --rounds 8 --timeout 600 --seed 42 \
  --request-id-prefix qwen38-dynamic-mamba-r5-quality \
  --output-json "${out_dir}/c64-quality-512.json"
jq -e '
  .total_requests == 512 and
  .pass_all == true and
  ([.results[].cached_tokens_nonzero] | all(. == 0))
' "${out_dir}/c64-quality-512.json" >/dev/null
curl -fsS "${base_url}/health" >"${out_dir}/health-after-quality.txt"

sha256sum "${concurrent_quality}" >>"${out_dir}/input-sha256sums.txt"
sort -u "${out_dir}/input-sha256sums.txt" -o "${out_dir}/input-sha256sums.txt"
sha256sum "${out_dir}"/*.json >"${out_dir}/result-sha256sums.txt"
printf 'PASS: fresh-server replication and 512/512 quality canary; %s\n' \
  "${out_dir}"
