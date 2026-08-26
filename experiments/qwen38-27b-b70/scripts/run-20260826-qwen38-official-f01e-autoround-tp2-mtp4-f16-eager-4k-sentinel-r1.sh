#!/usr/bin/env bash
set -uo pipefail

repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)
campaign=qwen38-official-f01e-autoround-tp2-mtp4-f16-eager-4k-sentinel-20260826-r1
ack_expected="RUN $campaign"
manifest="$repo/experiments/qwen38-27b-b70/data/2026-08-26-qwen38-official-f01e-autoround-tp2-mtp4-f16-eager-4k-sentinel-r1-prereg.json"
note="$repo/experiments/qwen38-27b-b70/notes/2026-08-26-qwen38-official-f01e-autoround-tp2-mtp4-f16-eager-4k-sentinel-r1-preregistration.md"
self=$(realpath -- "${BASH_SOURCE[0]}")
test_file="$repo/experiments/qwen38-27b-b70/scripts/test_qwen38_official_f01e_autoround_tp2_mtp4_f16_eager_4k_sentinel_r1.py"
proven_tp_cache_launcher="$repo/experiments/qwen38-27b-b70/scripts/run-20260823-qwen38-rolling-nightly-strict-smoke.sh"
protected_manifest="$repo/experiments/qwen38-27b-b70/data/2026-08-23-qwen38-current-main-overlay-manifest.json"
model=/mnt/usb-models/llm-models/qwen3.8-27b-int4-autoround-devan
model_manifest="$repo/repro/qwen38-27b-autoround-int4-b70/manifests/model.json"
model_verifier="$repo/repro/qwen38-27b-autoround-int4-b70/scripts/verify-model-direct.py"
fixture="$repo/data/qwen27-exact-depth/qwen38-bce40ca-exact-depth-v1.json"
depth_helper="$repo/scripts/bench-openai-token-depth-suite.py"
quality_helper="$repo/scripts/qwen38-text-quality-suite.py"
target_root=/mnt/fast-ai/bench-results/qwen38-official-f01e-autoround-tp2-mtp0-f16-eager-depth-expansion-20260826-r1
quality_baseline="$target_root/quality.json"
target_4k="$target_root/exact-depth/depth-4096.json"
target_terminal="$target_root/terminal-receipt.json"
parent_root=/mnt/fast-ai/bench-results/qwen38-official-f01e-autoround-tp2-mtp3-f16-eager-depth-expansion-20260826-r1
parent_terminal="$parent_root/terminal-receipt.json"
parent_arm="$parent_root/arm-result.json"
parent_quality="$parent_root/quality.json"
parent_4k="$parent_root/exact-depth/depth-4096.json"
parent_verify_4k="$parent_root/verification/depth-4096.json"
prior_mtp4_8k="$repo/experiments/qwen38-27b-b70/data/2026-08-26-qwen38-official-f01e-autoround-tp2-mtp4-f16-eager-8k-sentinel-r1-result.json"
model_config="$model/config.json"
model_index="$model/model.safetensors.index.json"
mtp_tensors="$model/model_extra_tensors.safetensors"
quant_config="$model/quantization_config.json"
venv_python=/home/steve/.venvs/vllm-xpu/bin/python
image_ref=vllm/vllm-openai-xpu@sha256:f01e24f6c7ff01f1e0662234255a1372297d1dbd89d003cf13c8fad3eab1ba4f
image_id=sha256:f01e24f6c7ff01f1e0662234255a1372297d1dbd89d003cf13c8fad3eab1ba4f
vllm_head=ac7509e2b1db40fec2f03dde1ed4e9dfdc2338c9
root=/mnt/fast-ai/bench-results/$campaign
cache_root=/home/steve/qwen38-current-main-runs/cache-official-f01e-autoround-tp2-mtp4-f16-eager-4k-sentinel-20260826-r1
port=19518
name=q38-f01e-ar-tp2-mtp4-f16-4k-r1
served_model=qwen38-official-f01e-autoround-tp2-mtp4
sudo_pass_file=${SUDO_PASS_FILE:-/home/steve/SUDOPASSWORD.txt}

active_name=
active_dir=

die() { printf 'error: %s\n' "$*" >&2; exit 2; }

dockerc() {
  if docker info >/dev/null 2>&1; then
    docker "$@"
  elif [[ -r "$sudo_pass_file" ]]; then
    sudo -S -p '' docker "$@" < "$sudo_pass_file"
  else
    return 126
  fi
}

cleanup_active() {
  [[ -n "$active_name" ]] || return 0
  if [[ -n "$active_dir" && -d "$active_dir" ]]; then
    dockerc logs "$active_name" > "$active_dir/server.log" 2>&1 || true
    dockerc inspect "$active_name" > "$active_dir/container-inspect.json" 2>/dev/null || true
  fi
  dockerc rm -f "$active_name" >/dev/null 2>&1 || true
  if ! dockerc inspect "$active_name" >/dev/null 2>&1; then
    active_name=
    active_dir=
  fi
}

cleanup_on_exit() {
  local rc=$?
  trap - EXIT INT TERM
  cleanup_active
  [[ -z "$active_name" ]] || rc=90
  exit "$rc"
}
trap cleanup_on_exit EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

sha_is() {
  local path=$1 expected=$2 observed
  [[ -f "$path" ]] || die "missing frozen input: $path"
  observed=$(sha256sum "$path" | awk '{print $1}') || die "cannot hash $path"
  [[ "$observed" == "$expected" ]] || die "frozen input changed: $path ($observed)"
}

static_check() {
  sha_is "$protected_manifest" 4eb3eeb81e40099a64ba0444743074e6b044295ff566c1abc11d864902abb454
  sha_is "$fixture" ebe507b725af6ec0713de4084d0bf52fbbab48b151511e0019c1bac2c5051bd9
  sha_is "$model_manifest" 731d851b39d37f3d58c5a74ad6a7cd3ade1c9e8543ef1612a5d55131ff8331b8
  sha_is "$model_verifier" 5bca853ae644099cb18c58b458dd04dfcc0844d7644f074c4350539504d80ce9
  sha_is "$depth_helper" 8f162c1ab9fde7e0daffed2c4f0d6ff061ad6076c5de716e36f3d883ab4a1067
  sha_is "$quality_helper" 67e65fc342393e5ae6903a332c929b3a2693e1f943c8a819b8447284fe835f6d
  sha_is "$quality_baseline" ef15f39a848d262a4582b1ab6c9a2f10713ecfbcae02497bc4462c8ae5a3af96
  sha_is "$proven_tp_cache_launcher" cb2bfd95e7ad9956dae5bc22ccfa575c8742847c963143291a21505533598202
  sha_is "$target_4k" 6e32b0a05f7e355bf21c5e3ebd0e04a16fbf3d54bc39890aa8740b3a5430f187
  sha_is "$target_terminal" 63fe2e8a85db47af331743b93b1c6e181f930775104f19483eb7b9e1da0f2c60
  sha_is "$parent_terminal" 977a0aba4fed5510fb8ec568e3a9eb99df4f86a872478878e8c85d147899b64c
  sha_is "$parent_arm" ed3f1b46ac8a6a6ed4ec5592a9a7621e82e1d5a8b59a30c73adc04af41b8ec2f
  sha_is "$parent_quality" f74046dd65642d9fa8cb177fed12bba27bbdeada1a7ff8fb5273bf3966245e2b
  sha_is "$parent_4k" daf7201c641185f1dd4e54ff1661c7a817d49979afe0d06c3661ef5e2bad1ec7
  sha_is "$parent_verify_4k" b1f0b4701936c4b7ca7cb5ca9e85ab91e394336ebca8b0cd1fed79a9dbc6a756
  sha_is "$prior_mtp4_8k" ae0828434248862bc9eaa8bcb82fe6a74d20b8007dc186b3f72477e68a38a3d3
  sha_is "$model_config" 9a1c29a807e34529bec03cba92b4dc00ba61e37a703b029b08a3142b6dc08cd1
  sha_is "$model_index" adf387dee183d109e95cdc4d4988fcd966de326861ff4d66876692170f1e03ad
  sha_is "$mtp_tensors" 94102b67c6b84e65dbb9bae37c00bd88ac1a43ff577ce65fd8842d231c7e89de
  sha_is "$quant_config" 0d1be50a7ad0a3c7350b4b4a4c8c1d26412d2cb2f1503e3ea21b40f1b8470c14
  jq -e '
    .status == "passed" and .gate.passed == true and
    .run_identity.depth == 4096 and .run_identity.max_tokens == 128 and
    .response.output_token_ids_sha256 == "3febb16ef2033c31e17817c6753ccdb95ad6e39db394ed4476ee12fb86af78b0" and
    (.response.token_ids|length) == 128 and
    .gate.checks.cached_tokens_zero == true and
    .gate.checks.request_prompt_depth_exact == true and
    .gate.checks.stream_token_ids_exact == true
  ' "$target_4k" >/dev/null || die "frozen same-topology TP2 target oracle failed"
  jq -e '
    .terminal == true and .state == "passed-quality-clean-depth-expansion" and
    .runner_return_code == 0 and
    .arm.frozen_same_topology_oracle_depths == [2048,4096,8192,16384,24576,32768] and
    .arm.objective_quality_passed == true and .arm.tp2_worker_topology_passed == true and
    .arm.rank_cache_isolation_passed == true and .arm.cleanup_passed == true
  ' "$target_terminal" >/dev/null || die "frozen same-topology TP2/MTP0 terminal receipt failed"
  jq -e '
    .terminal == true and .state == "passed-quality-clean-depth-expansion" and
    .runner_return_code == 0 and .automatic_descendant_expansion == false and
    .arm.state == "passed-quality-clean-depth-expansion" and
    .arm.passed_depth_count == 5 and .arm.passed_acceptance_count == 5 and
    .arm.passed_same_topology_target_count == 5 and
    .arm.frozen_same_topology_oracle_depths == [4096,8192,16384,24576,32768] and
    .arm.failed_or_quarantined_depths == [] and
    .arm.objective_quality_passed == true and .arm.same_topology_baseline_passed == true and
    .arm.tp2_worker_topology_passed == true and .arm.rank_cache_isolation_passed == true and
    .arm.cleanup_passed == true and .arm.descendant_execution_authorized == false and
    (.arm.depth_receipts | map(select(.depth == 4096))[0] |
      .return_code == 0 and .exact_passed == true and .per_depth_valid == true and
      .acceptance_passed == true and .target_parity_passed == true and
      .verification.acceptance.drafted_tokens == 123 and
      .verification.acceptance.accepted_tokens == 86 and
      .verification.candidate_ids_sha256 == "3febb16ef2033c31e17817c6753ccdb95ad6e39db394ed4476ee12fb86af78b0" and
      .verification.same_topology_target_verification.passed == true)
  ' "$parent_terminal" >/dev/null || die "frozen TP2/MTP3 scoped parent terminal failed"
  jq -e '
    .state == "passed-quality-clean-depth-expansion" and .passed_depth_count == 5 and
    .passed_acceptance_count == 5 and .passed_same_topology_target_count == 5 and
    .objective_quality_passed == true and .same_topology_baseline_passed == true and
    .tp2_worker_topology_passed == true and .rank_cache_isolation_passed == true and
    .cleanup_passed == true and .descendant_execution_authorized == false
  ' "$parent_arm" >/dev/null || die "frozen TP2/MTP3 scoped parent arm failed"
  jq -e '
    .pass_all == true and .baseline_match_all == true and
    (.exact_cases | length) == 7 and (.repeat_case.runs | length) == 8 and
    ([.exact_cases[].usage, .repeat_case.runs[].usage, .long_context_case.usage] |
      length == 16 and all(.[]; .prompt_tokens_details.cached_tokens == 0))
  ' "$parent_quality" >/dev/null || die "frozen TP2/MTP3 scoped parent quality failed"
  jq -e '
    .status == "passed" and .gate.passed == true and .run_identity.depth == 4096 and
    .run_identity.max_tokens == 128 and (.response.token_ids | length) == 128 and
    .response.output_token_ids_sha256 == "3febb16ef2033c31e17817c6753ccdb95ad6e39db394ed4476ee12fb86af78b0" and
    .gate.checks.cached_tokens_zero == true and .gate.checks.request_prompt_depth_exact == true
  ' "$parent_4k" >/dev/null || die "frozen TP2/MTP3 scoped parent 4K depth failed"
  jq -e '
    .depth == 4096 and .candidate_ids_sha256 == "3febb16ef2033c31e17817c6753ccdb95ad6e39db394ed4476ee12fb86af78b0" and
    .acceptance.passed == true and .acceptance.drafted_tokens == 123 and
    .acceptance.accepted_tokens == 86 and
    .same_topology_target_verification.passed == true and
    .same_topology_target_verification.first_divergence == null
  ' "$parent_verify_4k" >/dev/null || die "frozen TP2/MTP3 scoped parent 4K verification failed"
  jq -e '
    .status == "quarantined-target-parity-failed" and
    .diagnostic_point.x == 8192 and .diagnostic_point.cached_tokens == 0 and
    .diagnostic_point.site_speed_publication == false and
    .target_failure.passed == false and
    .target_failure.first_divergence.one_based == 99 and
    .target_failure.first_divergence.candidate == 411 and
    .target_failure.first_divergence.target == 579 and
    .authority.site_measured_speed_cells == 0 and
    .authority.diagnostic_speed_retained_only_in_evidence == true and
    .authority.automatic_depth_or_descendant_expansion == false
  ' "$prior_mtp4_8k" >/dev/null || die "frozen TP2/MTP4 exact-8K quarantine changed"
  jq -e '.text_config.mtp_num_hidden_layers == 1 and .text_config.mtp_use_dedicated_embeddings == false' \
    "$model_config" >/dev/null || die "embedded MTP config contract failed"
  jq -e '[.weight_map|to_entries[]|select(.key|startswith("mtp."))] as $m |
    ($m|length) == 29 and ([$m[].value]|unique) == ["model_extra_tensors.safetensors"]' \
    "$model_index" >/dev/null || die "embedded MTP tensor binding contract failed"
  jq -e --arg id "$campaign" --arg image "$image_ref" --arg root "$root" --argjson port "$port" '
    .schema == "neural.download.qwen38-official-autoround-tp2-mtp4-f16-eager-4k-sentinel-prereg.v1" and
    .campaign_id == $id and .state == "preregistered-not-launched" and
    .run_identity.image == $image and .run_identity.tensor_parallel == 2 and
    .run_identity.mtp_depth == 4 and
    .run_identity.speculative_config == {"method":"qwen3_next_mtp","num_speculative_tokens": 4} and
    .run_identity.startup_speculator_identity == {"method":"mtp","num_spec_tokens": 4} and
    .run_identity.kv_cache_dtype == "float16" and
    .run_identity.gpu_affinity == "0,1" and
    .run_identity.gpu_memory_utilization == 0.6 and
    .run_identity.graph_mode == "off" and .run_identity.max_model_len == 32896 and
    .exact_depth_contract.depths == [4096] and
    .execution.output_root == $root and .execution.port == $port and
    .execution.one_server_lifetime == true and
    .interpretation.historical_replacement_allowed == false and
    .interpretation.site_publication_automatic == false and
    .interpretation.failure_retains_lower_grade_evidence == true and
    .interpretation.depth_expansion_authorized == false and
    .interpretation.descendant_expansion_is_automatic == false and
    .interpretation.descendant_execution_authorized == false and
    .historical_risk.tp2_mtp4_8k_quarantine.status == "quarantined-target-parity-failed" and
    .historical_risk.tp2_mtp4_8k_quarantine.first_divergence_one_based == 99 and
    .historical_risk.tp2_mtp4_8k_quarantine.site_measured_speed_cells == 0 and
    .interpretation.protected_decode_values_unchanged == [71.45427094575045,30.329809361830037,49.05894025767351,71.9001988117144]
  ' "$manifest" >/dev/null || die "manifest invariant failed"
  bash -n "$self" || die "runner shell syntax failed"
  "$venv_python" "$test_file" >/dev/null || die "inert tests failed"
}

require_clean_pushed_main() {
  [[ "$(git -C "$repo" branch --show-current)" == main ]] || die "repository must be on main"
  [[ -z "$(git -C "$repo" status --porcelain=v1 --untracked-files=all)" ]] || die "repository must be clean"
  local head cached live
  head=$(git -C "$repo" rev-parse HEAD) || die "cannot resolve HEAD"
  cached=$(git -C "$repo" rev-parse origin/main) || die "cannot resolve cached origin/main"
  [[ "$head" == "$cached" ]] || die "local main must equal cached origin/main"
  live=$(git -C "$repo" ls-remote --exit-code origin refs/heads/main | awk '{print $1}') || die "cannot resolve live origin/main"
  [[ "$head" == "$live" ]] || die "local main must equal live origin/main"
  printf '%s\n' "$head"
}

render_users() {
  local node
  for node in /dev/dri/renderD*; do
    [[ -e "$node" ]] || continue
    fuser "$node" 2>/dev/null || true
  done
}

port_users() { ss -ltnH "sport = :$port" 2>/dev/null || true; }

require_idle() {
  [[ -z "$(dockerc ps -q)" ]] || die "a Docker container is already running"
  if pgrep -af '[E]ngineCore|[v]llm serve|[l]lama-server' >/dev/null; then
    die "a model server process is already running"
  fi
  [[ -z "$(render_users)" ]] || die "a process already owns a render node"
  [[ -z "$(port_users)" ]] || die "port $port is occupied"
  [[ ! -e "$root" ]] || die "output root already exists: $root"
  [[ ! -e "$cache_root" ]] || die "cache root already exists: $cache_root"
  [[ "$(findmnt -n -o FSTYPE -T "$(dirname "$root")")" == ext4 ]] || die "output root must be ext4"
  [[ "$(findmnt -n -o FSTYPE -T "$(dirname "$cache_root")")" == ext4 ]] || die "cache root must be ext4"
}

strict_postcleanup() {
  ! dockerc inspect "$name" >/dev/null 2>&1 || return 1
  [[ -z "$(port_users)" ]] || return 1
  ! pgrep -af '[E]ngineCore|[v]llm serve|[l]lama-server' >/dev/null || return 1
  [[ -z "$(render_users)" ]] || return 1
}

explicit_speculator_unsupported() {
  [[ -f "$root/image-id.txt" && "$(<"$root/image-id.txt")" == "$image_id" ]] || return 1
  awk '{ line=tolower($0); if (line ~ /(qwen3_next_mtp|speculative|speculator|mtp)/ && line ~ /(not supported|unsupported|unknown method|does not support)/) found=1 } END { exit(found ? 0 : 1) }' \
    "$root/server-startup.log" "$root/server.log" >/dev/null 2>&1
}

explicit_speculator_binding_failed() {
  [[ -f "$root/image-id.txt" && "$(<"$root/image-id.txt")" == "$image_id" ]] || return 1
  awk '{ line=tolower($0); if (line ~ /(qwen3_next_mtp|speculative|speculator|mtp|model_extra_tensors)/ && line ~ /(cannot load|failed to load|missing (weight|tensor)|not found|no such file)/) found=1 } END { exit(found ? 0 : 1) }' \
    "$root/server-startup.log" "$root/server.log" >/dev/null 2>&1
}

write_acceptance_and_target() {
  "$venv_python" - "$root/metrics.before.prom" "$root/metrics.after.prom" "$root/exact-depth/depth-4096.json" "$target_4k" "$root/verification-gates.json" <<'PY'
import hashlib, json, math, pathlib, re, sys
before_path, after_path, candidate_path, target_path, out_path = map(pathlib.Path, sys.argv[1:])
def metric(path, name):
    if not path.is_file(): return None
    pattern = re.compile(rf"^{re.escape(name)}(?:\{{[^}}]*\}})?\s+([-+0-9.eE]+)$")
    values = [float(m.group(1)) for line in path.read_text(errors="replace").splitlines() if (m := pattern.match(line))]
    return sum(values) if values and all(math.isfinite(value) for value in values) else None
draft_name = "vllm:spec_decode_num_draft_tokens_total"
accept_name = "vllm:spec_decode_num_accepted_tokens_total"
b_draft, a_draft = metric(before_path, draft_name), metric(after_path, draft_name)
b_accept, a_accept = metric(before_path, accept_name), metric(after_path, accept_name)
drafted = a_draft - b_draft if None not in (b_draft, a_draft) else None
accepted = a_accept - b_accept if None not in (b_accept, a_accept) else None
acceptance_pass = (
    all(isinstance(value, float) and math.isfinite(value) for value in (b_draft, a_draft, b_accept, a_accept, drafted, accepted))
    and a_draft >= b_draft and a_accept >= b_accept and drafted > 0 and 0 < accepted <= drafted
)
def ids(path):
    try: return json.loads(path.read_text())["response"]["token_ids"]
    except (OSError, KeyError, TypeError, json.JSONDecodeError): return None
candidate_ids, target_ids = ids(candidate_path), ids(target_path)
target_pass = isinstance(candidate_ids, list) and len(candidate_ids) == 128 and candidate_ids == target_ids
first_divergence = None
if isinstance(candidate_ids, list) and isinstance(target_ids, list):
    for i, (candidate, target) in enumerate(zip(candidate_ids, target_ids)):
        if candidate != target:
            first_divergence = {"zero_based": i, "one_based": i + 1, "candidate": candidate, "target": target}
            break
    if first_divergence is None and len(candidate_ids) != len(target_ids):
        first_divergence = {"zero_based": min(len(candidate_ids), len(target_ids)), "reason": "length-mismatch"}
value = {
    "acceptance": {"passed": acceptance_pass, "before_drafted_tokens": b_draft, "after_drafted_tokens": a_draft,
                   "before_accepted_tokens": b_accept, "after_accepted_tokens": a_accept,
                   "drafted_tokens": drafted, "accepted_tokens": accepted,
                   "acceptance_rate": accepted / drafted if acceptance_pass else None,
                   "conserved": acceptance_pass},
    "target_verification": {"passed": target_pass, "candidate_token_count": len(candidate_ids) if isinstance(candidate_ids, list) else None,
                            "target_token_count": len(target_ids) if isinstance(target_ids, list) else None,
                            "first_divergence": first_divergence,
                            "candidate_ids_sha256": hashlib.sha256(json.dumps(candidate_ids, separators=(",", ":")).encode()).hexdigest() if isinstance(candidate_ids, list) else None,
                            "target_ids_sha256": hashlib.sha256(json.dumps(target_ids, separators=(",", ":")).encode()).hexdigest() if isinstance(target_ids, list) else None,
                            "oracle_scope": "frozen same-image same-topology TP2/MTP0/eager/F16 exact-4K receipt; exact gate"},
}
out_path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
PY
}

quality_objective_gate() {
  jq -e '
    . as $q |
    ($q.pass_all == true) and
    (($q.exact_cases | type) == "array" and ($q.exact_cases | length) == 7) and
    (($q.repeat_case.runs | type) == "array" and ($q.repeat_case.runs | length) == 8) and
    (($q.long_context_case.usage | type) == "object") and
    ([
      $q.exact_cases[].usage,
      $q.repeat_case.runs[].usage,
      $q.long_context_case.usage
    ] | length == 16 and all(.[]; (.prompt_tokens_details.cached_tokens? == 0)))
  ' "$1"
}

write_arm_result() {
  local state=$1 reason=$2 depth_rc=$3 quality_rc=$4 startup_ok=$5 runner_rc=$6 cleanup_ok=$7 topology_ok=$8 target_ok=$9 cache_ok=${10} objective_quality_ok=${11} baseline_ok=${12}
  "$venv_python" - "$root/arm-result.json" "$state" "$reason" "$depth_rc" "$quality_rc" "$startup_ok" "$runner_rc" "$cleanup_ok" "$topology_ok" "$target_ok" "$cache_ok" "$objective_quality_ok" "$baseline_ok" <<'PY'
import datetime as dt, json, pathlib, sys
path, state, reason, depth_rc, quality_rc, startup_ok, runner_rc, cleanup_ok, topology_ok, target_ok, cache_ok, objective_quality_ok, baseline_ok = sys.argv[1:]
verification_path = pathlib.Path(path).with_name("verification-gates.json")
verification = json.loads(verification_path.read_text()) if verification_path.is_file() else {}
acceptance = verification.get("acceptance", {})
value = {
    "schema": "neural.download.qwen38-official-autoround-tp2-mtp4-f16-eager-4k-sentinel-arm.v1",
    "created_at_utc": dt.datetime.now(dt.UTC).isoformat(),
    "state": state,
    "reason": reason,
    "exact_4k_return_code": int(depth_rc),
    "quality_return_code": int(quality_rc),
    "startup_identity_passed": startup_ok == "1",
    "cleanup_passed": cleanup_ok == "1",
    "tp2_worker_topology_passed": topology_ok == "1",
    "same_topology_target_verification_passed": target_ok == "1",
    "exact_depth_and_cache_zero_passed": int(depth_rc) == 0,
    "acceptance": acceptance,
    "acceptance_passed": acceptance.get("passed") is True,
    "acceptance_conserved": acceptance.get("conserved") is True,
    "rank_cache_isolation_passed": cache_ok == "1",
    "objective_quality_passed": objective_quality_ok == "1",
    "same_topology_baseline_comparison_passed": baseline_ok == "1",
    "runner_return_code": int(runner_rc),
    "historical_replacement_allowed": False,
    "publication_authorized": False,
    "depth_expansion_authorized": False,
    "descendant_expansion_authorized": False,
    "descendant_execution_authorized": False,
    "lower_grade_evidence_retained": state != "passed-quality-clean-sentinel",
}
pathlib.Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
PY
}

terminal_receipt() {
  local launch_head=$1 runner_rc=$2
  "$venv_python" - "$root" "$campaign" "$launch_head" "$runner_rc" <<'PY'
import datetime as dt, json, pathlib, sys
root, campaign, launch_head, runner_rc = sys.argv[1:]
root = pathlib.Path(root)
arm_path = root / "arm-result.json"
arm = json.loads(arm_path.read_text()) if arm_path.is_file() else {"state": "failed", "reason": "arm-result-missing"}
receipt = {
    "schema": "neural.download.qwen38-official-autoround-tp2-mtp4-f16-eager-4k-sentinel-terminal.v1",
    "campaign_id": campaign,
    "created_at_utc": dt.datetime.now(dt.UTC).isoformat(),
    "state": arm["state"],
    "terminal": True,
    "launch_git_head": launch_head,
    "runner_return_code": int(runner_rc),
    "arm": arm,
    "historical_replacement_allowed": False,
    "protected_profiles_untouched": True,
    "publication_authorized": False,
    "depth_expansion_authorized": False,
    "descendant_execution_authorized": False,
    "automatic_descendant_expansion": False,
}
(root / "terminal-receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
PY
}

run_sentinel() {
  local startup_ok=0 depth_rc=125 quality_rc=125 runner_rc=0 cleanup_ok=0 topology_ok=0 target_ok=0 acceptance_ok=0 cache_ok=0 objective_quality_ok=0 baseline_ok=0 rank
  local state=failed reason=unknown observed_image observed_head versions healthy=0 running i
  local -a args=(
    "$model" --host 0.0.0.0 --port 8000 --trust-remote-code
    --served-model-name "$served_model"
    --tensor-parallel-size 2 --pipeline-parallel-size 1 --data-parallel-size 1
    --max-model-len 32896 --max-num-seqs 1 --max-num-batched-tokens 1024
    --gpu-memory-utilization 0.60 --dtype float16
    --reasoning-parser qwen3 --default-chat-template-kwargs '{"enable_thinking": false}'
    --enable-prompt-tokens-details --no-enable-prefix-caching
    --enable-chunked-prefill --async-scheduling --enforce-eager
    --speculative-config '{"method":"qwen3_next_mtp","num_speculative_tokens": 4}'
  )
  printf '%q ' "${args[@]}" > "$root/server-args.shell.txt"
  printf '\n' >> "$root/server-args.shell.txt"

  if ! dockerc run -d --name "$name" --device /dev/dri --group-add 44 --group-add 992 \
      --ipc=host --shm-size 16g -v /dev/dri/by-path:/dev/dri/by-path:ro \
      -v "$model:$model:ro" -v "$cache_root:/run-cache" -p "127.0.0.1:$port:8000" \
      -e ZE_AFFINITY_MASK=0,1 \
      -e VLLM_NO_USAGE_STATS=1 -e PYTHONHASHSEED=0 \
      -e VLLM_XPU_ENABLE_XPU_GRAPH=0 -e VLLM_XPU_GRAPH=0 \
      -e VLLM_CACHE_ROOT=/run-cache/vllm -e XDG_CACHE_HOME=/run-cache/xdg \
      -e CCL_ZE_IPC_EXCHANGE=sockets \
      "$image_ref" "${args[@]}" > "$root/container-id.txt"; then
    dockerc rm -f "$name" >/dev/null 2>&1 || true
    strict_postcleanup && cleanup_ok=1
    write_arm_result failed docker-run-failed 125 125 0 31 "$cleanup_ok" 0 0 0 0 0
    return 31
  fi
  active_name=$name
  active_dir=$root
  observed_image=$(dockerc inspect --format '{{.Image}}' "$name" 2>/dev/null || true)
  printf '%s\n' "$observed_image" > "$root/image-id.txt"

  for i in $(seq 1 240); do
    if curl -fsS "http://127.0.0.1:$port/health" > "$root/health.json" 2>/dev/null; then healthy=1; break; fi
    running=$(dockerc inspect --format '{{.State.Running}}' "$name" 2>/dev/null || printf false)
    [[ "$running" == true ]] || break
    sleep 5
  done
  dockerc logs "$name" > "$root/server-startup.log" 2>&1 || true
  if (( ! healthy )); then
    cleanup_active
    if explicit_speculator_unsupported; then
      state=unsupported; reason=explicit-tp2-mtp4-speculator-unsupported; runner_rc=42
    elif explicit_speculator_binding_failed; then
      state=failed; reason=explicit-tp2-mtp4-speculator-binding-failed; runner_rc=43
    else
      state=failed; reason=tp2-infrastructure-or-startup-failed; runner_rc=32
    fi
    strict_postcleanup && cleanup_ok=1
    write_arm_result "$state" "$reason" 125 125 0 "$runner_rc" "$cleanup_ok" 0 0 0 0 0
    return "$runner_rc"
  fi

  observed_head=$(dockerc exec "$name" git -C /workspace/vllm rev-parse HEAD 2>/dev/null || true)
  versions=$(dockerc exec "$name" python3 -c 'import importlib.metadata as m; print(m.version("vllm")); print(m.version("vllm-xpu-kernels"))' 2>/dev/null || true)
  printf '%s\n' "$observed_head" > "$root/vllm-source-commit.txt"
  printf '%s\n' "$versions" > "$root/stack-versions.txt"
  if [[ "$observed_image" != "$image_id" || "$observed_head" != "$vllm_head" ]] || \
     ! grep -Fxq '0.27.2rc1.dev77+gac7509e2b.xpu' "$root/stack-versions.txt" || \
     ! grep -Fxq '0.1.12.3' "$root/stack-versions.txt" || \
     ! grep -Fq 'quantization=inc' "$root/server-startup.log" || \
     ! grep -Fq 'enforce_eager=True' "$root/server-startup.log" || \
     ! grep -Fq 'kv_cache_dtype=auto' "$root/server-startup.log" || \
     ! grep -Fq "speculative_config=SpeculativeConfig(method='mtp', model='$model', num_spec_tokens=4)" "$root/server-startup.log" || \
     grep -Fq 'Graph capturing finished' "$root/server-startup.log" || \
     grep -Fq 'Compiling a graph for compile range' "$root/server-startup.log"; then
    cleanup_active
    strict_postcleanup && cleanup_ok=1
    write_arm_result failed startup-identity-or-mode-gate-failed 125 125 0 33 "$cleanup_ok" 0 0 0 0 0
    return 33
  fi
  startup_ok=1
  topology_ok=1
  for rank in 0 1; do
    grep -Eq "world_size=2 rank=$rank local_rank=$rank" "$root/server-startup.log" || topology_ok=0
  done
  grep -Fq 'world_size=2, local_world_size=2' "$root/server-startup.log" || topology_ok=0
  if (( topology_ok == 0 )); then
    cleanup_active; strict_postcleanup && cleanup_ok=1
    write_arm_result failed tp2-worker-topology-gate-failed 125 125 1 34 "$cleanup_ok" 0 0 0 0 0
    return 34
  fi
  if ! curl -fsS "http://127.0.0.1:$port/v1/models" > "$root/models.json"; then
    runner_rc=34
  fi

  mkdir "$root/exact-depth"
  curl -fsS "http://127.0.0.1:$port/metrics" > "$root/metrics.before.prom" || runner_rc=35
  "$venv_python" "$depth_helper" --execute --fixture "$fixture" --depth 4096 \
    --case-id depth-4096 --context-capacity 32896 --response-adapter vllm \
    --base-url "http://127.0.0.1:$port" --model "$served_model" \
    --timeout 900 --out "$root/exact-depth/depth-4096.json" \
    > "$root/exact-depth/depth-4096.stdout.json" \
    2> "$root/exact-depth/depth-4096.stderr.log"
  depth_rc=$?
  printf '%s\n' "$depth_rc" > "$root/exact-depth/depth-4096.rc"
  curl -fsS "http://127.0.0.1:$port/metrics" > "$root/metrics.after.prom" || runner_rc=35
  write_acceptance_and_target || runner_rc=36
  jq -e '.acceptance.passed == true and .acceptance.conserved == true' "$root/verification-gates.json" >/dev/null && acceptance_ok=1
  jq -e '.target_verification.passed == true' "$root/verification-gates.json" >/dev/null && target_ok=1

  "$venv_python" "$quality_helper" --base-url "http://127.0.0.1:$port" \
    --model "$served_model" --tokenizer "$model" --timeout 900 \
    --repeat-runs 8 --long-context-tokens 8192 \
    --request-id-prefix "$campaign" \
    --chat-template-kwargs-json '{"enable_thinking":false}' \
    --baseline-json "$quality_baseline" --require-baseline \
    --output-json "$root/quality.json" > "$root/quality.stdout.log" 2>&1
  quality_rc=$?
  quality_objective_gate "$root/quality.json" >/dev/null 2>&1 && objective_quality_ok=1
  jq -e '.baseline_match_all == true' "$root/quality.json" >/dev/null 2>&1 && baseline_ok=1
  cleanup_active
  strict_postcleanup && cleanup_ok=1
  if [[ ! -d "$cache_root/vllm/torch_compile_cache" ]] || \
     [[ -z "$(find "$cache_root/vllm/torch_compile_cache" -type f -print -quit 2>/dev/null)" ]]; then
    cache_ok=1
    printf 'graph-off: no compile artifacts\n' > "$root/rank-cache-isolation.txt"
  else
    cache_ok=1
    for rank in 0 1; do
      find "$cache_root/vllm/torch_compile_cache" -type f -path "*/rank_${rank}_0/*" -print -quit | grep -q . || cache_ok=0
    done
    find "$cache_root/vllm/torch_compile_cache" -type f | grep -Ev '/rank_[01]_0/' > "$root/shared-compile-artifacts.txt" || true
    [[ ! -s "$root/shared-compile-artifacts.txt" ]] || cache_ok=0
  fi

  if (( cleanup_ok == 0 )); then
    state=failed; reason=strict-postcleanup-failed; runner_rc=39
  elif (( runner_rc != 0 )); then
    state=failed; reason=models-or-verification-gate-failed
  elif (( cache_ok == 0 )); then
    state=failed; reason=rank-cache-isolation-gate-failed; runner_rc=38
  elif (( depth_rc != 0 )); then
    state=quarantined-exact-depth-failed; reason=exact-4k-gate-failed-diagnostic-evidence-retained; runner_rc=37
  elif (( acceptance_ok == 0 )); then
    state=quarantined-acceptance-failed; reason=isolated-positive-conserved-acceptance-gate-failed; runner_rc=38
  elif (( target_ok == 0 )); then
    state=quarantined-target-parity-failed; reason=same-topology-tp2-mtp0-exact-token-parity-failed; runner_rc=39
  elif (( quality_rc != 0 || objective_quality_ok == 0 || baseline_ok == 0 )); then
    state=quarantined-quality-failed; reason=objective-cache-zero-or-same-topology-baseline-quality-failed; runner_rc=40
  elif (( topology_ok == 1 )); then
    state=passed-quality-clean-sentinel; reason=tp2-mtp4-exact-4k-acceptance-target-quality-cache-and-cleanup-passed; runner_rc=0
  fi
  write_arm_result "$state" "$reason" "$depth_rc" "$quality_rc" "$startup_ok" "$runner_rc" "$cleanup_ok" "$topology_ok" "$target_ok" "$cache_ok" "$objective_quality_ok" "$baseline_ok"
  return "$runner_rc"
}

action=help
ack=
while (($#)); do
  case "$1" in
    --check) action=check ;;
    --plan) action=plan ;;
    --execute) action=execute ;;
    --ack) shift; (($#)) || die "--ack needs a value"; ack=$1 ;;
    *) die "unknown argument: $1" ;;
  esac
  shift
done

case "$action" in
  help)
    printf 'usage: %s --check | --plan | --execute --ack %q\n' "$self" "$ack_expected"
    ;;
  check)
    static_check
    printf '{"campaign_id":"%s","status":"PASS","launch_performed":false}\n' "$campaign"
    ;;
  plan)
    static_check
    jq '{campaign_id,state,purpose,parent_oracle,target_oracle,historical_risk,run_identity,exact_depth_contract,quality_contract,execution,terminal_classification,interpretation}' "$manifest"
    ;;
  execute)
    [[ "$ack" == "$ack_expected" ]] || die "exact acknowledgement required: $ack_expected"
    static_check
    launch_head=$(require_clean_pushed_main) || die "clean pushed main check failed"
    observed_image=$(dockerc image inspect --format '{{.Id}}' "$image_ref" 2>/dev/null || true)
    [[ "$observed_image" == "$image_id" ]] || die "exact official image is not resident"
    require_idle
    exec 9>/run/lock/neural-download-gpu-campaign.lock
    flock -n 9 || die "canonical GPU campaign lock is held"
    require_idle
    mkdir "$root" "$cache_root" || die "cannot create fresh campaign roots"
    sha256sum "$manifest" "$note" "$self" "$test_file" "$protected_manifest" \
      "$fixture" "$model_manifest" "$model_verifier" "$depth_helper" \
      "$quality_helper" "$quality_baseline" "$target_4k" "$target_terminal" \
      "$parent_terminal" "$parent_arm" "$parent_quality" "$parent_4k" "$parent_verify_4k" "$prior_mtp4_8k" "$model_config" \
      "$model_index" "$mtp_tensors" "$quant_config" > "$root/input-sha256sums.txt"
    if ! "$model_verifier" "$model_manifest" "$model" --json "$root/model-verification.json" \
        > "$root/model-verification.log" 2>&1; then
      cleanup_ok=0
      strict_postcleanup && cleanup_ok=1
      write_arm_result failed model-verification-failed 125 125 0 41 "$cleanup_ok" 0 0 0 0 0
      terminal_receipt "$launch_head" 41
      exit 41
    fi
    run_sentinel
    runner_rc=$?
    terminal_receipt "$launch_head" "$runner_rc"
    printf '{"campaign_id":"%s","terminal_receipt":"%s/terminal-receipt.json"}\n' "$campaign" "$root"
    exit "$runner_rc"
    ;;
esac
