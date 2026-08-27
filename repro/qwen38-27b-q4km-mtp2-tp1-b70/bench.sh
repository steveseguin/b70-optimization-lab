#!/usr/bin/env bash
set -euo pipefail
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo=$(cd -- "${script_dir}/../.." && pwd)
base_url=${BASE_URL:-http://127.0.0.1:18139}
out_dir=${OUT_DIR:?set OUT_DIR to a new result directory}
[[ ! -e "${out_dir}" ]] || { printf 'Refusing to overwrite %s\n' "${out_dir}" >&2; exit 1; }
mkdir -p "${out_dir}"
curl -fsS "${base_url}/health" >"${out_dir}/health.json"
python3 "${repo}/scripts/bench-openai-realistic-suite.py" \
  --base-url "${base_url}" --model qwen38-q4km-q4mtp-tp1-mtp2 --api-mode native-raw \
  --suite "${repo}/repro/qwen36-27b-autoround-int4-b70/realistic-suite-v1.json" \
  --max-tokens 512 --metric-tokens 100 --seed 42 --timeout 900 --return-token-ids --require-natural-eos \
  --request-extra-json '{"cache_prompt":false,"seed":42,"temperature":0,"top_p":1}' \
  --out "${out_dir}/performance.json"
python3 "${repo}/scripts/neural-download-canaries.py" --base-url "${base_url}" \
  --model qwen38-q4km-q4mtp-tp1-mtp2 --out "${out_dir}/canaries.json"
python3 - "${out_dir}/performance.json" "${out_dir}/canaries.json" \
  "${repo}/experiments/qwen38-27b-b70/data/qwen38-q4km-targetonly-tp1-mtp0-20260827-r1/performance.json" <<'PY'
import json, sys
p, c, oracle = map(lambda x: json.load(open(x)), sys.argv[1:])
assert p["realistic_final_gate"]["passed"] and p["fresh_response_validity"]["valid"]
assert p["realistic_final_gate"]["cached_tokens_all_zero"] and c["pass_all"]
left = {r["prompt_id"]: r["token_ids"] for r in p["rows"]}
right = {r["prompt_id"]: r["token_ids"] for r in oracle["rows"]}
assert left == right, "complete token arrays differ from the registered target-only oracle"
v = p["summary"]["class_balanced_tok_s_1_100_intervals_after_ttft"]["median"]
print(f"class_balanced_median_tok_s={v:.12f}")
print("cached_tokens_all_zero=true\ncanaries_passed=true\ntarget_arrays_exact=12/12")
PY
