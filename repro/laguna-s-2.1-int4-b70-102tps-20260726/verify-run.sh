#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
repo_root="$(git -C "$script_dir" rev-parse --show-toplevel)"
readonly comparator="$repo_root/experiments/laguna-s-2.1-xpu-b70/tools/compare_exact_runs.py"
readonly oracle="$script_dir/teacher-token-oracle-v1.json"
readonly text_oracle="$script_dir/teacher-text-sha256-v1.json"

die() {
  printf 'Laguna reproduction validation: %s\n' "$*" >&2
  exit 2
}

[[ $# == 1 ]] || die "usage: verify-run.sh RUN_DIR"
run_dir="$(realpath -e -- "$1")"
[[ -d "$run_dir" ]] || die "not a run directory: $run_dir"

for file in bench.json exactness-vs-q1.json identity.txt server.log status.txt cleanup-status.txt; do
  [[ -r "$run_dir/$file" ]] || die "missing or unreadable $file"
done

grep -Fx 'status=PASS' "$run_dir/status.txt" >/dev/null \
  || die "run status is not PASS"
grep -Fx 'vllm_commit=e596ef1543466ae1a05e5bb8091f58872e2b18ba' "$run_dir/identity.txt" >/dev/null \
  || die "vLLM identity mismatch"
grep -Fx 'kernel_commit=6f9dd3c3a7b1b677a992ca4f431a968408f9c816' "$run_dir/identity.txt" >/dev/null \
  || die "XPU-kernel identity mismatch"
grep -Fx 'exact_max_m=12' "$run_dir/identity.txt" >/dev/null \
  || die "verifier width mismatch"
grep -Fx 'num_speculative_tokens=11' "$run_dir/identity.txt" >/dev/null \
  || die "DFlash depth mismatch"
grep -Fx 'dflash_fp8_w8a16=1' "$run_dir/identity.txt" >/dev/null \
  || die "draft FP8 selector mismatch"

while IFS='=' read -r name value; do
  [[ "$value" == 0 ]] || die "cleanup field $name is $value, expected 0"
done < "$run_dir/cleanup-status.txt"

python3 "$comparator" \
  --teacher "$oracle" \
  --teacher-text-oracle "$text_oracle" \
  --require-text-hash \
  --candidate "$run_dir/bench.json" \
  --out /dev/null >/dev/null \
  || die "candidate differs from the compact token/text oracles"

jq -e '
  .fresh_response_validity.valid == true
  and .fresh_response_validity.each_prompt_run_once == true
  and .fresh_response_validity.cached_tokens_all_zero == true
  and .fresh_response_validity.history_acceleration == false
  and .fresh_response_validity.response_reuse == false
  and .fresh_response_validity.context_checkpoints_or_prefix_reuse == false
  and .realistic_final_gate.passed == true
  and .run_identity.prompt_count == 13
  and .run_identity.max_tokens == 512
  and .run_identity.seed == 1
  and .summary.tok_s_1_100_after_ttft.count == 13
  and .summary.tok_s_1_100_intervals_after_ttft.count == 13
' "$run_dir/bench.json" >/dev/null || die "fresh-response or metric gate failed"

python3 - "$run_dir/server.log" <<'PY'
import re
import sys
from pathlib import Path

lines = Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace").splitlines()
rank_pattern = re.compile(r"Worker_TP([0-3])_EP([0-3])")
expected_ranks = {(0, 0), (1, 1), (2, 2), (3, 3)}
for label, marker in (
    ("capture", "Captured audited breakable cudagraph"),
    ("replay", "Replayed audited breakable cudagraph"),
):
    rows = [line for line in lines if marker in line]
    ranks = {
        tuple(map(int, match.groups()))
        for line in rows
        if (match := rank_pattern.search(line))
    }
    if len(rows) != 4 or ranks != expected_ranks:
        raise SystemExit(
            f"{label} evidence mismatch: rows={len(rows)} ranks={sorted(ranks)}"
        )
    if any("(graphs=146, eager_breaks=145)" not in line for line in rows):
        raise SystemExit(f"{label} topology is not 146/145")

fp8_marker = "Prepared Laguna DFlash FP8 W8A16 draft projections: count=31"
fp8_rows = [line for line in lines if fp8_marker in line]
fp8_ranks = {
    tuple(map(int, match.groups()))
    for line in fp8_rows
    if (match := rank_pattern.search(line))
}
if len(fp8_rows) != 4 or fp8_ranks != expected_ranks:
    raise SystemExit(
        f"draft FP8 evidence mismatch: rows={len(fp8_rows)} ranks={sorted(fp8_ranks)}"
    )
PY

python3 - "$run_dir/bench.json" <<'PY'
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
        raise SystemExit(f"row {index} has fewer than 100 token timestamps")
    span = float(offsets[99]) - float(offsets[0])
    if span <= 0:
        raise SystemExit(f"row {index} has a nonpositive metric span")
    legacy.append(100.0 / span)
    conventional.append(99.0 / span)

published = statistics.median(legacy)
corrected = statistics.median(conventional)
summary = data["summary"]
checks = (
    (summary["tok_s_1_100_after_ttft"]["median"], published, "legacy summary"),
    (
        summary["tok_s_1_100_intervals_after_ttft"]["median"],
        corrected,
        "interval summary",
    ),
)
for actual, expected, label in checks:
    if not math.isclose(float(actual), expected, rel_tol=0, abs_tol=1e-12):
        raise SystemExit(f"{label} mismatch: {actual!r} != {expected!r}")
print(f"published_legacy_tok_s={published:.14f}")
print(f"conventional_interval_tok_s={corrected:.14f}")
PY

printf 'reproduction_validation=PASS\n'
