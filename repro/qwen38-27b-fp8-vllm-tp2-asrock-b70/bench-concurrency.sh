#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/../.." && pwd)
out_dir=${OUT_DIR:?set OUT_DIR to a new result directory}
base_url=${BASE_URL:-http://127.0.0.1:18089}
model=${MODEL_NAME:-qwen38-fp8}
suite=${SUITE_PATH:-${repo_root}/experiments/qwen38-27b-b70/data/2026-08-25-qwen38-q4km-tp2-http-smallctx-suite.json}
oracle=${ORACLE_DIGESTS:-${repo_root}/experiments/qwen38-27b-b70/data/qwen38-fp8-tp2-http-concurrency-oracle-pilot-20260826-r1-attempt1/oracle-digests.json}
single_client=${repo_root}/scripts/bench-openai-single-decode.py
harness=${repo_root}/scripts/bench-openai-concurrency-oracle.py
qualifier=${repo_root}/scripts/qualify-openai-concurrency-attempt.py

[[ ! -e "${out_dir}" ]] || { printf 'refusing to overwrite %s\n' "${out_dir}" >&2; exit 1; }
[[ -f "${suite}" && -f "${oracle}" && -f "${single_client}" && -f "${harness}" && -f "${qualifier}" ]] || {
  printf 'a required in-repository input is missing\n' >&2
  exit 1
}
curl -fsS "${base_url}/health" >/dev/null
mkdir -p "${out_dir}"

python3 "${single_client}" \
  --base-url "${base_url}" --model "${model}" --api-mode completions \
  --prompt-tokens 128 --prompt-mode filled-fixed-line-unique \
  --max-tokens 128 --repeats 1 --seed 4242 --timeout 600 \
  --out "${out_dir}/excluded-warmup.json" \
  >"${out_dir}/excluded-warmup.stdout.txt"

python3 "${harness}" \
  --base-url "${base_url}" --model "${model}" --api-mode completions \
  --suite "${suite}" --concurrency 1,2,4,8,16,32,64 --repeats 1 \
  --max-tokens 128 --seed 42 --timeout 1800 \
  --request-extra-json '{"ignore_eos":true,"temperature":0}' \
  --return-token-ids --oracle-digests "${oracle}" \
  --out "${out_dir}/result.json" | tee "${out_dir}/harness-summary.txt"

python3 "${qualifier}" \
  --result "${out_dir}/result.json" \
  --out "${out_dir}/qualification.json" \
  --active-slots 4

sha256sum "${suite}" "${oracle}" "${harness}" "${qualifier}" \
  >"${out_dir}/input-sha256sums.txt"
sha256sum "${out_dir}/result.json" "${out_dir}/qualification.json" \
  >"${out_dir}/result-sha256sums.txt"
printf 'PASS: %s\n' "${out_dir}"
