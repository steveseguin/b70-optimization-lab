#!/usr/bin/env bash
set -euo pipefail

# Fixed target-only diagnostic gate for a server started by
# run-model-intake-baseline.sh. Passing establishes a baseline, not promotion.

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/.." && pwd)
intake_id="${INTAKE_ID:-}"
base_url="${BASE_URL:-http://127.0.0.1:18100}"
out="${OUT:-${PWD}/intake-baseline-result.json}"

[[ -n "${intake_id}" ]] || { printf 'Set INTAKE_ID.\n' >&2; exit 2; }
curl -fsS "${base_url}/health" >/dev/null
python3 "${repo_root}/scripts/bench-openai-realistic-suite.py" \
    --base-url "${base_url}" --model "${intake_id}" --api-mode completions \
    --suite "${repo_root}/repro/qwen36-27b-autoround-int4-b70/realistic-suite-v1.json" \
    --max-tokens 128 --metric-tokens 100 --seed 1 --timeout 600 --out "${out}" \
    --request-extra-json '{"cache_prompt":false,"seed":42,"temperature":0}'

python3 - "${out}" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
gate = d["realistic_final_gate"]
fresh = d["fresh_response_validity"]
if not fresh["valid"]:
    raise SystemExit("fresh-response validity failed")
if not gate["cached_tokens_all_zero"]:
    raise SystemExit("cached-token gate failed")
if not gate["passed"]:
    raise SystemExit("fixed diagnostic suite failed")
metric = d["summary"]["tok_s_1_100_after_ttft"]
print(f"baseline_median_tok_s={metric['median']:.12f}")
print(f"baseline_p10_tok_s={metric['p10']:.12f}")
print("cached_tokens_all_zero=true")
print("fresh_response_valid=true")
print("status=diagnostic-baseline; quality oracle and clean-runtime pin still required")
PY
