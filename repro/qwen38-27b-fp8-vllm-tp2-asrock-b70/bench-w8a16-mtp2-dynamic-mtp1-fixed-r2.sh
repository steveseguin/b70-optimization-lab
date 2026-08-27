#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/../.." && pwd)
out_dir=${OUT_DIR:?set OUT_DIR to a new result directory}
model_dir=${MODEL_DIR:?set MODEL_DIR to the verified Qwen3.8-27B-FP8 directory}
base_url=${BASE_URL:-http://127.0.0.1:18128}
model=${MODEL_NAME:-qwen38-fp8-w8a16-mtp2-dynamic-mtp1-fixed-r2}
container=${CONTAINER_NAME:-qwen38-fp8-w8a16-mtp2-dynamic-mtp1-fixed-r2}
suite=${repo_root}/experiments/qwen38-27b-b70/data/2026-08-25-qwen38-q4km-tp2-http-smallctx-suite.json
harness=${repo_root}/scripts/bench-openai-concurrency-oracle.py
single=${repo_root}/scripts/bench-openai-single-decode.py
sequential_quality=${repo_root}/scripts/qwen38-text-quality-suite.py
sequential_baseline=${repo_root}/experiments/qwen38-27b-b70/data/qwen38-fp8-block-w8a16-mtp2-reuse-screen-20260826-r1/sequential-quality.json
single_gate=${SINGLE_GATE:-82.810053}
c64_gate=${C64_GATE:-875}
run_id=${RUN_ID:-qwen38-dynamic-mtp1-r2}

[[ ! -e "${out_dir}" ]] || { printf 'refusing to overwrite %s\n' "${out_dir}" >&2; exit 1; }
for command_name in curl docker jq python3 sha256sum; do
  command -v "${command_name}" >/dev/null || {
    printf '%s is required\n' "${command_name}" >&2
    exit 1
  }
done
for required in "${suite}" "${harness}" "${single}" "${sequential_quality}" \
  "${sequential_baseline}"; do
  [[ -f "${required}" ]] || { printf 'missing input: %s\n' "${required}" >&2; exit 1; }
done
curl -fsS "${base_url}/health" >/dev/null
mkdir -p "${out_dir}"
curl -fsS "${base_url}/v1/models" >"${out_dir}/models.json"
docker inspect "${container}" >"${out_dir}/docker-inspect.json"

run_concurrency() {
  local concurrency=$1
  local output=$2
  local prefix=$3
  python3 "${harness}" \
    --base-url "${base_url}" --model "${model}" --api-mode completions \
    --suite "${suite}" --concurrency "${concurrency}" --repeats 1 \
    --max-tokens 128 --seed 42 --timeout 600 \
    --request-id-prefix "${prefix}" \
    --request-extra-json '{"ignore_eos":true,"temperature":0}' \
    --return-token-ids --out "${output}"
}

validate_concurrency() {
  local output=$1
  local concurrency=$2
  local expected_tokens=$((concurrency * 128))
  jq -e --argjson concurrency "${concurrency}" \
    --argjson expected_tokens "${expected_tokens}" '
      (.batches | length) == 1 and
      .batches[0].concurrency == $concurrency and
      .batches[0].request_count == $concurrency and
      .batches[0].total_completion_tokens == $expected_tokens and
      .batches[0].completion_tokens_complete == true and
      .batches[0].cached_tokens_all_zero == true and
      .batches[0].cross_base_oracle_collision_count == 0 and
      .batches[0].complete_token_id_identity_all == true
    ' "${output}" >/dev/null
}

# R1 failed at two active requests. This canary is correctness evidence only.
run_concurrency 2 "${out_dir}/excluded-c2-crash-canary.json" "${run_id}-c2"
validate_concurrency "${out_dir}/excluded-c2-crash-canary.json" 2
if [[ "${C2_REQUIRE_ORACLE_EXACT:-0}" == "1" ]]; then
  jq -e '.batches[0].oracle_exact_all == true' \
    "${out_dir}/excluded-c2-crash-canary.json" >/dev/null || {
      exact=$(jq -r \
        '"\(.batches[0].oracle_exact_count)/\(.batches[0].oracle_exact_total)"' \
        "${out_dir}/excluded-c2-crash-canary.json")
      printf 'CLOSED: c2 sequential-oracle agreement is %s, not 2/2\n' \
        "${exact}" >&2
      exit 5
    }
fi
curl -fsS "${base_url}/health" >/dev/null

python3 "${sequential_quality}" \
  --base-url "${base_url}" --model "${model}" --tokenizer "${model_dir}" \
  --timeout 600 --seed 20260609 --repeat-runs 8 --skip-long-context \
  --request-id-prefix "${run_id}-sequential" \
  --baseline-json "${sequential_baseline}" --require-baseline \
  --chat-template-kwargs-json '{"enable_thinking":false}' \
  --output-json "${out_dir}/sequential-quality.json"
jq -e '.pass_all == true and .baseline_match_all == true' \
  "${out_dir}/sequential-quality.json" >/dev/null

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

run_concurrency 64 "${out_dir}/excluded-c64-transition.json" "${run_id}-transition"
validate_concurrency "${out_dir}/excluded-c64-transition.json" 64
run_concurrency 64 "${out_dir}/c64-screen.json" "${run_id}-screen"
validate_concurrency "${out_dir}/c64-screen.json" 64

sha256sum "${suite}" "${harness}" "${single}" "${sequential_quality}" \
  "${sequential_baseline}" \
  >"${out_dir}/input-sha256sums.txt"
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
