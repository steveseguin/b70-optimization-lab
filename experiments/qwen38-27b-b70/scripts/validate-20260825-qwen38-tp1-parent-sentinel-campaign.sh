#!/usr/bin/env bash
set -euo pipefail

# Static validator/plan renderer only. Deliberately contains no launch path.
# A launch wrapper must freeze copies of these inputs and delegate server
# mechanics to the referenced rolling strict runner.

script=$(realpath -e -- "${BASH_SOURCE[0]}")
repo=$(git -C "$(dirname -- "$script")" rev-parse --show-toplevel)
contract=$repo/experiments/qwen38-27b-b70/data/2026-08-25-qwen38-b2dd9ce73d-tp1-parent-sentinel-campaign.json
note=$repo/experiments/qwen38-27b-b70/notes/2026-08-25-qwen38-b2dd9ce73d-tp1-parent-sentinel-preregistration.md
builder=$repo/experiments/qwen38-27b-b70/scripts/build-20260825-qwen38-tp1-context-sentinel-suite.py
runner=$repo/experiments/qwen38-27b-b70/scripts/run-20260823-qwen38-rolling-nightly-strict-smoke.sh
suite=$repo/patches/qwen36-27b-autoround-int4-b70/batch-invariant-rmsnorm-20260817/validation-suite.json
context_suite=$repo/experiments/qwen38-27b-b70/data/2026-08-25-qwen38-b2dd9ce73d-tp1-context-sentinel-suite.json
baseline=${QUALITY_BASELINE:-/mnt/usb-models/bench-results/qwen38-27b-autoround-int4-b70/nightly-strict-20260823/tp1-mtp0-f16-graph-seed0-natural-eos-replay-a-baseline-quality/quality.json}

die() { echo "error: $*" >&2; exit 1; }
check_sha() {
  local path=$1 expected=$2
  [[ -f $path ]] || die "missing input: $path"
  [[ $(sha256sum "$path" | awk '{print $1}') == "$expected" ]] ||
    die "hash mismatch: $path"
}

mode=${1:---validate}
case $mode in
  --validate|--validate-repo-only|--render-plan) ;;
  --help)
    echo "usage: $(basename "$0") [--validate|--validate-repo-only|--render-plan]"
    echo "This preregistration validator never launches Docker, a server, or a GPU run."
    exit 0
    ;;
  *) die "unknown argument: $1 (launch is intentionally unavailable)" ;;
esac

jq -e '
  .state == "preregistered-not-launched" and
  .coverage_axes.decision_state_count == 210 and
  .coverage_axes.mtp_depth == [0,1,2,3,4] and
  .coverage_axes.graph == ["off","on"] and
  .coverage_axes.kv_cache_dtype == ["float16","fp8_e4m3","fp8_e5m2"] and
  .coverage_axes.active_context_tokens == [0,2048,4096,8192,16384,24576,32768] and
  .coverage_axes.serving_context_probe_input_tokens == [2048,4096,8192,16384,24576,32000] and
  (.coverage_axes.short_suite | startswith("separate evidence type")) and
  (.parents | length) == 6 and
  ([.parents[].id] | unique | length) == 6 and
  ([.parents[].port] | unique | length) == 6 and
  ([.parents[].root] | unique | length) == 6 and
  ([.parents[].cache] | unique | length) == 6 and
  .banked_cell.must_not_rerun_for_coverage == true and
  (.banked_cell.cell | contains("outside-active-context-axis")) and
  .banked_cell.strict_a_decode_tok_s == 30.280007107732555 and
  .frozen_identity.vllm_commit == "b2dd9ce73dce2ad09007d1db5c171454118981d7" and
  .frozen_identity.xpu_kernel_commit == "1e90ffa672ba02f17a909da11838a4c55b199783" and
  .frozen_identity.weight_revision == "Qwen3.8-27B only" and
  .frozen_identity.common_server.gpu_memory_utilization == 0.9 and
  .frozen_identity.pythonhashseed == "0" and
  .frozen_inputs.context_suite == "experiments/qwen38-27b-b70/data/2026-08-25-qwen38-b2dd9ce73d-tp1-context-sentinel-suite.json" and
  .frozen_inputs.context_suite_sha256 == "e8a8a470c8e0a9f6e73460e8d5e01d42d13659faf447e289ca4803c7aa7a683f" and
  .runner_mapping."p1-context-spine".argv[6] == .frozen_inputs.context_suite and
  .protected_speed_evidence.manifest_sha256 == "4eb3eeb81e40099a64ba0444743074e6b044295ff566c1abc11d864902abb454" and
  .protected_speed_evidence.canonical_values_sha256 == "e6ee2cb9908ce940087788243eac5b544c0d2831b94efa47fe6441232c740e8f" and
  .protected_speed_evidence.tp1_pinned_diagnostic == [30.2178,30.2569] and
  .protected_speed_evidence.tp1_pinned_strict == [30.31067504052998] and
  .protected_speed_evidence.tp2_pinned_diagnostic == [48.8301,48.950458800865434] and
  .protected_speed_evidence.tp2_pinned_strict == [49.01965141150585] and
  .protected_speed_evidence.tp4_pinned_diagnostic == [71.6741,71.5488] and
  .protected_speed_evidence.tp4_pinned_strict == [71.29326283364946,71.39843006187554] and
  .protected_speed_evidence.a356_stock_tp4_strict == [71.9001988117144,71.2457420049019] and
  .protected_speed_evidence."0ecc_stock_tp1_strict" == [30.324297716696414,30.325970521145816] and
  .protected_speed_evidence.tp2_overlay_diagnostic == [49.05894025767351] and
  .protected_speed_evidence.tp2_overlay_strict == [49.00935245117815] and
  .protected_speed_evidence.tp4_overlay_diagnostic == [71.72254506718171] and
  .protected_speed_evidence.tp4_overlay_strict == [71.35287190161719,71.45427094575045]
' "$contract" >/dev/null || die "campaign contract invariant failed"

check_sha "$suite" 292dea6aaf60f53067fb63c9bc5aba15bd1c6e71c2601693e6750239edf9fa0c
check_sha "$context_suite" e8a8a470c8e0a9f6e73460e8d5e01d42d13659faf447e289ca4803c7aa7a683f
check_sha "$runner" cb2bfd95e7ad9956dae5bc22ccfa575c8742847c963143291a21505533598202
[[ -f $note && -f $builder ]] || die "new packet is incomplete"

if [[ $mode == --validate ]]; then
  check_sha "$baseline" 738b8ed03746ed976c157bf9c392a2637de7c477b719c55f2d533b398adbef18
fi

if [[ $mode == --render-plan ]]; then
  jq '{campaign_id,state,banked_cell,coverage_axes,parents,quality_contract,status_resolution,cleanup_contract}' "$contract"
elif [[ $mode == --validate-repo-only ]]; then
  printf 'PASS %s (repo-local inputs only; external baseline not checked; no launch performed)\n' "$(jq -r .campaign_id "$contract")"
else
  printf 'PASS %s (static only; no launch performed)\n' "$(jq -r .campaign_id "$contract")"
fi
