#!/usr/bin/env bash
set -euo pipefail

root="/home/steve/llm-optimizations"
scripts="${root}/experiments/deepseek-v4-flash-reap-xpu-b70/scripts"
quality="${root}/experiments/deepseek-v4-flash-reap-xpu-b70/quality"
model="deepseek-v4-flash-0731-reap-k160"
revision="ddc04540efda3d2a0788b129f1fad828ddc19b60"
base_url="${BASE_URL:-http://127.0.0.1:18080}"
run_dir="${RUN_DIR:?set RUN_DIR to the active 0731 server run directory}"
mode="${1:-smoke}"

case "${mode}" in
  smoke|full) ;;
  *) printf 'usage: %s smoke|full\n' "$0" >&2; exit 2 ;;
esac

identity="${run_dir}/identity.txt"
test -f "${identity}"
grep -Fx "model_revision=${revision}" "${identity}" >/dev/null
grep -Fx "served_model_name=${model}" "${identity}" >/dev/null
grep -Fx 'tensor_parallel_size=4' "${identity}" >/dev/null
grep -Fx 'data_parallel_size=1' "${identity}" >/dev/null
grep -Fx 'pipeline_parallel_size=1' "${identity}" >/dev/null
if [[ "${mode}" == "full" ]]; then
  max_model_len="$(awk -F= '$1 == "max_model_len" {print $2}' "${identity}")"
  test "${max_model_len}" -ge 2048
fi

for output in \
  endpoint-models.json \
  exact-canaries-pre.json \
  exact-canaries-pre-score.json \
  exact-canaries-post.json \
  exact-canaries-post-score.json \
  quality-continuity.json \
  quality-continuity-score.json \
  realistic-suite.json \
  target-qualification-summary.json; do
  test ! -e "${run_dir}/${output}"
done

curl --fail --silent --show-error "${base_url}/v1/models" \
  >"${run_dir}/endpoint-models.json"
jq -e --arg model "${model}" \
  '.data | any(.id == $model)' "${run_dir}/endpoint-models.json" >/dev/null

capture_exact() {
  local label="$1"
  local output="$2"
  local score="$3"
  python3 "${scripts}/capture-openai-logprob-corpus.py" \
    --base-url "${base_url}" \
    --model "${model}" \
    --model-revision "${revision}" \
    --suite "${quality}/exact-canaries-v1.json" \
    --out "${output}" \
    --max-tokens 32 \
    --top-logprobs 0 \
    --seed 1 \
    --label "${label}"
  python3 "${scripts}/score-exact-canaries.py" \
    "${output}" \
    --suite "${quality}/exact-canaries-v1.json" \
    --strict-contract "${quality}/exact-canaries-0731-target-contract-v1.json" \
    --out "${score}"
}

capture_exact \
  "0731-target-${mode}-pre" \
  "${run_dir}/exact-canaries-pre.json" \
  "${run_dir}/exact-canaries-pre-score.json"

if [[ "${mode}" == "smoke" ]]; then
  jq -n \
    --arg mode "${mode}" \
    --arg model "${model}" \
    --arg revision "${revision}" \
    --arg identity_sha256 "$(sha256sum "${identity}" | awk '{print $1}')" \
    --arg exact_score_sha256 "$(sha256sum "${run_dir}/exact-canaries-pre-score.json" | awk '{print $1}')" \
    '{schema: "deepseek-v4-0731-target-qualification-v1", status: "pass", mode: $mode, model: $model, revision: $revision, identity_sha256: $identity_sha256, exact_pre_score_sha256: $exact_score_sha256}' \
    >"${run_dir}/target-qualification-summary.json"
  exit 0
fi

python3 "${scripts}/capture-openai-logprob-corpus.py" \
  --base-url "${base_url}" \
  --model "${model}" \
  --model-revision "${revision}" \
  --suite "${quality}/suite-v1.json" \
  --out "${run_dir}/quality-continuity.json" \
  --max-tokens 1024 \
  --top-logprobs 0 \
  --seed 1776 \
  --label 0731-target-quality-continuity
python3 "${scripts}/score-quality-capture.py" \
  "${run_dir}/quality-continuity.json" \
  --promotion \
  --suite "${quality}/suite-v1.json" \
  --expected-model "${model}" \
  --expected-model-revision "${revision}" \
  --out "${run_dir}/quality-continuity-score.json"

python3 "${root}/scripts/bench-openai-realistic-suite.py" \
  --base-url "${base_url}" \
  --model "${model}" \
  --suite "${root}/repro/rapid-model-snapshots-b70/realistic-suite-v1.json" \
  --max-tokens 128 \
  --metric-tokens 100 \
  --seed 1 \
  --return-token-ids \
  --out "${run_dir}/realistic-suite.json"
jq -e '.realistic_final_gate.passed == true' \
  "${run_dir}/realistic-suite.json" >/dev/null

capture_exact \
  0731-target-full-post \
  "${run_dir}/exact-canaries-post.json" \
  "${run_dir}/exact-canaries-post-score.json"

python3 - "${run_dir}" "${model}" "${revision}" <<'PY'
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

run = Path(sys.argv[1])
model = sys.argv[2]
revision = sys.argv[3]


def load(name: str):
    return json.loads((run / name).read_text(encoding="utf-8"))


def digest(name: str) -> str:
    return hashlib.sha256((run / name).read_bytes()).hexdigest()


exact_pre = load("exact-canaries-pre-score.json")
exact_post = load("exact-canaries-post-score.json")
quality = load("quality-continuity-score.json")
realistic = load("realistic-suite.json")
result = {
    "schema": "deepseek-v4-0731-target-qualification-v1",
    "status": "pass",
    "mode": "full",
    "completed_at_utc": datetime.now(timezone.utc).isoformat(),
    "model": model,
    "revision": revision,
    "gates": {
        "exact_pre": exact_pre.get("passed") is True,
        "quality_executable_and_corruption": quality.get("promotion_gates_passed") is True,
        "realistic_fresh_response": realistic.get("realistic_final_gate", {}).get("passed") is True,
        "exact_post": exact_post.get("passed") is True,
    },
    "quality_manual_rubrics_pending": quality.get("manual_rubrics_pending"),
    "performance": realistic.get("summary"),
    "sha256": {
        name: digest(name)
        for name in (
            "identity.txt",
            "exact-canaries-pre.json",
            "exact-canaries-pre-score.json",
            "quality-continuity.json",
            "quality-continuity-score.json",
            "realistic-suite.json",
            "exact-canaries-post.json",
            "exact-canaries-post-score.json",
        )
    },
}
if not all(result["gates"].values()):
    raise SystemExit(f"qualification gate unexpectedly false: {result['gates']}")
(run / "target-qualification-summary.json").write_text(
    json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
)
PY
