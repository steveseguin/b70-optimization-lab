#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/../.." && pwd)
port="${PORT:-18087}"
base_url="${BASE_URL:-http://127.0.0.1:${port}}"
out="${OUT:-${PWD}/qwen38-fp8-tp2-p512-g128-n5.json}"

curl -fsS "${base_url}/health" >/dev/null

# One separate warmup request; its result is intentionally not included.
python3 "${repo_root}/scripts/bench-openai-single-decode.py" \
    --base-url "${base_url}" --model qwen38-fp8 --api-mode completions \
    --prompt-tokens 512 --prompt-mode filled-fixed-line-unique \
    --max-tokens 128 --repeats 1 --seed 4242 --timeout 300 \
    --out "${out%.json}.warmup.json" >/dev/null

python3 "${repo_root}/scripts/bench-openai-single-decode.py" \
    --base-url "${base_url}" --model qwen38-fp8 --api-mode completions \
    --prompt-tokens 512 --prompt-mode filled-fixed-line-unique \
    --max-tokens 128 --repeats 5 --seed 42 --timeout 300 --out "${out}"

python3 - "${out}" <<'PY'
import json
import sys

data = json.load(open(sys.argv[1]))
fresh = data["fresh_response_validity"]
if not fresh["all_prompt_hashes_distinct"] or not fresh["cached_tokens_all_zero"]:
    raise SystemExit("fresh-response/cache-zero gate failed")
if data["summary"]["completion_tokens"]["min"] != 128:
    raise SystemExit("one or more requests ended before 128 tokens")
print(f"median_tok_s_after_ttft={data['summary']['tok_s_after_ttft']['median']:.12f}")
print(f"median_tok_s_wall={data['summary']['tok_s_wall']['median']:.12f}")
print(f"median_ttft_s={data['summary']['ttft_s']['median']:.12f}")
print("cached_tokens_all_zero=true")
PY
