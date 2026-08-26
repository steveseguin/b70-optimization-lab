#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/../.." && pwd)
out_dir=${OUT_DIR:?set OUT_DIR to a new result directory}
model_dir=${MODEL_DIR:?set MODEL_DIR to the verified Qwen3.8-27B-FP8 directory}
base_url=${BASE_URL:-http://127.0.0.1:18116}
model=${MODEL_NAME:-qwen38-fp8-block-w8a16}
container=${CONTAINER_NAME:-qwen38-fp8-block-w8a16-tp2-p128}
suite=${repo_root}/experiments/qwen38-27b-b70/data/2026-08-25-qwen38-q4km-tp2-http-smallctx-suite.json
oracle=${repo_root}/experiments/qwen38-27b-b70/data/qwen38-fp8-tp2-http-p128-oracle-screen-20260826-r6-attempt1/oracle-digests.json
harness=${repo_root}/scripts/bench-openai-concurrency-oracle.py
single=${repo_root}/scripts/bench-openai-single-decode.py
sequential_quality=${repo_root}/scripts/qwen38-text-quality-suite.py
concurrent_quality=${repo_root}/experiments/qwen38-27b-b70/scripts/qwen38-concurrent-quality-canary.py

[[ ! -e "${out_dir}" ]] || { printf 'refusing to overwrite %s\n' "${out_dir}" >&2; exit 1; }
for required in "${suite}" "${oracle}" "${harness}" "${single}" "${sequential_quality}" "${concurrent_quality}"; do
  [[ -f "${required}" ]] || { printf 'missing input: %s\n' "${required}" >&2; exit 1; }
done
curl -fsS "${base_url}/health" >/dev/null
mkdir -p "${out_dir}"
curl -fsS "${base_url}/v1/models" >"${out_dir}/models.json"
docker inspect "${container}" >"${out_dir}/docker-inspect.json"

python3 "${single}" \
  --base-url "${base_url}" --model "${model}" --api-mode completions \
  --prompt-tokens 32 --prompt-mode default --max-tokens 128 \
  --repeats 5 --seed 1 --timeout 600 \
  --out "${out_dir}/single-p40-o128.json" \
  >"${out_dir}/single-p40-o128.stdout.txt"

python3 "${harness}" \
  --base-url "${base_url}" --model "${model}" --api-mode completions \
  --suite "${suite}" --concurrency 128 --repeats 1 --max-tokens 128 \
  --seed 42 --timeout 600 \
  --request-extra-json '{"ignore_eos":true,"temperature":0}' \
  --return-token-ids --oracle-digests "${oracle}" \
  --out "${out_dir}/excluded-c128-conditioning.json" \
  >"${out_dir}/excluded-c128-conditioning.stdout.txt"

python3 "${harness}" \
  --base-url "${base_url}" --model "${model}" --api-mode completions \
  --suite "${suite}" --concurrency 128 --repeats 5 --max-tokens 128 \
  --seed 42 --timeout 600 \
  --request-extra-json '{"ignore_eos":true,"temperature":0}' \
  --return-token-ids --oracle-digests "${oracle}" \
  --out "${out_dir}/c128-measured-x5.json" \
  >"${out_dir}/c128-measured-x5.stdout.txt"

python3 "${sequential_quality}" \
  --base-url "${base_url}" --model "${model}" --tokenizer "${model_dir}" \
  --timeout 600 --seed 20260609 --repeat-runs 8 \
  --request-id-prefix qwen38-fp8-block-w8a16-sequential \
  --skip-long-context --chat-template-kwargs-json '{"enable_thinking":false}' \
  --output-json "${out_dir}/sequential-quality.json" \
  >"${out_dir}/sequential-quality.stdout.txt"

python3 "${concurrent_quality}" \
  --base-url "${base_url}" --model "${model}" --concurrency 128 \
  --rounds 8 --timeout 600 --seed 42 \
  --request-id-prefix qwen38-fp8-block-w8a16-c128-quality \
  --output-json "${out_dir}/concurrent-quality-1024.json" \
  >"${out_dir}/concurrent-quality-1024.stdout.txt"

sha256sum "${suite}" "${oracle}" "${harness}" "${single}" \
  "${sequential_quality}" "${concurrent_quality}" >"${out_dir}/input-sha256sums.txt"
sha256sum "${out_dir}"/*.json >"${out_dir}/result-sha256sums.txt"
printf 'PASS: %s\n' "${out_dir}"
