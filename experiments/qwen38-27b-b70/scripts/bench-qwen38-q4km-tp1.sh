#!/usr/bin/env bash
set -euo pipefail

# Fixed cold realistic 12-prompt suite against the TP1 lane server.
# Verifies the fresh-response gate and cached_tokens=0, records output hashes,
# and reports (informationally) how many outputs match the promoted TP2 oracle.
# The TP1 route defines its own oracle; TP2 equality is evidence, not a gate.

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/../../.." && pwd)

QWEN38_HOST="${QWEN38_HOST:-127.0.0.1}"
QWEN38_PORT="${QWEN38_PORT:-18088}"
base_url="http://${QWEN38_HOST}:${QWEN38_PORT}"
out="${OUT:-${PWD}/qwen38-q4km-tp1-realistic512.json}"

curl -fsS "${base_url}/health" >/dev/null
python3 "${repo_root}/scripts/bench-openai-realistic-suite.py" \
    --base-url "${base_url}" \
    --model qwen38-q4km-tp1-b70s \
    --api-mode completions \
    --suite "${repo_root}/repro/qwen36-27b-autoround-int4-b70/realistic-suite-v1.json" \
    --max-tokens 512 \
    --metric-tokens 100 \
    --seed 1 \
    --timeout 600 \
    --out "${out}" \
    --request-extra-json '{"cache_prompt":false,"seed":42,"temperature":0}'

python3 - "${out}" "${repo_root}/experiments/qwen38-27b-b70/data/2026-08-15-q4km-tp2-q4k-glu-summary.json" <<'PY'
import json
import sys

data = json.load(open(sys.argv[1]))
reference = json.load(open(sys.argv[2]))
gate = data["realistic_final_gate"]
fresh = data["fresh_response_validity"]
legacy = data["summary"]["tok_s_1_100_after_ttft"]

if not gate["passed"] or not fresh["valid"] or not gate["cached_tokens_all_zero"]:
    raise SystemExit("realistic fresh-response gate failed")

tp2_matches = sum(
    1 for a, b in zip(data["output_sha256s"], reference["output_sha256s"]) if a == b
)
print(f"historical_100_event_median_tok_s={legacy['median']:.12f}")
print(f"conventional_99_interval_median_tok_s={legacy['median'] * 0.99:.12f}")
print(f"conventional_99_interval_p10_tok_s={legacy['p10'] * 0.99:.12f}")
print(f"full_after_ttft_median_tok_s={data['summary']['tok_s_after_ttft_full']['median']:.12f}")
print(f"full_wall_median_tok_s={data['summary']['tok_s_wall_full']['median']:.12f}")
print(f"ttft_median_ms={data['summary']['ttft_ms']['median']:.6f}")
print("cached_tokens_all_zero=true")
print(f"tp2_oracle_exact_matches={tp2_matches}/12 (informational)")
print("realistic_final_gate_passed=true")
PY
