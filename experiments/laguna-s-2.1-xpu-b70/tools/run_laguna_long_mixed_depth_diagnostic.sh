#!/usr/bin/env bash
# Frozen seven-row long-context mixed-depth feasibility run; never emits a score.
#
# The analyzer this feeds tests one question: does the 32,640-token context ever
# accept a draft token beyond position 6, and does a short prompt still accept
# beyond it on the same service? A pass authorizes a default-off source
# prototype only. It is not a performance measurement and cannot promote
# anything.
#
# The row sequence is fixed by the analyzer, which rejects extra, missing,
# reordered, or renamed rows. Selecting the 1,024-token first-live warmup plus
# the three 32,640-token rows makes the benchmark emit exactly:
#   laguna-lc-01024-early
#   laguna-lc-32640-early    sentinel-after-laguna-lc-32640-early
#   laguna-lc-32640-middle   sentinel-after-laguna-lc-32640-middle
#   laguna-lc-32640-late     sentinel-after-laguna-lc-32640-late
# because the benchmark appends a 256-token sentinel after every 32,640-token
# case and case selection preserves suite order.
#
# The run stays on the incumbent q12 identity. The analyzer requires accepted
# draft positions 0 through 10 to all be present, which only holds at draft
# depth 11, so this diagnostic cannot be run at any other depth.
set -euo pipefail
umask 077

tag="${1:?usage: run_laguna_long_mixed_depth_diagnostic.sh TAG REPEAT_ORACLE}"
oracle="${2:?usage: run_laguna_long_mixed_depth_diagnostic.sh TAG REPEAT_ORACLE}"
[[ "$tag" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$ ]] || {
  echo "invalid tag" >&2
  exit 2
}
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
repo_root="$(git -C "$script_dir" rev-parse --show-toplevel)"
# shellcheck source=laguna_nvme_paths.sh
source "$script_dir/laguna_nvme_paths.sh"

readonly runner="$script_dir/run_laguna_long_context_baseline.sh"
readonly analyzer="$script_dir/analyze_laguna_long_mixed_depth.py"
readonly resolved_prover="$script_dir/assert_laguna_resolved_cache_partition.py"
readonly python="${LAGUNA_ANALYZER_PYTHON:-/home/steve/.venvs/deepseek-v4-xpu/bin/python}"
readonly suite="$repo_root/experiments/laguna-s-2.1-xpu-b70/long-context-suite-v1.json"
# The analyzer's frozen row identities, in its required order.
readonly cases=laguna-lc-01024-early,laguna-lc-32640-early,laguna-lc-32640-middle,laguna-lc-32640-late
readonly required_case_ids=(
  laguna-lc-01024-early
  laguna-lc-32640-early
  sentinel-after-laguna-lc-32640-early
  laguna-lc-32640-middle
  sentinel-after-laguna-lc-32640-middle
  laguna-lc-32640-late
  sentinel-after-laguna-lc-32640-late
)
# The incumbent pair: 8192 batched minus the ten drafting slots depth 11
# reserves at max_num_seqs=1, which is what partitions 32,640 tokens as
# 8182 + 8182 + 8182 + 8094.
readonly batched_tokens=8192
readonly derived_scheduled_tokens=8182

die() { echo "Laguna mixed-depth diagnostic: $*" >&2; exit 2; }

for path in "$runner" "$analyzer" "$resolved_prover" "$python" "$suite"; do
  [[ -e "$path" ]] || die "missing required path: $path"
done
oracle="$(realpath -- "$oracle")" || die "cannot resolve the repeat oracle"
[[ -f "$oracle" ]] || die "missing repeat oracle: $oracle"
[[ -z "$(git -C "$repo_root" status --short)" ]] || die "main repository is dirty"

# The benchmark tolerates an oracle that covers more than the selected rows, but
# every selected row must be present or the run cannot reach oracle exactness.
[[ "$(jq -r .schema "$oracle")" == laguna-long-context-repeat-oracle-v1 ]] \
  || die "repeat oracle schema mismatch"
[[ "$(jq -r .status "$oracle")" == PASS_COMPOSITE_ORACLE ]] \
  || die "repeat oracle is not a passing composite oracle"
for case_id in "${required_case_ids[@]}"; do
  [[ "$(jq -r --arg id "$case_id" '[.rows[] | select(.case_id == $id)] | length' "$oracle")" == 1 ]] \
    || die "repeat oracle does not cover exactly one $case_id row"
done

! pgrep -f 'vllm serve|VLLM::EngineCore|VLLM::Worker|torchrun' >/dev/null 2>&1 \
  || die "foreign model process blocks the diagnostic"
! ss -H -ltn 'sport = :8000 or sport = :18080' | grep -q . \
  || die "protected port is busy"

readonly diagnostic_root="$LAGUNA_NVME_RUN_ROOT/laguna-long-mixed-depth-$tag"
readonly run_dir="$LAGUNA_NVME_RUN_ROOT/laguna-long-mixed-depth-$tag-run"
for path in "$diagnostic_root" "$run_dir"; do
  [[ ! -e "$path" && ! -L "$path" ]] || die "path already exists: $path"
done

laguna_nvme_prepare_paths
mkdir -m 700 "$diagnostic_root"
diagnostic_root_created=true
finalize_diagnostic() {
  local status="$?"
  trap - EXIT INT TERM
  if [[ "$diagnostic_root_created" == true ]]; then
    printf 'exit_status=%s\ncompleted_at_utc=%s\n' \
      "$status" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
      > "$diagnostic_root/wrapper-status.txt"
    chmod -R a-w "$diagnostic_root" 2>/dev/null || true
  fi
  exit "$status"
}
trap finalize_diagnostic EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

{
  printf 'schema=laguna-long-mixed-depth-diagnostic-v1\ntag=%s\n' "$tag"
  printf 'repo_head=%s\nrepo_clean=true\n' "$(git -C "$repo_root" rev-parse HEAD)"
  printf 'repeat_oracle=%s\nrepeat_oracle_sha256=%s\n' \
    "$oracle" "$(sha256sum "$oracle" | cut -d' ' -f1)"
  printf 'suite=%s\nsuite_sha256=%s\n' \
    "$suite" "$(sha256sum "$suite" | cut -d' ' -f1)"
  printf 'candidate_profile=q12\ncandidate_spec=11\ncandidate_m=12\n'
  printf 'exact_prefill_chunks=1\ngpu_memory_utilization=0.80\n'
  printf 'required_swap_layout=laguna-longctx-24g\n'
  printf 'declared_max_num_batched_tokens=%s\n' "$batched_tokens"
  printf 'declared_max_num_scheduled_tokens=auto\n'
  printf 'expected_derived_scheduled_tokens=%s\n' "$derived_scheduled_tokens"
  printf 'selected_case_ids=%s\nexpected_row_ids=%s\n' \
    "$cases" "$(IFS=,; printf '%s' "${required_case_ids[*]}")"
  printf 'scored_measurement=false\npromotable=false\n'
  printf 'q12_short_record_reference_conventional_tok_s=125.4619731637751\n'
  sha256sum "$runner" "$analyzer" "$resolved_prover" \
    "$script_dir/bench_laguna_long_context.py" \
    "$script_dir/serve_laguna_long_context_nvme.sh"
} > "$diagnostic_root/identity.txt"

# The identity frozen by the 2026-08-02 mixed-depth preregistration: q12 with
# the exact-prefill selector on, segmented DFlash plus inline attention on, GPU
# utilization 0.80, and the 24 GiB swap layout with its memory guards. The
# exact-prefill selector in particular is not optional: the repeat oracle was
# produced with it on, so turning it off would change the prefill path and fail
# every row's oracle check.
env \
  LAGUNA_LONG_CANDIDATE_PROFILE=q12 \
  LAGUNA_EXACT_PREFILL_CHUNKS=1 \
  LAGUNA_MAX_MODEL_LEN=32768 \
  LAGUNA_MAX_NUM_BATCHED_TOKENS="$batched_tokens" \
  LAGUNA_MAX_NUM_SCHEDULED_TOKENS=auto \
  LAGUNA_GPU_UTIL=0.80 \
  LAGUNA_MIN_MEM_AVAILABLE_KB=8388608 \
  LAGUNA_MIN_SWAP_FREE_KB=4194304 \
  LAGUNA_MIN_SWAP_TOTAL_KB=25165816 \
  LAGUNA_REQUIRED_SWAP_LAYOUT=laguna-longctx-24g \
  LAGUNA_LONG_CASE_IDS="$cases" \
  LAGUNA_LONG_ORACLE="$oracle" \
  LAGUNA_REQUIRE_ORACLE=1 \
  "$runner" candidate "$run_dir" 2>&1 | tee "$diagnostic_root/run.stdout"

# Prove what was actually in force before reading any number the run produced.
"$python" "$resolved_prover" \
  --server-log "$run_dir/server.log" \
  --expected-batched-tokens "$batched_tokens" \
  --expected-scheduled-tokens "$derived_scheduled_tokens" \
  --out "$diagnostic_root/resolved-cache-partition.json" \
  2>&1 | tee "$diagnostic_root/resolved-cache-partition.stdout"

"$python" "$analyzer" \
  --input "$run_dir/bench.json" \
  --out "$diagnostic_root/mixed-depth-feasibility.json" \
  2>&1 | tee "$diagnostic_root/analyzer.stdout"
