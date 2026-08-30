#!/usr/bin/env bash
set -euo pipefail
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo=$(cd -- "${script_dir}/../.." && pwd)
base_url=${BASE_URL:-http://127.0.0.1:18142}
out_dir=${OUT_DIR:?set OUT_DIR to a new result directory}
mtp_depth=${MTP_DEPTH:-2}
oracle_json=${ORACLE_JSON:-}
[[ "${mtp_depth}" == 0 || "${mtp_depth}" == 2 ]] || { printf 'MTP_DEPTH must be 0 or 2\n' >&2; exit 2; }
[[ ! -e "${out_dir}" ]] || { printf 'Refusing to overwrite %s\n' "${out_dir}" >&2; exit 1; }
if [[ "${mtp_depth}" == 2 && -z "${oracle_json}" ]]; then
  printf 'MTP2 validation requires ORACLE_JSON from a fresh package MTP0 run\n' >&2
  exit 2
fi
mkdir -p "${out_dir}"
curl -fsS "${base_url}/health" >"${out_dir}/health.json"
python3 "${repo}/scripts/bench-openai-realistic-suite.py" \
  --base-url "${base_url}" --model "qwen38-q4km-q4mtp-tp2-mtp${mtp_depth}" --api-mode native-raw \
  --suite "${repo}/repro/qwen36-27b-autoround-int4-b70/realistic-suite-v1.json" \
  --max-tokens 512 --metric-tokens 100 --seed 42 --timeout 900 --return-token-ids --require-natural-eos \
  --request-extra-json '{"cache_prompt":false,"seed":42,"temperature":0,"top_p":1}' \
  --out "${out_dir}/performance.json"
python3 "${repo}/scripts/neural-download-canaries.py" --base-url "${base_url}" \
  --model "qwen38-q4km-q4mtp-tp2-mtp${mtp_depth}" --out "${out_dir}/canaries.json"
python3 - "${out_dir}/performance.json" "${out_dir}/canaries.json" "${mtp_depth}" "${oracle_json}" <<'PY'
import json, sys
performance = json.load(open(sys.argv[1]))
canaries = json.load(open(sys.argv[2]))
depth = int(sys.argv[3])
oracle_path = sys.argv[4]
assert performance["realistic_final_gate"]["passed"]
assert performance["fresh_response_validity"]["valid"]
assert performance["realistic_final_gate"]["cached_tokens_all_zero"]
assert canaries["pass_all"]
value = performance["summary"]["class_balanced_tok_s_1_100_intervals_after_ttft"]["median"]
print(f"class_balanced_median_tok_s={value:.12f}")
print("cached_tokens_all_zero=true\ncanaries_passed=true")
if depth == 2:
    oracle = json.load(open(oracle_path))
    left = {row["prompt_id"]: row["token_ids"] for row in performance["rows"]}
    right = {row["prompt_id"]: row["token_ids"] for row in oracle["rows"]}
    assert left == right, "complete token arrays differ from the fresh MTP0 oracle"
    print("target_arrays_exact=12/12")
PY
