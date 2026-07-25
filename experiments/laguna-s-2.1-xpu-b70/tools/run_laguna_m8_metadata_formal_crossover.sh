#!/usr/bin/env bash
# One-shot preregistered Laguna graph metadata A1/B1 -> B2/A2 controller.
set -euo pipefail
umask 077

readonly frozen_path=/home/steve/.venvs/deepseek-v4-xpu/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export PATH="$frozen_path"
export PYTHONDONTWRITEBYTECODE=1

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=laguna_nvme_paths.sh
source "$script_dir/laguna_nvme_paths.sh"

campaign_root="${1:?usage: run_laguna_m8_metadata_formal_crossover.sh CAMPAIGN_ROOT}"
(( $# == 1 )) || { echo "exactly one campaign root is required" >&2; exit 2; }

readonly repo_root=/home/steve/llm-optimizations
readonly python=/home/steve/.venvs/deepseek-v4-xpu/bin/python
readonly runner="$script_dir/run_laguna_m8_metadata_formal_crossover_leg.sh"
readonly analyzer="$script_dir/analyze_laguna_m8_metadata_crossover.py"
readonly analyzer_test="$script_dir/test_analyze_laguna_m8_metadata_crossover.py"
readonly base_parser="$script_dir/analyze_shared_elementwise_qknorm_stack_crossover.py"
readonly graph_serve="$script_dir/serve_laguna_m8_metadata_graph_nvme.sh"
readonly nvme_paths="$script_dir/laguna_nvme_paths.sh"
readonly comparator="$script_dir/compare_exact_runs.py"
readonly teacher="$LAGUNA_NVME_RUN_ROOT/bulletproof-q1-canonical-cb616c6-6fc06b0-20260722T142908Z/bench.json"
readonly a1="$campaign_root/A1-graph-metadata-off"
readonly b1="$campaign_root/B1-graph-metadata-on"
readonly b2="$campaign_root/B2-graph-metadata-on"
readonly a2="$campaign_root/A2-graph-metadata-off"

die() {
  echo "Laguna formal M8 metadata crossover: $*" >&2
  exit 2
}

seal_campaign() {
  [[ -d "$campaign_root" ]] && chmod -R a-w -- "$campaign_root" || true
}
trap 'status=$?; seal_campaign; exit "$status"' EXIT

[[ "$campaign_root" == "$LAGUNA_NVME_RUN_ROOT"/* ]] \
  || die "campaign root must be below the fixed NVMe run root"
[[ "$(realpath -m -- "$campaign_root")" == "$campaign_root" ]] \
  || die "campaign root must already be canonical"
laguna_nvme_prepare_paths
laguna_nvme_assert_fresh_run_path "$campaign_root"
[[ -z "$(git -C "$repo_root" status --short)" ]] || die "main worktree is dirty"
for path in \
  "$runner" "$analyzer" "$analyzer_test" "$base_parser" "$graph_serve" \
  "$nvme_paths" "$comparator" "$teacher"; do
  [[ -f "$path" ]] || die "required formal tool is missing: $path"
done

laguna_nvme_prepare_run_dir "$campaign_root"
chmod 700 -- "$campaign_root"
{
  printf 'schema=laguna-m8-metadata-formal-crossover-controller-v1\n'
  printf 'order=A1-graph-metadata-off,B1-graph-metadata-on,B2-graph-metadata-on,A2-graph-metadata-off\n'
  printf 'phase1_stop=true\nrescue_runs=forbidden\n'
  printf 'qualification_timing_inputs=forbidden\n'
  printf 'graph_runtime_fixed=true\n'
  printf 'treatment_selector=VLLM_XPU_LAGUNA_M8_PREBUILT_EXACT_ATTN_METADATA\n'
  printf 'control_selector=0\ncandidate_selector=1\n'
  printf 'capture_attention_graphs=0\nsuite_invocations_per_start=1\n'
  printf 'warmup_generations=0\nretries=0\n'
  sha256sum \
    "$0" "$runner" "$graph_serve" "$analyzer" "$analyzer_test" \
    "$base_parser" "$nvme_paths" "$comparator"
} > "$campaign_root/controller-identity.txt"

run_leg() {
  local treatment="$1" label="$2" directory="$3"
  /usr/bin/env -i PATH="$frozen_path" LANG=C.UTF-8 LC_ALL=C.UTF-8 \
    bash "$runner" "$treatment" "$label" "$directory" \
    > "$campaign_root/${label}.controller.stdout" \
    2> "$campaign_root/${label}.controller.stderr"
}

run_leg control A1 "$a1"
run_leg candidate B1 "$b1"

"$python" "$analyzer" \
  --a1 "$a1" \
  --b1 "$b1" \
  --out "$campaign_root/phase1-analysis.json" \
  --markdown-out "$campaign_root/phase1-analysis.md" \
  > "$campaign_root/phase1-analysis.stdout"

if ! jq -e '
  .analysis_mode == "phase1_a1_b1" and
  .phase1_pass == true and
  .disposition == "phase1_pass_continue_to_full_abba"
' "$campaign_root/phase1-analysis.json" >/dev/null; then
  printf 'status=PHASE1_STOP\n' > "$campaign_root/status.txt"
  echo "Laguna formal M8 metadata crossover stopped after failed phase 1: $campaign_root"
  exit 0
fi

run_leg candidate B2 "$b2"
run_leg control A2 "$a2"

"$python" "$comparator" \
  --teacher "$teacher" \
  --candidate "$a1/bench.json" \
  --candidate "$b1/bench.json" \
  --candidate "$b2/bench.json" \
  --candidate "$a2/bench.json" \
  --out "$campaign_root/all-vs-teacher.json" \
  > "$campaign_root/all-vs-teacher.stdout"
"$python" "$comparator" \
  --teacher "$a1/bench.json" \
  --candidate "$b1/bench.json" \
  --candidate "$b2/bench.json" \
  --candidate "$a2/bench.json" \
  --out "$campaign_root/cross-leg.json" \
  > "$campaign_root/cross-leg.stdout"

"$python" "$analyzer" \
  --a1 "$a1" \
  --b1 "$b1" \
  --b2 "$b2" \
  --a2 "$a2" \
  --all-vs-teacher "$campaign_root/all-vs-teacher.json" \
  --cross-leg "$campaign_root/cross-leg.json" \
  --out "$campaign_root/full-analysis.json" \
  --markdown-out "$campaign_root/full-analysis.md" \
  > "$campaign_root/full-analysis.stdout"

jq -r '"status=" + .disposition' "$campaign_root/full-analysis.json" \
  > "$campaign_root/status.txt"
echo "Laguna formal M8 metadata crossover complete: $campaign_root"
