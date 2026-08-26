#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/../.." && pwd)
out_dir=${OUT_DIR:?set OUT_DIR to a new result directory}
base_url=${BASE_URL:-http://127.0.0.1:18128}
model=${MODEL_NAME:-qwen38-fp8-w8a16-mtp2-dynamic-mtp1-fixed-r3-p192}
container=${CONTAINER_NAME:-qwen38-fp8-w8a16-mtp2-dynamic-mtp1-fixed-r3-p192}
suite=${repo_root}/experiments/qwen38-27b-b70/data/2026-08-25-qwen38-q4km-tp2-http-smallctx-suite.json
harness=${repo_root}/scripts/bench-openai-concurrency-oracle.py
single=${repo_root}/scripts/bench-openai-single-decode.py
single_gate=82.810053
c64_gate=875

[[ ! -e "${out_dir}" ]] || { printf 'refusing to overwrite %s\n' "${out_dir}" >&2; exit 1; }
for command_name in curl docker jq python3 sha256sum; do
  command -v "${command_name}" >/dev/null || {
    printf '%s is required\n' "${command_name}" >&2
    exit 1
  }
done
for required in "${suite}" "${harness}" "${single}"; do
  [[ -f "${required}" ]] || { printf 'missing input: %s\n' "${required}" >&2; exit 1; }
done
curl -fsS "${base_url}/health" >/dev/null
mkdir -p "${out_dir}"
curl -fsS "${base_url}/v1/models" >"${out_dir}/models.json"
docker inspect "${container}" >"${out_dir}/docker-inspect.json"

run_c64() {
  local output=$1
  local prefix=$2
  python3 "${harness}" \
    --base-url "${base_url}" --model "${model}" --api-mode completions \
    --suite "${suite}" --concurrency 64 --repeats 1 \
    --max-tokens 128 --seed 42 --timeout 600 \
    --request-id-prefix "${prefix}" \
    --request-extra-json '{"ignore_eos":true,"temperature":0}' \
    --return-token-ids --out "${output}"
  jq -e '
    (.batches | length) == 1 and
    .batches[0].concurrency == 64 and
    .batches[0].request_count == 64 and
    .batches[0].total_completion_tokens == 8192 and
    .batches[0].completion_tokens_complete == true and
    .batches[0].cached_tokens_all_zero == true and
    .batches[0].cross_base_oracle_collision_count == 0 and
    .batches[0].complete_token_id_identity_all == true
  ' "${output}" >/dev/null
}

python3 "${single}" \
  --base-url "${base_url}" --model "${model}" --api-mode completions \
  --prompt-tokens 32 --prompt-mode default --max-tokens 128 \
  --repeats 1 --seed 1 --timeout 600 \
  --out "${out_dir}/excluded-single-conditioning.json"
python3 "${single}" \
  --base-url "${base_url}" --model "${model}" --api-mode completions \
  --prompt-tokens 32 --prompt-mode default --max-tokens 128 \
  --repeats 5 --seed 1 --timeout 600 \
  --out "${out_dir}/single-p40-o128.json"
jq -e --argjson gate "${single_gate}" '
  (.rows | length) == 5 and
  .rows[0].completion_tokens == 128 and
  .rows[0].usage.prompt_tokens_details.cached_tokens == 0 and
  .rows[0].tok_s_after_ttft >= $gate
' "${out_dir}/single-p40-o128.json" >/dev/null

run_c64 "${out_dir}/excluded-c64-transition.json" qwen38-dynamic-mtp1-r3-p192-transition
run_c64 "${out_dir}/c64-screen.json" qwen38-dynamic-mtp1-r3-p192-screen

sha256sum "${suite}" "${harness}" "${single}" >"${out_dir}/input-sha256sums.txt"
sha256sum "${out_dir}"/*.json >"${out_dir}/result-sha256sums.txt"

c64_rate=$(jq -r '.batches[0].aggregate_tok_s_wall' "${out_dir}/c64-screen.json")
if ! jq -e --argjson gate "${c64_gate}" \
  '.batches[0].aggregate_tok_s_wall >= $gate' \
  "${out_dir}/c64-screen.json" >/dev/null; then
  printf 'CLOSED: declared c64 %.6f tok/s is below %.6f\n' \
    "${c64_rate}" "${c64_gate}" >&2
  exit 3
fi
printf 'PASS: declared c64 %.6f tok/s; %s\n' "${c64_rate}" "${out_dir}"
