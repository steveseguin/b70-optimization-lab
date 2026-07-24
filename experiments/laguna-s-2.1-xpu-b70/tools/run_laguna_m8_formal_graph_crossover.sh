#!/usr/bin/env bash
# One-shot preregistered A1/B1 -> B2/A2 Laguna graph crossover controller.
set -euo pipefail
umask 077

readonly frozen_path=/home/steve/.venvs/deepseek-v4-xpu/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export PATH="$frozen_path"
export PYTHONDONTWRITEBYTECODE=1

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=laguna_nvme_paths.sh
source "$script_dir/laguna_nvme_paths.sh"

campaign_root="${1:?usage: run_laguna_m8_formal_graph_crossover.sh CAMPAIGN_ROOT}"
(( $# == 1 )) || { echo "exactly one campaign root is required" >&2; exit 2; }

readonly repo_root=/home/steve/llm-optimizations
readonly python=/home/steve/.venvs/deepseek-v4-xpu/bin/python
readonly runner="$script_dir/run_laguna_m8_formal_graph_crossover_leg.sh"
readonly analyzer="$script_dir/analyze_laguna_m8_graph_crossover.py"
readonly comparator="$script_dir/compare_exact_runs.py"
readonly teacher="$LAGUNA_NVME_RUN_ROOT/bulletproof-q1-canonical-cb616c6-6fc06b0-20260722T142908Z/bench.json"
readonly a1="$campaign_root/A1-eager"
readonly b1="$campaign_root/B1-graph"
readonly b2="$campaign_root/B2-graph"
readonly a2="$campaign_root/A2-eager"

die() {
  echo "Laguna formal M8 graph crossover: $*" >&2
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
for path in "$runner" "$analyzer" "$comparator" "$teacher"; do
  [[ -f "$path" ]] || die "required formal tool is missing: $path"
done

laguna_nvme_prepare_run_dir "$campaign_root"
chmod 700 -- "$campaign_root"
{
  printf 'schema=laguna-m8-formal-graph-crossover-controller-v1\n'
  printf 'order=A1-eager,B1-graph,B2-graph,A2-eager\n'
  printf 'phase1_stop=true\nrescue_runs=forbidden\n'
  printf 'qualification_timing_inputs=forbidden\n'
  sha256sum "$0" "$runner" "$analyzer" "$comparator"
} > "$campaign_root/controller-identity.txt"

run_leg() {
  local treatment="$1" label="$2" directory="$3"
  /usr/bin/env -i PATH="$frozen_path" LANG=C.UTF-8 LC_ALL=C.UTF-8 \
    bash "$runner" "$treatment" "$label" "$directory" \
    > "$campaign_root/${label}.controller.stdout" \
    2> "$campaign_root/${label}.controller.stderr"
}

run_leg eager A1 "$a1"
run_leg graph B1 "$b1"

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
  echo "Laguna formal M8 graph crossover stopped after failed phase 1: $campaign_root"
  exit 0
fi

run_leg graph B2 "$b2"
run_leg eager A2 "$a2"

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
echo "Laguna formal M8 graph crossover complete: $campaign_root"
