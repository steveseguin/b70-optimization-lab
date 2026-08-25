#!/usr/bin/env bash
set -euo pipefail

# Static validator only. It cannot launch Docker, a model, or a GPU run.

script=$(realpath -e -- "${BASH_SOURCE[0]}")
repo=$(git -C "$(dirname -- "$script")" rev-parse --show-toplevel)
lane=$repo/experiments/qwen38-27b-b70
contract=$lane/data/2026-08-25-qwen38-b2dd9ce73d-tp2-zero-overlay-r1-prereg.json
note=$lane/notes/2026-08-25-qwen38-b2dd9ce73d-tp2-zero-overlay-r1-prereg.md
freeze=$lane/data/2026-08-25-qwen38-b2dd9ce73d-campaign-freeze.json
runner=$lane/scripts/run-20260823-qwen38-rolling-nightly-strict-smoke.sh
suite=$repo/patches/qwen36-27b-autoround-int4-b70/batch-invariant-rmsnorm-20260817/validation-suite.json
model_manifest=$repo/repro/qwen38-27b-autoround-int4-b70/manifests/model.json
baseline=${QUALITY_BASELINE:-/mnt/usb-models/bench-results/qwen38-27b-autoround-int4-b70/nightly-strict-20260823/tp2-mtp0-f16-graph-natural-eos-replay-b-baseline-quality/quality.json}

die() { printf 'error: %s\n' "$*" >&2; exit 1; }
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
    printf 'usage: %s [--validate|--validate-repo-only|--render-plan]\n' "$(basename -- "$0")"
    printf 'Static only; this script has no launch path.\n'
    exit 0
    ;;
  *) die "unknown argument: $mode" ;;
esac

jq -e '
  .state == "preregistered-not-launched" and
  .launch_host == "four-B70 measuring host only" and
  .frozen_identity.vllm_commit == "b2dd9ce73dce2ad09007d1db5c171454118981d7" and
  .frozen_identity.xpu_kernel_commit == "1e90ffa672ba02f17a909da11838a4c55b199783" and
  .frozen_identity.image_id == "sha256:059d4b3ee881c2a54d801518d59fd26b4e3c3af8840f4c18187c8b28000bc296" and
  .frozen_identity.overlay == "none" and
  .topology.tensor_parallel == 2 and
  .topology.gpus == "0,1" and
  .topology.mtp_depth == 0 and
  .topology.kv_cache_dtype == "float16" and
  .topology.graph.enabled == true and
  .topology.graph.capture_sizes == [1,2] and
  ([.arms[].id] == ["diagnostic","strict-a","strict-b"]) and
  .arms[0].cache_policy == "fresh" and
  .arms[1].cache_policy == "replay" and
  .arms[2].cache_policy == "replay" and
  .arms[1].quality == true and
  .execution_policy.atomic == true and
  .execution_policy.continue_after_speed_miss_if_non_speed_gates_pass == true and
  .execution_policy.explicit_acknowledgement == "RUN_QWEN38_B2DD_TP2_ZERO_OVERLAY_R1" and
  .protected_speed_comparisons_tok_s.diagnostic_floor == 48.8301 and
  .protected_speed_comparisons_tok_s.strict_floor == 49.01965141150585 and
  .protected_speed_comparisons_tok_s.speed_controls_execution == false and
  .protected_speed_comparisons_tok_s.lowering_or_replacement_allowed == false
' "$contract" >/dev/null || die 'TP2 contract invariant failed'

check_sha "$freeze" 54f6303a7864cb2263818bc55370606df2535c689a06011dd97d2eddcbd8ac2c
check_sha "$runner" cb2bfd95e7ad9956dae5bc22ccfa575c8742847c963143291a21505533598202
check_sha "$suite" 292dea6aaf60f53067fb63c9bc5aba15bd1c6e71c2601693e6750239edf9fa0c
check_sha "$model_manifest" 731d851b39d37f3d58c5a74ad6a7cd3ade1c9e8543ef1612a5d55131ff8331b8
[[ -f $note ]] || die "missing note: $note"

if [[ $mode == --validate ]]; then
  check_sha "$baseline" 0ba49be19bbb081023259ce290f87990d3e26038e461d136862631442a63bc48
fi

if [[ $mode == --render-plan ]]; then
  jq '{campaign_id,state,purpose,frozen_identity,topology,paths,arms,non_speed_gates,protected_speed_comparisons_tok_s,execution_policy,follow_up}' "$contract"
elif [[ $mode == --validate-repo-only ]]; then
  printf 'PASS %s (repo-local inputs only; external baseline not checked; no launch performed)\n' "$(jq -r .campaign_id "$contract")"
else
  printf 'PASS %s (static only; no launch performed)\n' "$(jq -r .campaign_id "$contract")"
fi
