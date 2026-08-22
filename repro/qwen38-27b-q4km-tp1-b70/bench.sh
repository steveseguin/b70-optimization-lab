#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/../.." && pwd)
base_url="${BASE_URL:-http://127.0.0.1:18088}"
out="${OUT:-${PWD}/qwen38-q4km-tp1-result.json}"

curl -fsS "${base_url}/health" >/dev/null
python3 "${repo_root}/scripts/bench-openai-realistic-suite.py" \
  --base-url "${base_url}" --model qwen38-q4km-tp1-b70 \
  --api-mode completions \
  --suite "${repo_root}/repro/qwen36-27b-autoround-int4-b70/realistic-suite-v1.json" \
  --max-tokens 512 --metric-tokens 100 --seed 1 --timeout 600 --out "${out}" \
  --request-extra-json '{"cache_prompt":false,"seed":42,"temperature":0}'

python3 - "${out}" \
  "${repo_root}/experiments/qwen38-27b-b70/data/2026-08-21-q4km-tp1-gpu0-final-i.json" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
reference = json.load(open(sys.argv[2]))
gate, fresh = d["realistic_final_gate"], d["fresh_response_validity"]
if not gate["passed"] or not fresh["valid"] or not gate["cached_tokens_all_zero"]:
    raise SystemExit("fresh, cache-zero benchmark gate failed")
if d["output_sha256s"] != reference["output_sha256s"]:
    raise SystemExit("output hashes differ from the registered TP1 oracle")
legacy = d["summary"]["tok_s_1_100_after_ttft"]
print(f"conventional_99_interval_median_tok_s={legacy['median'] * 0.99:.12f}")
print(f"conventional_99_interval_p10_tok_s={legacy['p10'] * 0.99:.12f}")
print(f"ttft_median_ms={d['summary']['ttft_ms']['median']:.6f}")
print("cached_tokens_all_zero=true")
print("output_hashes_exact=12/12")
print("realistic_final_gate_passed=true")
PY
