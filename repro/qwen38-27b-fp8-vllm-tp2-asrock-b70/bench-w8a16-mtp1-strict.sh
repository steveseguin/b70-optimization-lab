#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/../.." && pwd)
out_dir=${OUT_DIR:?set OUT_DIR to a new result directory}
base_url=${BASE_URL:-http://127.0.0.1:18124}
model=${MODEL_NAME:-qwen38-fp8-block-w8a16-mtp1}
profile=${PROFILE_LABEL:-mtp1-research-audit}
attempt=${ATTEMPT_LABEL:-third-party-fresh-attempt}
suite=${SUITE:-${repo_root}/repro/qwen36-27b-autoround-int4-b70/realistic-suite-v1.json}
harness=${repo_root}/scripts/bench-openai-realistic-suite.py
canary_harness=${repo_root}/scripts/neural-download-canaries.py

[[ ! -e "${out_dir}" ]] || {
  printf 'refusing to overwrite result directory: %s\n' "${out_dir}" >&2
  exit 1
}
for required in "${suite}" "${harness}" "${canary_harness}"; do
  [[ -f "${required}" ]] || { printf 'missing input: %s\n' "${required}" >&2; exit 1; }
done
curl -fsS "${base_url}/health" >/dev/null
mkdir -p "${out_dir}"

python3 - "${out_dir}/campaign-identity.json" "${suite}" "${profile}" "${attempt}" <<'PY'
import datetime as dt
import hashlib
import json
import pathlib
import sys

out, suite, profile, attempt = sys.argv[1:]
suite_path = pathlib.Path(suite)
identity = {
    "schema": "neural.download.qwen38-fp8-public-strict-attempt.v1",
    "created_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
    "profile": profile,
    "attempt": attempt,
    "suite": str(suite_path),
    "suite_sha256": hashlib.sha256(suite_path.read_bytes()).hexdigest(),
    "prompt_kv_response_history_cache_reuse": False,
    "performance_contract": {
        "complete_fixed_suite": True,
        "max_tokens": 512,
        "metric_events": 100,
        "metric_intervals": 99,
        "aggregation": "median-of-prompt-class-medians",
        "cached_tokens_required": 0,
        "temperature": 0,
        "prompt_reuse": False,
        "ignore_eos": False,
    },
}
pathlib.Path(out).write_text(json.dumps(identity, indent=2, sort_keys=True) + "\n")
PY

curl -fsS "${base_url}/v1/models" >"${out_dir}/models.json"
python3 "${harness}" \
  --base-url "${base_url}" --model "${model}" --api-mode completions \
  --suite "${suite}" --max-tokens 512 --metric-tokens 100 --seed 42 \
  --timeout 900 --return-token-ids --require-natural-eos \
  --request-extra-json '{"temperature":0,"top_p":1}' \
  --out "${out_dir}/performance.json" >"${out_dir}/performance.stdout"
python3 "${canary_harness}" \
  --base-url "${base_url}" --model "${model}" \
  --out "${out_dir}/canaries.json" >"${out_dir}/canaries.stdout"

python3 - "${out_dir}/performance.json" "${out_dir}/canaries.json" <<'PY'
import json
import sys

performance = json.load(open(sys.argv[1]))
canaries = json.load(open(sys.argv[2]))
gate = performance["realistic_final_gate"]
fresh = performance["fresh_response_validity"]
primary = performance["summary"]["class_balanced_tok_s_1_100_intervals_after_ttft"]
assert gate["passed"]
assert fresh["performance_gate_eligible"]
assert fresh["cached_tokens_all_zero"]
assert len(performance["rows"]) == 12
assert canaries["pass_all"]
print(f"class_balanced_median_tok_s={primary['median']:.12f}")
print("workload_cache_zero_canary_gate=pass")
print("target_and_repeat_parity=not_evaluated_by_single_attempt")
PY

sha256sum "${suite}" "${harness}" "${canary_harness}" \
  >"${out_dir}/input-sha256sums.txt"
printf 'PASS workload/cache/canaries: %s\n' "${out_dir}"
printf 'THIS ATTEMPT ALONE IS NOT QUALIFIED: preserve two fresh MTP1 and two matched-image MTP0 attempts with every comparison 12/12 exact\n'
