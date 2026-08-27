#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/../.." && pwd)
base_url=${BASE_URL:-http://127.0.0.1:18128}
model=${MODEL_NAME:-qwen38-fp8-w8a16-dynamic-mtp-tp2}
out=${OUT:?set OUT to a new realistic-suite JSON path}
suite=${SUITE:-${repo_root}/repro/qwen36-27b-autoround-int4-b70/realistic-suite-v1.json}

[[ ! -e "${out}" ]] || {
  printf 'refusing to overwrite existing result: %s\n' "${out}" >&2
  exit 1
}
curl -fsS "${base_url}/health" >/dev/null

python3 "${repo_root}/scripts/bench-openai-realistic-suite.py" \
  --base-url "${base_url}" \
  --model "${model}" \
  --api-mode completions \
  --suite "${suite}" \
  --max-tokens 512 \
  --metric-tokens 100 \
  --seed 42 \
  --timeout 300 \
  --return-token-ids \
  --require-natural-eos \
  --request-extra-json '{"temperature":0,"top_p":1}' \
  --out "${out}" >/dev/null

python3 - "${out}" <<'PY'
import json
import sys

data = json.load(open(sys.argv[1]))
gate = data["realistic_final_gate"]
fresh = data["fresh_response_validity"]
rows = data["rows"]
summary = data["summary"]

if not gate["passed"] or not fresh["valid"]:
    raise SystemExit("realistic fresh-response gate failed")
if not gate["cached_tokens_all_zero"]:
    raise SystemExit("one or more requests reported cached prompt tokens")
if not gate["return_token_ids_requested"]:
    raise SystemExit("stream token-ID timing was not requested")
if len(rows) != 12 or any((row.get("completion_tokens") or 0) < 100 for row in rows):
    raise SystemExit("expected the complete suite with every response covering the metric window")
if data["run_identity"].get("max_tokens") != 512:
    raise SystemExit("promotion requires the fixed 512-token response cap")

primary = summary["tok_s_1_100_intervals_after_ttft"]
print(f"conventional_median_tok_s={primary['median']:.12f}")
print(f"conventional_p10_tok_s={primary['p10']:.12f}")
print(
    "full_after_ttft_median_tok_s="
    f"{summary['tok_s_after_ttft_full']['median']:.12f}"
)
print(f"wall_median_tok_s={summary['tok_s_wall_full']['median']:.12f}")
print(f"ttft_median_ms={summary['ttft_ms']['median']:.6f}")
print("cached_tokens_all_zero=true")
print("realistic_final_gate_passed=true")
PY
