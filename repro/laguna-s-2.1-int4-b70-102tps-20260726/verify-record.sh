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
readonly record_run="$script_dir/evidence/record-run"
readonly evidence_manifest="$script_dir/evidence/record-run.sha256"
readonly runtime_lock="$script_dir/manifests/runtime-lock.json"
readonly model_manifest="$script_dir/manifests/model-release-files.sha256"
readonly historical_harness_commit=c8942a8e49ab9a69f7ca07701c2f194350bf63c3

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

for required in \
  "$packet" "$queue" "$receipt" "$oracle" "$text_oracle" "$comparator" \
  "$evidence_manifest" "$runtime_lock" "$model_manifest"; do
  [[ -f "$required" ]] || die "missing required artifact: $required"
done
[[ -d "$record_run" ]] || die "tracked sealed record evidence is missing"

check_hash "$comparator" c18b6f37aa0f5a848a9d771fa91de14bab115b41557b9d7066bce5984c2a6945
check_hash "$evidence_manifest" e83bf2402b2f3183ba876c9c34bc1c59e068f6beea38650b1b8add48657e6f50
check_hash "$runtime_lock" 8c861e5c9d44232346770e2822aa795179f8f90c2678d2ebbb42a690ef4f4a97
check_hash "$model_manifest" c19edb79458a24ceb4bb26c991302de71ef29be40e70124e90bf6c13538c692e
(
  cd "$script_dir/evidence"
  sha256sum --check --strict "$(basename -- "$evidence_manifest")" >/dev/null
) || die "tracked sealed record evidence does not match its manifest"

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
  and .quality.full512_output_then_next == "2/2"
  and .quality.long_context_then_next_tested == false
  and .quality.first_valid_score_is_reported_score == true
  and .graph.graphs_per_rank == 146
  and .graph.eager_breaks_per_rank == 145
  and .source.vllm_commit == "e596ef1543466ae1a05e5bb8091f58872e2b18ba"
  and .source.kernel_commit == "6f9dd3c3a7b1b677a992ca4f431a968408f9c816"
  and .source.attention_runtime_commit == "906190641d708b8028018c5dde653e265c835348"
  and .source.native_base_commit == "4772f727590c51b72add79350b913d098cf67872"
  and .source.xpumem_source_commit == "18a44f440ca3ac2006d5ba19cd12ccca0a0c9982"
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
      [.source.kernel_combined_patch, .sha256.kernel_combined_patch],
      [.source.attention_runtime_bundle, .sha256.attention_runtime_bundle],
      [
        .source.attention_runtime_combined_patch,
        .sha256.attention_runtime_combined_patch
      ]
    ][]
    | @tsv
  ' "$packet"
)

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

git -C "$repo_root" cat-file -e "$historical_harness_commit^{commit}" \
  || die "historical harness commit is absent"
[[ "$(
  git -C "$repo_root" show \
    "$historical_harness_commit:experiments/laguna-s-2.1-xpu-b70/tools/run_laguna_mwide_measurement_leg.sh" \
    | sha256sum | awk '{print $1}'
)" == 168351646feeeea846a5d6040603f1f50f9cefa8ae9745732e2829b96cfd218e ]] \
  || die "historical measurement leg no longer matches identity.txt"
[[ "$(
  git -C "$repo_root" show \
    "$historical_harness_commit:experiments/laguna-s-2.1-xpu-b70/tools/compare_exact_runs.py" \
    | sha256sum | awk '{print $1}'
)" == 87ad4d57907a15afba221be42ea00e3a1975308d421e0edc13881dafe38e3db3 ]] \
  || die "historical comparator no longer matches identity.txt"

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

grep -Fx 'status=PASS' "$record_run/status.txt" >/dev/null \
  || die "sealed run status is not PASS"
[[ "$(wc -l < "$record_run/cleanup-status.txt")" == 4 ]] \
  || die "sealed cleanup status must contain exactly four fields"
for expected in \
  original_status=0 stop_status=0 worker_status=0 idle_status=0; do
  grep -Fx "$expected" "$record_run/cleanup-status.txt" >/dev/null \
    || die "sealed cleanup status is missing $expected"
done
grep -Fx 'prestart elapsed_seconds=73 snapshots=13' \
  "$record_run/idle-interval/summary.txt" >/dev/null \
  || die "sealed prestart idle interval mismatch"
grep -Fx 'poststop elapsed_seconds=73 snapshots=13' \
  "$record_run/idle-interval/summary.txt" >/dev/null \
  || die "sealed poststop idle interval mismatch"
for idle in "$record_run/pre-idle.json" "$record_run/post-idle.json"; do
  jq -e '
    .status == "passed"
    and .idle.device_ids == [0,1,2,3]
    and .xpu_smi.sha256
      == "2b5b128edf28b38da8637413fe8bfe3a4a40e8113210ba9ddaed945bd56d826e"
  ' "$idle" >/dev/null || die "sealed idle evidence is malformed: $idle"
done
for expected in \
  'VLLM_XPU_LAGUNA_EXACT_MAX_M=12' \
  'LAGUNA_DFLASH_NUM_SPECULATIVE_TOKENS=11' \
  'VLLM_XPU_LAGUNA_DFLASH_FP8_W8A16=1' \
  'VLLM_XPU_LAGUNA_M8_PREBUILT_EXACT_ATTN_METADATA=1' \
  'VLLM_XPU_LAGUNA_M8_BREAKABLE_GRAPH=1' \
  'VLLM_USE_BREAKABLE_CUDAGRAPH=1' \
  'XPU_GRAPH=1' \
  'VLLM_XPU_ENABLE_XPU_GRAPH=1'; do
  grep -Fx "$expected" "$record_run/service-environment.txt" >/dev/null \
    || die "sealed service environment is missing $expected"
done

printf 'record_verification=PASS\n'
printf 'published_legacy_tok_s=102.97143559613157\n'
printf 'conventional_interval_tok_s=101.94172124017027\n'
printf 'metric_disposition=approved receipt preserved; no duplicate submission\n'
printf 'localmaxxing_id=cms2ccv2d00lps201rej94pjy\n'
printf 'localmaxxing_status=APPROVED\n'
printf 'sealed_raw_evidence=tracked-hashes-token-text-accounting-environment-cleanup-idle-pass\n'
