#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/../.." && pwd)
# shellcheck source=config.env
source "${script_dir}/config.env"

base_url="http://${QWEN36_HOST}:${QWEN36_PORT}"
out="${OUT:-${PWD}/qwen36-q8-tp2-realistic512.json}"

curl -fsS "${base_url}/health" >/dev/null

python3 "${repo_root}/scripts/bench-openai-realistic-suite.py" \
    --base-url "${base_url}" \
    --model qwen36-q8-tp2-asrock-b70 \
    --api-mode completions \
    --suite "${repo_root}/repro/qwen36-27b-autoround-int4-b70/realistic-suite-v1.json" \
    --max-tokens 512 \
    --metric-tokens 100 \
    --seed 1 \
    --timeout 300 \
    --out "${out}" \
    --request-extra-json '{"cache_prompt":false,"seed":42,"temperature":0}'

python3 - "${out}" "${repo_root}/data/qwen36-q8-tp2-asrock-b70-20260814/summary.json" <<'PY'
import json
import sys

data = json.load(open(sys.argv[1]))
reference = json.load(open(sys.argv[2]))
gate = data["realistic_final_gate"]
fresh = data["fresh_response_validity"]
legacy = data["summary"]["tok_s_1_100_after_ttft"]

if not gate["passed"] or not fresh["valid"] or not gate["cached_tokens_all_zero"]:
    raise SystemExit("realistic fresh-response gate failed")
if data["output_sha256s"] != reference["output_sha256s"]:
    raise SystemExit("output hashes differ from the promoted target-only oracle")

print(f"historical_100_event_median_tok_s={legacy['median']:.12f}")
print(f"conventional_99_interval_median_tok_s={legacy['median'] * 0.99:.12f}")
print(f"conventional_99_interval_p10_tok_s={legacy['p10'] * 0.99:.12f}")
print(f"full_512_after_ttft_median_tok_s={data['summary']['tok_s_after_ttft_full']['median']:.12f}")
print(f"full_512_wall_median_tok_s={data['summary']['tok_s_wall_full']['median']:.12f}")
print(f"ttft_median_ms={data['summary']['ttft_ms']['median']:.6f}")
print("cached_tokens_all_zero=true")
print("output_hashes_exact=12/12")
print("realistic_final_gate_passed=true")
PY
