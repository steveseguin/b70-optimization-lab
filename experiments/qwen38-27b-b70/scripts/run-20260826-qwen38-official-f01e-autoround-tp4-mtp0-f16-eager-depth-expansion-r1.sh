#!/usr/bin/env bash
set -uo pipefail

repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)
campaign=qwen38-official-f01e-autoround-tp4-mtp0-f16-eager-depth-expansion-20260826-r1
ack_expected="RUN $campaign"
manifest="$repo/experiments/qwen38-27b-b70/data/2026-08-26-qwen38-official-f01e-autoround-tp4-mtp0-f16-eager-depth-expansion-r1-prereg.json"
note="$repo/experiments/qwen38-27b-b70/notes/2026-08-26-qwen38-official-f01e-autoround-tp4-mtp0-f16-eager-depth-expansion-r1-preregistration.md"
self=$(realpath -- "${BASH_SOURCE[0]}")
test_file="$repo/experiments/qwen38-27b-b70/scripts/test_qwen38_official_f01e_autoround_tp4_mtp0_f16_eager_depth_expansion_r1.py"
proven_tp_cache_launcher="$repo/experiments/qwen38-27b-b70/scripts/run-20260823-qwen38-rolling-nightly-strict-smoke.sh"
protected_manifest="$repo/experiments/qwen38-27b-b70/data/2026-08-23-qwen38-current-main-overlay-manifest.json"
model=/mnt/usb-models/llm-models/qwen3.8-27b-int4-autoround-devan
model_manifest="$repo/repro/qwen38-27b-autoround-int4-b70/manifests/model.json"
model_verifier="$repo/repro/qwen38-27b-autoround-int4-b70/scripts/verify-model-direct.py"
fixture="$repo/data/qwen27-exact-depth/qwen38-bce40ca-exact-depth-v1.json"
depth_helper="$repo/scripts/bench-openai-token-depth-suite.py"
quality_helper="$repo/scripts/qwen38-text-quality-suite.py"
quality_baseline=/mnt/usb-models/bench-results/qwen38-27b-autoround-int4-b70/nightly-strict-20260823/tp1-mtp0-f16-graph-seed0-natural-eos-replay-a-baseline-quality/quality.json
tp1_target_root=/mnt/fast-ai/bench-results/qwen38-official-f01e-autoround-tp1-f16-graphmodes-depth-20260826-r3/eager-f16/exact-depth
tp1_target_terminal=/mnt/fast-ai/bench-results/qwen38-official-f01e-autoround-tp1-f16-graphmodes-depth-20260826-r3/terminal-receipt.json
parent_root=/mnt/fast-ai/bench-results/qwen38-official-f01e-autoround-tp4-mtp0-f16-eager-8k-oracle-sentinel-20260826-r1
parent_8k="$parent_root/exact-depth/depth-8192.json"
parent_terminal="$parent_root/terminal-receipt.json"
parent_quality="$parent_root/quality.json"
model_config="$model/config.json"
model_index="$model/model.safetensors.index.json"
quant_config="$model/quantization_config.json"
venv_python=/home/steve/.venvs/vllm-xpu/bin/python
image_ref=vllm/vllm-openai-xpu@sha256:f01e24f6c7ff01f1e0662234255a1372297d1dbd89d003cf13c8fad3eab1ba4f
image_id=sha256:f01e24f6c7ff01f1e0662234255a1372297d1dbd89d003cf13c8fad3eab1ba4f
vllm_head=ac7509e2b1db40fec2f03dde1ed4e9dfdc2338c9
root=/mnt/fast-ai/bench-results/$campaign
cache_root=/home/steve/qwen38-current-main-runs/cache-official-f01e-autoround-tp4-mtp0-f16-eager-depth-expansion-20260826-r1
port=19486
name=q38-f01e-ar-tp4-mtp0-f16-depth-r1
served_model=qwen38-official-f01e-autoround-tp4-mtp0
sudo_pass_file=${SUDO_PASS_FILE:-/home/steve/SUDOPASSWORD.txt}
depths=(2048 4096 8192 16384 24576 32768)

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
  sha_is "$quality_baseline" 738b8ed03746ed976c157bf9c392a2637de7c477b719c55f2d533b398adbef18
  sha_is "$proven_tp_cache_launcher" cb2bfd95e7ad9956dae5bc22ccfa575c8742847c963143291a21505533598202
  sha_is "$tp1_target_root/depth-2048.json" b130cd570fdf72303c79b30c79704956adc73d1507e9909e5f6bf34a0ee20d5e
  sha_is "$tp1_target_root/depth-4096.json" c9dbfb8b9cf8ef23bea5ebe2cb3199c82d678988106e2f619221236e4726dd9e
  sha_is "$tp1_target_root/depth-8192.json" 94f7d11862b2e35b057e7a95b3d529b89a4c2857d8886ce93e4b4d85b7385c34
  sha_is "$tp1_target_root/depth-16384.json" 69cab2ec785de5615c4a47ca666c68d579dc5d9a163a50c87461e35217d0a847
  sha_is "$tp1_target_root/depth-24576.json" 4902ceb508b2828f405f62e7c3b76c323074b03b904d67be2dfce64b159e23c4
  sha_is "$tp1_target_root/depth-32768.json" 668b1ae15d8497c7230565a6937514585e6dddcc56e685e1f0e146c902464598
  sha_is "$tp1_target_terminal" 6cb6b3c8ae06eefe0c516c0dac057c20ca7837e6bae3b96e012a250f41dafa02
  sha_is "$parent_8k" 49ea5caae577dae86bb52378e84a6ad45da051ae403904158751903393121d9e
  sha_is "$parent_terminal" 779c64418c9cec0654f5107bfc83ccb5263f88d12b9481dd87a5ec301d170a16
  sha_is "$parent_quality" 2019240440a9ec03bf7904317b4d14a8499631b91183fd06430eedb3eb19d5ca
  sha_is "$model_config" 9a1c29a807e34529bec03cba92b4dc00ba61e37a703b029b08a3142b6dc08cd1
  sha_is "$model_index" adf387dee183d109e95cdc4d4988fcd966de326861ff4d66876692170f1e03ad
  sha_is "$quant_config" 0d1be50a7ad0a3c7350b4b4a4c8c1d26412d2cb2f1503e3ea21b40f1b8470c14
  jq -e '.status == "passed" and .gate.passed == true and .run_identity.depth == 8192 and
    .response.output_token_ids_sha256 == "34e792ccf3c1d795b686750f27990de2ca605c22046c97b3fff8ad0a7fc82e53"' \
    "$parent_8k" >/dev/null || die "frozen TP4 parent 8K oracle failed"
  jq -e '.terminal == true and (.state|startswith("passed-quality-clean-tp4-oracle"))' \
    "$parent_terminal" >/dev/null || die "frozen TP4 parent terminal receipt failed"
  jq -e --arg id "$campaign" --arg image "$image_ref" --arg root "$root" --argjson port "$port" '
    .schema == "neural.download.qwen38-official-autoround-tp4-mtp0-f16-eager-depth-expansion-prereg.v1" and
    .campaign_id == $id and .state == "preregistered-not-launched" and
    .run_identity.image == $image and .run_identity.tensor_parallel == 4 and
    .run_identity.mtp_depth == 0 and .run_identity.kv_cache_dtype == "float16" and
    .run_identity.gpu_affinity == "0,1,2,3" and
    .run_identity.gpu_memory_utilization == 0.6 and
    .run_identity.graph_mode == "off" and .run_identity.max_model_len == 32896 and
    .exact_depth_contract.depths == [2048,4096,8192,16384,24576,32768] and
    .execution.output_root == $root and .execution.port == $port and
    .execution.one_server_lifetime == true and
    .interpretation.historical_replacement_allowed == false and
    .execution.port == 19486 and
    .interpretation.protected_decode_values_unchanged == [71.45427094575045,30.329809361830037,49.05894025767351,71.9001988117144] and
    .interpretation.existing_tp4_8k_replacement_allowed == false and
    .interpretation.cross_topology_mismatch_is_caveat_not_rejection == true
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

write_depth_verification() {
  local depth=$1 candidate="$root/exact-depth/depth-$1.json" target="$tp1_target_root/depth-$1.json"
  "$venv_python" - "$depth" "$candidate" "$target" "$parent_8k" "$root/verification/depth-$depth.json" <<'PY'
import hashlib, json, pathlib, sys
depth = int(sys.argv[1])
candidate_path, target_path, parent_path, out_path = map(pathlib.Path, sys.argv[2:])
def ids(path):
    try: return json.loads(path.read_text())["response"]["token_ids"]
    except (OSError, KeyError, TypeError, json.JSONDecodeError): return None
candidate_ids, target_ids = ids(candidate_path), ids(target_path)
parent_ids = ids(parent_path) if depth == 8192 else None
comparison_pass = isinstance(candidate_ids, list) and len(candidate_ids) == 128 and candidate_ids == target_ids
first_divergence = None
if isinstance(candidate_ids, list) and isinstance(target_ids, list):
    for i, (candidate, target) in enumerate(zip(candidate_ids, target_ids)):
        if candidate != target:
            first_divergence = {"zero_based": i, "one_based": i + 1, "candidate": candidate, "target": target}
            break
    if first_divergence is None and len(candidate_ids) != len(target_ids):
        first_divergence = {"zero_based": min(len(candidate_ids), len(target_ids)), "reason": "length-mismatch"}
value = {
    "depth": depth,
    "candidate_receipt": str(candidate_path),
    "candidate_ids_sha256": hashlib.sha256(json.dumps(candidate_ids, separators=(",", ":")).encode()).hexdigest() if isinstance(candidate_ids, list) else None,
    "cross_topology_comparison": {
        "passed": comparison_pass,
        "target_receipt": str(target_path),
        "target_ids_sha256": hashlib.sha256(json.dumps(target_ids, separators=(",", ":")).encode()).hexdigest() if isinstance(target_ids, list) else None,
        "first_divergence": first_divergence,
        "policy": "comparison caveat only; mismatch does not reject a TP4-native oracle",
    },
    "parent_8k_match": {
        "required": depth == 8192,
        "passed": (candidate_ids == parent_ids and isinstance(candidate_ids, list) and len(candidate_ids) == 128) if depth == 8192 else None,
        "parent_receipt": str(parent_path) if depth == 8192 else None,
    },
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
  local state=$1 reason=$2 passed_depths=$3 comparison_passes=$4 quality_rc=$5 startup_ok=$6 runner_rc=$7 cleanup_ok=$8 topology_ok=$9 parent_ok=${10} cache_ok=${11} objective_quality_ok=${12} baseline_ok=${13}
  "$venv_python" - "$root/arm-result.json" "$state" "$reason" "$passed_depths" "$comparison_passes" "$quality_rc" "$startup_ok" "$runner_rc" "$cleanup_ok" "$topology_ok" "$parent_ok" "$cache_ok" "$objective_quality_ok" "$baseline_ok" "$root" <<'PY'
import datetime as dt, json, pathlib, sys
path, state, reason, passed_depths, comparison_passes, quality_rc, startup_ok, runner_rc, cleanup_ok, topology_ok, parent_ok, cache_ok, objective_quality_ok, baseline_ok, root = sys.argv[1:]
oracle_states = {
    "passed-quality-clean-depth-expansion",
    "passed-quality-clean-depth-expansion-with-comparison-caveat",
}
native_oracle_states = oracle_states | {"partial-depth-expansion"}
depths = [2048, 4096, 8192, 16384, 24576, 32768]
receipts = []
for depth in depths:
    rc_path = pathlib.Path(root) / "exact-depth" / f"depth-{depth}.rc"
    verify_path = pathlib.Path(root) / "verification" / f"depth-{depth}.json"
    rc = int(rc_path.read_text().strip()) if rc_path.is_file() else 125
    verification = json.loads(verify_path.read_text()) if verify_path.is_file() else None
    receipts.append({"depth": depth, "return_code": rc, "exact_passed": rc == 0, "verification": verification})
native_global_pass = state in native_oracle_states and all(v == "1" for v in (startup_ok, cleanup_ok, topology_ok, parent_ok, cache_ok, objective_quality_ok))
frozen_depths = [item["depth"] for item in receipts if item["exact_passed"]] if native_global_pass else []
value = {
    "schema": "neural.download.qwen38-official-autoround-tp4-mtp0-f16-eager-depth-expansion-arm.v1",
    "created_at_utc": dt.datetime.now(dt.UTC).isoformat(),
    "state": state,
    "reason": reason,
    "depth_receipts": receipts,
    "passed_depth_count": int(passed_depths),
    "passed_cross_topology_comparison_count": int(comparison_passes),
    "quality_return_code": int(quality_rc),
    "startup_identity_passed": startup_ok == "1",
    "cleanup_passed": cleanup_ok == "1",
    "tp4_worker_topology_passed": topology_ok == "1",
    "parent_8k_match_passed": parent_ok == "1",
    "rank_cache_isolation_passed": cache_ok == "1",
    "objective_quality_passed": objective_quality_ok == "1",
    "tp1_baseline_comparison_passed": baseline_ok == "1",
    "runner_return_code": int(runner_rc),
    "historical_replacement_allowed": False,
    "frozen_same_topology_oracle_depths": frozen_depths,
    "failed_or_quarantined_depths": [item["depth"] for item in receipts if item["depth"] not in frozen_depths],
    "comparison_caveat": state == "passed-quality-clean-depth-expansion-with-comparison-caveat",
    "complete_descendant_expansion_authorized": state in oracle_states,
    "per_depth_descendant_oracle_authority": native_global_pass,
    "descendant_execution_authorized": False,
    "historical_or_protected_replacement_allowed": False,
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
    "schema": "neural.download.qwen38-official-autoround-tp4-mtp0-f16-eager-depth-expansion-terminal.v1",
    "campaign_id": campaign,
    "created_at_utc": dt.datetime.now(dt.UTC).isoformat(),
    "state": arm["state"],
    "terminal": True,
    "launch_git_head": launch_head,
    "runner_return_code": int(runner_rc),
    "arm": arm,
    "historical_replacement_allowed": False,
    "protected_profiles_untouched": True,
    "automatic_descendant_expansion": False,
}
(root / "terminal-receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
PY
}

run_expansion() {
  local startup_ok=0 passed_depths=0 comparison_passes=0 quality_rc=125 runner_rc=0 cleanup_ok=0 topology_ok=0 parent_ok=0 cache_ok=0 objective_quality_ok=0 baseline_ok=0 rank depth depth_rc
  local state=failed reason=unknown observed_image observed_head versions healthy=0 running i
  local -a args=(
    "$model" --host 0.0.0.0 --port 8000 --trust-remote-code
    --served-model-name "$served_model"
    --tensor-parallel-size 4 --pipeline-parallel-size 1 --data-parallel-size 1
    --max-model-len 32896 --max-num-seqs 1 --max-num-batched-tokens 1024
    --gpu-memory-utilization 0.60 --dtype float16
    --reasoning-parser qwen3 --default-chat-template-kwargs '{"enable_thinking": false}'
    --enable-prompt-tokens-details --no-enable-prefix-caching
    --enable-chunked-prefill --async-scheduling --enforce-eager
  )
  printf '%q ' "${args[@]}" > "$root/server-args.shell.txt"
  printf '\n' >> "$root/server-args.shell.txt"

  if ! dockerc run -d --name "$name" --device /dev/dri --group-add 44 --group-add 992 \
      --ipc=host --shm-size 16g -v /dev/dri/by-path:/dev/dri/by-path:ro \
      -v "$model:$model:ro" -v "$cache_root:/run-cache" -p "127.0.0.1:$port:8000" \
      -e ZE_AFFINITY_MASK=0,1,2,3 \
      -e VLLM_NO_USAGE_STATS=1 -e PYTHONHASHSEED=0 \
      -e VLLM_XPU_ENABLE_XPU_GRAPH=0 -e VLLM_XPU_GRAPH=0 \
      -e VLLM_CACHE_ROOT=/run-cache/vllm -e XDG_CACHE_HOME=/run-cache/xdg \
      -e CCL_ZE_IPC_EXCHANGE=sockets \
      "$image_ref" "${args[@]}" > "$root/container-id.txt"; then
    dockerc rm -f "$name" >/dev/null 2>&1 || true
    strict_postcleanup && cleanup_ok=1
    write_arm_result failed docker-run-failed 0 0 125 0 31 "$cleanup_ok" 0 0 0 0 0
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
    state=failed; reason=tp4-infrastructure-or-startup-failed; runner_rc=32
    strict_postcleanup && cleanup_ok=1
    write_arm_result "$state" "$reason" 0 0 125 0 "$runner_rc" "$cleanup_ok" 0 0 0 0 0
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
     grep -Fq 'speculative_config=SpeculativeConfig' "$root/server-startup.log" || \
     grep -Fq 'Graph capturing finished' "$root/server-startup.log" || \
     grep -Fq 'Compiling a graph for compile range' "$root/server-startup.log"; then
    cleanup_active
    strict_postcleanup && cleanup_ok=1
    write_arm_result failed startup-identity-or-mode-gate-failed 0 0 125 0 33 "$cleanup_ok" 0 0 0 0 0
    return 33
  fi
  startup_ok=1
  topology_ok=1
  for rank in 0 1 2 3; do
    grep -Eq "world_size=4 rank=$rank local_rank=$rank" "$root/server-startup.log" || topology_ok=0
  done
  grep -Fq 'world_size=4, local_world_size=4' "$root/server-startup.log" || topology_ok=0
  if (( topology_ok == 0 )); then
    cleanup_active; strict_postcleanup && cleanup_ok=1
    write_arm_result failed tp4-worker-topology-gate-failed 0 0 125 1 34 "$cleanup_ok" 0 0 0 0 0
    return 34
  fi
  if ! curl -fsS "http://127.0.0.1:$port/v1/models" > "$root/models.json"; then
    runner_rc=34
  fi

  mkdir "$root/exact-depth" "$root/verification"
  for depth in "${depths[@]}"; do
    "$venv_python" "$depth_helper" --execute --fixture "$fixture" --depth "$depth" \
      --case-id "depth-$depth" --context-capacity 32896 --response-adapter vllm \
      --base-url "http://127.0.0.1:$port" --model "$served_model" \
      --timeout 900 --out "$root/exact-depth/depth-$depth.json" \
      > "$root/exact-depth/depth-$depth.stdout.json" \
      2> "$root/exact-depth/depth-$depth.stderr.log"
    depth_rc=$?
    printf '%s\n' "$depth_rc" > "$root/exact-depth/depth-$depth.rc"
    (( depth_rc == 0 )) && passed_depths=$((passed_depths + 1))
    if write_depth_verification "$depth"; then
      jq -e '.cross_topology_comparison.passed == true' "$root/verification/depth-$depth.json" >/dev/null 2>&1 && comparison_passes=$((comparison_passes + 1))
      if (( depth == 8192 )) && jq -e '.parent_8k_match.passed == true' "$root/verification/depth-8192.json" >/dev/null; then parent_ok=1; fi
    else
      runner_rc=36
    fi
  done

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
    for rank in 0 1 2 3; do
      find "$cache_root/vllm/torch_compile_cache" -type f -path "*/rank_${rank}_0/*" -print -quit | grep -q . || cache_ok=0
    done
    find "$cache_root/vllm/torch_compile_cache" -type f | grep -Ev '/rank_[0-3]_0/' > "$root/shared-compile-artifacts.txt" || true
    [[ ! -s "$root/shared-compile-artifacts.txt" ]] || cache_ok=0
  fi

  if (( cleanup_ok == 0 )); then
    state=failed; reason=strict-postcleanup-failed; runner_rc=39
  elif (( runner_rc != 0 )); then
    state=failed; reason=models-or-verification-gate-failed
  elif (( cache_ok == 0 )); then
    state=failed; reason=rank-cache-isolation-gate-failed; runner_rc=38
  elif (( parent_ok == 0 )); then
    state=quarantined-parent-8k-mismatch; reason=frozen-tp4-parent-8k-mismatch; runner_rc=42
  elif (( passed_depths == 6 && objective_quality_ok == 1 && topology_ok == 1 && comparison_passes == 6 && baseline_ok == 1 )); then
    state=passed-quality-clean-depth-expansion; reason=all-six-tp4-depths-parent-quality-comparisons-and-cleanup-passed; runner_rc=0
  elif (( passed_depths == 6 && objective_quality_ok == 1 && topology_ok == 1 )); then
    state=passed-quality-clean-depth-expansion-with-comparison-caveat; reason=all-tp4-native-gates-passed-with-cross-topology-or-baseline-caveat; runner_rc=0
  elif (( passed_depths < 6 )); then
    state=partial-depth-expansion; reason=per-depth-evidence-retained-with-one-or-more-exact-depth-failures; runner_rc=37
  elif (( objective_quality_ok == 0 )); then
    state=quarantined-objective-quality-failed; reason=six-depths-passed-but-objective-quality-failed; runner_rc=40
  fi
  write_arm_result "$state" "$reason" "$passed_depths" "$comparison_passes" "$quality_rc" "$startup_ok" "$runner_rc" "$cleanup_ok" "$topology_ok" "$parent_ok" "$cache_ok" "$objective_quality_ok" "$baseline_ok"
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
    jq '{campaign_id,state,prior_evidence,reopen_basis,run_identity,exact_depth_contract,quality_contract,execution,terminal_classification,interpretation}' "$manifest"
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
      "$quality_helper" "$quality_baseline" \
      "$tp1_target_root/depth-2048.json" "$tp1_target_root/depth-4096.json" \
      "$tp1_target_root/depth-8192.json" "$tp1_target_root/depth-16384.json" \
      "$tp1_target_root/depth-24576.json" "$tp1_target_root/depth-32768.json" \
      "$tp1_target_terminal" \
      "$parent_8k" "$parent_terminal" "$parent_quality" "$model_config" \
      "$model_index" "$quant_config" > "$root/input-sha256sums.txt"
    if ! "$model_verifier" "$model_manifest" "$model" --json "$root/model-verification.json" \
        > "$root/model-verification.log" 2>&1; then
      cleanup_ok=0
      strict_postcleanup && cleanup_ok=1
      write_arm_result failed model-verification-failed 0 0 125 0 41 "$cleanup_ok" 0 0 0 0 0
      terminal_receipt "$launch_head" 41
      exit 41
    fi
    run_expansion
    runner_rc=$?
    terminal_receipt "$launch_head" "$runner_rc"
    printf '{"campaign_id":"%s","terminal_receipt":"%s/terminal-receipt.json"}\n' "$campaign" "$root"
    exit "$runner_rc"
    ;;
esac
