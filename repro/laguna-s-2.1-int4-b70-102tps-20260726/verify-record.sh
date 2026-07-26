#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
repo_root="$(git -C "$script_dir" rev-parse --show-toplevel)"

readonly packet="$repo_root/data/laguna-s-2.1-width12-dflash-fp8-record-20260726.json"
readonly queue="$repo_root/data/localmaxxing-laguna-s-2.1-int4-b70-width12-dflash-fp8-102.971tok-20260726.queue.json"
readonly receipt="$repo_root/data/localmaxxing-responses/laguna-s-2.1-int4-b70-width12-dflash-fp8-102.971tok-20260726.response.json"
readonly oracle="$script_dir/teacher-token-oracle-v1.json"
readonly text_oracle="$script_dir/teacher-text-sha256-v1.json"
readonly comparator="$repo_root/experiments/laguna-s-2.1-xpu-b70/tools/compare_exact_runs.py"
readonly record_run="${RECORD_RUN_ROOT:-/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-width12-dflash-fp8-e596ef154-20260726T214259Z}"

die() {
  printf 'Laguna record verification: %s\n' "$*" >&2
  exit 2
}

check_hash() {
  local path="$1" expected="$2" actual
  [[ -f "$path" ]] || die "missing file: $path"
  actual="$(sha256sum -- "$path")"
  actual="${actual%% *}"
  [[ "$actual" == "$expected" ]] \
    || die "SHA256 mismatch for $path: expected $expected, got $actual"
}

for required in "$packet" "$queue" "$receipt" "$oracle" "$text_oracle" "$comparator"; do
  [[ -f "$required" ]] || die "missing required artifact: $required"
done

jq -e '
  .schema == "laguna-s-2.1-width12-dflash-fp8-record-v1"
  and .status == "VERIFIED_RECORD_SUBMITTED_APPROVED"
  and .metric == "median_tok_s_1_100_after_ttft"
  and .record.value_tok_s == 102.97143559613157
  and .metric_accounting.published_convention == "legacy-inclusive-events"
  and .metric_accounting.published_value_tok_s == 102.97143559613157
  and .metric_accounting.conventional_interval_value_tok_s == 101.94172124017027
  and .metric_accounting.timestamped_events == 100
  and .metric_accounting.inter_token_intervals == 99
  and .quality.teacher_exact == "13/13"
  and .quality.cached_tokens_zero == "13/13"
  and .quality.first_valid_score_is_reported_score == true
  and .graph.graphs_per_rank == 146
  and .graph.eager_breaks_per_rank == 145
  and .source.vllm_commit == "e596ef1543466ae1a05e5bb8091f58872e2b18ba"
  and .source.kernel_commit == "6f9dd3c3a7b1b677a992ca4f431a968408f9c816"
  and .localmaxxing.submission_status == "APPROVED"
  and .localmaxxing.id == "cms2ccv2d00lps201rej94pjy"
' "$packet" >/dev/null || die "record packet identity or gates do not match"

jq -e '
  length == 1
  and .[0].payload.hfId == "poolside/Laguna-S-2.1-INT4"
  and .[0].payload.modelRevision == "4bbfc285f2f8b3b6b526274c133b7b17aae6c8cb"
  and .[0].payload.hardware.gpuCount == 4
  and .[0].payload.engineFlags.tensorParallelSize == 4
  and .[0].payload.tokSOut == 102.97143559613157
  and .[0].payload.engineFlags.primaryMetricName == "median_tok_s_1_100_after_ttft"
  and .[0].payload.engineFlags.realisticSuiteGatePassed == true
  and .[0].payload.engineFlags.realisticSuiteCachedTokensAllZero == true
' "$queue" >/dev/null || die "LocalMaxxing queue does not match the sealed record"

jq -e '
  .http_status == 201
  and .response.id == "cms2ccv2d00lps201rej94pjy"
  and .response.status == "APPROVED"
  and .public_verification.id == .response.id
  and .public_verification.status == "APPROVED"
  and .public_verification.tok_s_out == 102.9714355961316
  and .public_verification.model == "poolside/Laguna-S-2.1-INT4"
  and .public_verification.gpu_count == 4
' "$receipt" >/dev/null || die "LocalMaxxing receipt or public verification does not match"

check_hash "$oracle" a2be70c2c603ceaaf5de4558ef80c6063e54a38af604623463a0bcbc22e3cdeb
check_hash "$text_oracle" 3b669ddc389a08c75b7812b5af2394032476019fae04b9de83e51f520db0cf72
jq -e '
  .schema == "laguna-q1-token-oracle-v1"
  and .source_sha256 == "d41d3d5e2471ee98f783e58407e44217ade67f7472147eeeb82780efa89879d1"
  and (.rows | length) == 13
  and ([.rows[].token_ids | length] == [512,512,512,512,512,512,512,512,512,512,296,426,512])
' "$oracle" >/dev/null || die "compact canonical-q1 token oracle is malformed"
jq -e '
  .schema == "laguna-q1-text-sha256-oracle-v1"
  and .source_sha256 == "d41d3d5e2471ee98f783e58407e44217ade67f7472147eeeb82780efa89879d1"
  and (.rows | length) == 13
  and ([.rows[].prompt_index] == [0,1,2,3,4,5,6,7,8,9,10,11,12])
  and all(.rows[]; (.sha256 | type) == "string" and (.sha256 | length) == 64)
' "$text_oracle" >/dev/null || die "compact canonical-q1 text oracle is malformed"

while IFS=$'\t' read -r relative expected; do
  check_hash "$repo_root/$relative" "$expected"
done < <(
  jq -r '
    [
      [.source.vllm_bundle, .sha256.vllm_bundle],
      [.source.vllm_combined_patch, .sha256.vllm_combined_patch],
      [.source.kernel_bundle, .sha256.kernel_bundle],
      [.source.kernel_combined_patch, .sha256.kernel_combined_patch]
    ][]
    | @tsv
  ' "$packet"
)

raw_status=not-present
if [[ -d "$record_run" ]]; then
  while IFS=$'\t' read -r filename key; do
    expected="$(jq -r --arg key "$key" '.sha256[$key]' "$packet")"
    check_hash "$record_run/$filename" "$expected"
  done <<'EOF'
bench.json	bench
exactness-vs-q1.json	exactness
server.log	server_log
identity.txt	identity
metrics-after-suite.prom	metrics_after_suite
EOF
  python3 "$comparator" \
    --teacher "$oracle" \
    --teacher-text-oracle "$text_oracle" \
    --require-text-hash \
    --candidate "$record_run/bench.json" \
    --out /dev/null >/dev/null \
    || die "sealed benchmark no longer matches the tracked token/text oracles"
  python3 - "$record_run/bench.json" <<'PY'
import json
import math
import statistics
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
legacy = []
conventional = []
for index, row in enumerate(data["rows"]):
    offsets = row["token_id_offsets_s"]
    if len(offsets) < 100:
        raise SystemExit(f"row {index} has fewer than 100 timestamped token events")
    span = float(offsets[99]) - float(offsets[0])
    if span <= 0:
        raise SystemExit(f"row {index} has a nonpositive metric span")
    legacy.append(100.0 / span)
    conventional.append(99.0 / span)

published = statistics.median(legacy)
corrected = statistics.median(conventional)
if not math.isclose(published, 102.97143559613157, rel_tol=0, abs_tol=1e-12):
    raise SystemExit(f"published metric mismatch: {published!r}")
if not math.isclose(corrected, 101.94172124017027, rel_tol=0, abs_tol=1e-12):
    raise SystemExit(f"conventional metric mismatch: {corrected!r}")
PY
  raw_status=hashes-token-text-and-accounting-pass
fi

printf 'record_verification=PASS\n'
printf 'published_legacy_tok_s=102.97143559613157\n'
printf 'conventional_interval_tok_s=101.94172124017027\n'
printf 'metric_disposition=approved receipt preserved; no duplicate submission\n'
printf 'localmaxxing_id=cms2ccv2d00lps201rej94pjy\n'
printf 'localmaxxing_status=APPROVED\n'
printf 'sealed_raw_evidence=%s\n' "$raw_status"
