#!/usr/bin/env bash
set -uo pipefail

repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)
campaign=qwen38-official-f01e-autoround-tp2-mtp0-f16-piecewise-depth-20260826-r1
ack_expected="RUN $campaign"
manifest="$repo/experiments/qwen38-27b-b70/data/2026-08-26-qwen38-official-f01e-autoround-tp2-mtp0-f16-piecewise-depth-r1-prereg.json"
note="$repo/experiments/qwen38-27b-b70/notes/2026-08-26-qwen38-official-f01e-autoround-tp2-mtp0-f16-piecewise-depth-r1-preregistration.md"
self=$(realpath -- "${BASH_SOURCE[0]}")
test_file="$repo/experiments/qwen38-27b-b70/scripts/test_qwen38_official_f01e_autoround_tp2_mtp0_f16_piecewise_depth_r1.py"
protected_manifest="$repo/experiments/qwen38-27b-b70/data/2026-08-23-qwen38-current-main-overlay-manifest.json"
eager_result="$repo/experiments/qwen38-27b-b70/data/2026-08-26-qwen38-official-f01e-autoround-tp2-mtp0-f16-eager-depth-expansion-r1-result.json"
dated_graph_result="$repo/experiments/qwen38-27b-b70/data/2026-08-26-qwen38-b2dd9ce73d-tp2-exact-depth-quality-r1-result.json"
eager_root=/mnt/fast-ai/bench-results/qwen38-official-f01e-autoround-tp2-mtp0-f16-eager-depth-expansion-20260826-r1
eager_target_root="$eager_root/exact-depth"
eager_terminal="$eager_root/terminal-receipt.json"
eager_arm="$eager_root/arm-result.json"
quality_baseline="$eager_root/quality.json"
dated_graph_root=/home/steve/qwen38-current-main-runs/tp2-exact-depth-b2dd9ce73d-20260826-r1/01-exact-depths/exact-depth
model=/mnt/usb-models/llm-models/qwen3.8-27b-int4-autoround-devan
model_manifest="$repo/repro/qwen38-27b-autoround-int4-b70/manifests/model.json"
model_verifier="$repo/repro/qwen38-27b-autoround-int4-b70/scripts/verify-model-direct.py"
fixture="$repo/data/qwen27-exact-depth/qwen38-bce40ca-exact-depth-v1.json"
depth_helper="$repo/scripts/bench-openai-token-depth-suite.py"
quality_helper="$repo/scripts/qwen38-text-quality-suite.py"
model_config="$model/config.json"
model_index="$model/model.safetensors.index.json"
quant_config="$model/quantization_config.json"
venv_python=/home/steve/.venvs/vllm-xpu/bin/python
image_ref=vllm/vllm-openai-xpu@sha256:f01e24f6c7ff01f1e0662234255a1372297d1dbd89d003cf13c8fad3eab1ba4f
image_id=sha256:f01e24f6c7ff01f1e0662234255a1372297d1dbd89d003cf13c8fad3eab1ba4f
vllm_head=ac7509e2b1db40fec2f03dde1ed4e9dfdc2338c9
root=/mnt/fast-ai/bench-results/$campaign
cache_root=/home/steve/qwen38-current-main-runs/cache-official-f01e-autoround-tp2-mtp0-f16-piecewise-depth-20260826-r1
port=19496
name=q38-f01e-ar-tp2-mtp0-f16-pwdepth-r1
served_model=qwen38-official-f01e-autoround-tp2-mtp0-piecewise
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
  sha_is "$eager_result" c4423e5231ac112152a0bdc02419b805cc9422aa1f3d572e8c2c01f9b64baaa7
  sha_is "$dated_graph_result" 3b31ec401e37f713054fa37a201acb9ebc209664d1d9415006268a1368aef167
  sha_is "$eager_terminal" 63fe2e8a85db47af331743b93b1c6e181f930775104f19483eb7b9e1da0f2c60
  sha_is "$eager_arm" b6d66ec05417fc29b933277d3b7948616b6b39633439571b37e8b2a63a10838b
  sha_is "$quality_baseline" ef15f39a848d262a4582b1ab6c9a2f10713ecfbcae02497bc4462c8ae5a3af96
  sha_is "$eager_target_root/depth-2048.json" 57b1ad5760ab790c3b839a897bc6b1807a2d1037710b0e949e2977973cc5864e
  sha_is "$eager_target_root/depth-4096.json" 6e32b0a05f7e355bf21c5e3ebd0e04a16fbf3d54bc39890aa8740b3a5430f187
  sha_is "$eager_target_root/depth-8192.json" 55bc2ad94cb920dda1233f3d26209d009a80549469974182c0455d2826f11266
  sha_is "$eager_target_root/depth-16384.json" c93e67650b0bf61941f33280dd66a2de82b555c4d65b0a0ddc1093defb03d569
  sha_is "$eager_target_root/depth-24576.json" eaef51ab0c3ad12501d1f9b087233359b3a6455cce25bb68161828cd61600fa0
  sha_is "$eager_target_root/depth-32768.json" cf37631f2d2d32fb0dfbc7ab1674b9cccdf67270791fc728112dbd2a458edc9b
  sha_is "$dated_graph_root/depth-2048.json" 1ede0356f6fd1ab6a168a430ff36819dabaa9ce3fe2dfaea1aa2d303aa55db7b
  sha_is "$dated_graph_root/depth-4096.json" 0e6bcf6bfee49c0634cc3b21ae1de182c34a4644221379e9a48bd8fd9de291c8
  sha_is "$dated_graph_root/depth-8192.json" b68b8cabc28333ed14a9355a05ddd7d3219e2a4649a96402680703a160187bec
  sha_is "$dated_graph_root/depth-16384.json" 0055a12364b8e40c948ed2e415282e1e0f6f1926a23e4cafcfe55a7da4b48fce
  sha_is "$dated_graph_root/depth-24576.json" 542b84249e51da07af661bc1b4442a7c456fe689180d532fa0f79b6a13b522a2
  sha_is "$dated_graph_root/depth-32768.json" 3dde8f193aa95da9790b61300b7b4e5d4c13cf935931e4e7e7f57df6a7484927
  sha_is "$model_config" 9a1c29a807e34529bec03cba92b4dc00ba61e37a703b029b08a3142b6dc08cd1
  sha_is "$model_index" adf387dee183d109e95cdc4d4988fcd966de326861ff4d66876692170f1e03ad
  sha_is "$quant_config" 0d1be50a7ad0a3c7350b4b4a4c8c1d26412d2cb2f1503e3ea21b40f1b8470c14
  jq -e '
    .state == "passed-quality-clean-depth-expansion" and .terminal == true and
    .arm.state == "passed-quality-clean-depth-expansion" and
    .arm.passed_depth_count == 6 and .arm.objective_quality_passed == true and
    .arm.tp2_worker_topology_passed == true and .arm.rank_cache_isolation_passed == true and
    .arm.cleanup_passed == true and
    .arm.frozen_same_topology_oracle_depths == [2048,4096,8192,16384,24576,32768]
  ' "$eager_terminal" >/dev/null || die "current-f01e eager parent receipt failed"
  jq -e '
    .pass_all == true and .baseline_match_all == true and
    (.exact_cases | length) == 7 and (.repeat_case.runs | length) == 8 and
    ([.exact_cases[].usage,.repeat_case.runs[].usage,.long_context_case.usage] |
      length == 16 and all(.[]; .prompt_tokens_details.cached_tokens == 0))
  ' "$quality_baseline" >/dev/null || die "current-f01e eager quality oracle failed"
  jq -e --arg id "$campaign" --arg image "$image_ref" --arg root "$root" --argjson port "$port" '
    .schema == "neural.download.qwen38-official-autoround-tp2-mtp0-f16-piecewise-depth-prereg.v1" and
    .campaign_id == $id and .state == "preregistered-not-launched" and
    .run_identity.image == $image and .run_identity.tensor_parallel == 2 and
    .run_identity.mtp_depth == 0 and .run_identity.speculative_config == null and
    .run_identity.kv_cache_dtype == "float16" and .run_identity.graph_mode == "PIECEWISE" and
    .run_identity.graph_capture_sizes == [1] and .run_identity.gpu_affinity == "0,1" and
    .run_identity.gpu_memory_utilization == 0.6 and .run_identity.max_model_len == 32896 and
    .exact_depth_contract.depths == [2048,4096,8192,16384,24576,32768] and
    .execution.output_root == $root and .execution.port == $port and .execution.port == 19496 and
    .execution.one_server_lifetime == true and .execution.default_is_inert == true and
    .parent_oracles.same_image_same_topology_eager.terminal_state == "passed-quality-clean-depth-expansion" and
    .interpretation.protected_decode_values_unchanged == [71.45427094575045,30.329809361830037,49.05894025767351,71.9001988117144] and
    .interpretation.historical_replacement_allowed == false and
    .interpretation.automatic_publication_allowed == false and
    .interpretation.descendant_execution_authorized == false
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

quality_objective_gate() {
  jq -e '
    . as $q |
    ($q.pass_all == true) and
    (($q.exact_cases | type) == "array" and ($q.exact_cases | length) == 7) and
    (($q.repeat_case.runs | type) == "array" and ($q.repeat_case.runs | length) == 8) and
    (($q.repeat_case.unique_hashes | length) == 1) and
    (($q.long_context_case.usage | type) == "object") and
    ([
      $q.exact_cases[].usage,
      $q.repeat_case.runs[].usage,
      $q.long_context_case.usage
    ] | length == 16 and all(.[]; (.prompt_tokens_details.cached_tokens? == 0)))
  ' "$1"
}

write_depth_verification() {
  local depth=$1 candidate="$root/exact-depth/depth-$1.json" eager="$eager_target_root/depth-$1.json" dated="$dated_graph_root/depth-$1.json"
  "$venv_python" - "$depth" "$candidate" "$eager" "$dated" "$root/verification/depth-$depth.json" <<'PY'
import hashlib, json, pathlib, sys
depth = int(sys.argv[1])
candidate_path, eager_path, dated_path, out_path = map(pathlib.Path, sys.argv[2:])
def ids(path):
    try:
        value = json.loads(path.read_text())["response"]["token_ids"]
        return value if isinstance(value, list) else None
    except (OSError, KeyError, TypeError, json.JSONDecodeError):
        return None
def digest(value):
    return hashlib.sha256(json.dumps(value, separators=(",", ":")).encode()).hexdigest() if isinstance(value, list) else None
def compare(candidate, target):
    passed = isinstance(candidate, list) and len(candidate) == 128 and candidate == target
    divergence = None
    if isinstance(candidate, list) and isinstance(target, list):
        for index, (left, right) in enumerate(zip(candidate, target)):
            if left != right:
                divergence = {"zero_based": index, "one_based": index + 1, "candidate": left, "target": right}
                break
        if divergence is None and len(candidate) != len(target):
            divergence = {"zero_based": min(len(candidate), len(target)), "reason": "length-mismatch"}
    return passed, divergence
candidate_ids, eager_ids, dated_ids = ids(candidate_path), ids(eager_path), ids(dated_path)
eager_passed, eager_divergence = compare(candidate_ids, eager_ids)
dated_passed, dated_divergence = compare(candidate_ids, dated_ids)
value = {
    "depth": depth,
    "candidate_receipt": str(candidate_path),
    "candidate_ids_sha256": digest(candidate_ids),
    "same_image_target_comparison": {
        "passed": eager_passed,
        "target_receipt": str(eager_path),
        "target_ids_sha256": digest(eager_ids),
        "first_divergence": eager_divergence,
        "policy": "required for a valid current-f01e graph cell",
    },
    "dated_graph_comparison": {
        "passed": dated_passed,
        "target_receipt": str(dated_path),
        "target_ids_sha256": digest(dated_ids),
        "first_divergence": dated_divergence,
        "policy": "cross-runtime comparison caveat only; never a validity or speed gate",
    },
}
out_path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
PY
}

write_cache_isolation() {
  "$venv_python" - "$cache_root" "$root/rank-cache-isolation.json" <<'PY'
import hashlib, json, pathlib, re, sys
root, out = map(pathlib.Path, sys.argv[1:])
files = sorted(path for path in root.rglob("*") if path.is_file())
rank_pattern = re.compile(r"^rank_[0-9]+_[0-9]+$")
rank_files, shared_files = {}, []
for path in files:
    rel = path.relative_to(root)
    ranks = [part for part in rel.parts if rank_pattern.match(part)]
    if ranks:
        rank_files.setdefault(ranks[0], []).append(str(rel))
    else:
        shared_files.append(str(rel))
expected = ["rank_0_0", "rank_1_0"]
observed = sorted(rank_files)
value = {
    "schema": "neural.download.tp-rank-cache-isolation.v1",
    "cache_root": str(root),
    "total_files": len(files),
    "expected_rank_namespaces": expected,
    "observed_rank_namespaces": observed,
    "rank_file_counts": {rank: len(rank_files.get(rank, [])) for rank in expected},
    "shared_file_count": len(shared_files),
    "shared_files_sha256": hashlib.sha256("\n".join(shared_files).encode()).hexdigest(),
    "passed": observed == expected and all(rank_files.get(rank) for rank in expected),
    "policy": "Only rank_0_0 and rank_1_0 rank namespaces are allowed; shared AOT/cache support files are inventoried separately.",
}
out.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
raise SystemExit(0 if value["passed"] else 1)
PY
}

write_arm_result() {
  local output=$1 state=$2 reason=$3 exact_passes=$4 target_passes=$5 dated_passes=$6 quality_rc=$7 startup_ok=$8 runner_rc=$9 cleanup_ok=${10} topology_ok=${11} cache_ok=${12} objective_ok=${13} baseline_ok=${14} run_root=${15}
  "$venv_python" - "$output" "$state" "$reason" "$exact_passes" "$target_passes" "$dated_passes" "$quality_rc" "$startup_ok" "$runner_rc" "$cleanup_ok" "$topology_ok" "$cache_ok" "$objective_ok" "$baseline_ok" "$run_root" <<'PY'
import datetime as dt, json, pathlib, sys
path, state, reason, exact_passes, target_passes, dated_passes, quality_rc, startup_ok, runner_rc, cleanup_ok, topology_ok, cache_ok, objective_ok, baseline_ok, root = sys.argv[1:]
root = pathlib.Path(root)
depths = [2048, 4096, 8192, 16384, 24576, 32768]
receipts = []
for depth in depths:
    rc_path = root / "exact-depth" / f"depth-{depth}.rc"
    verify_path = root / "verification" / f"depth-{depth}.json"
    rc = int(rc_path.read_text().strip()) if rc_path.is_file() else 125
    verification = json.loads(verify_path.read_text()) if verify_path.is_file() else None
    target_ok = bool(verification and verification.get("same_image_target_comparison", {}).get("passed"))
    receipts.append({"depth": depth, "return_code": rc, "exact_passed": rc == 0, "same_image_target_passed": target_ok, "verification": verification})
global_ok = state in {"passed-quality-clean-piecewise-depth", "partial-depth-expansion"} and all(value == "1" for value in (startup_ok, cleanup_ok, topology_ok, cache_ok, objective_ok, baseline_ok))
valid_depths = [item["depth"] for item in receipts if global_ok and item["exact_passed"] and item["same_image_target_passed"]]
value = {
    "schema": "neural.download.qwen38-official-autoround-tp2-mtp0-f16-piecewise-depth-arm.v1",
    "created_at_utc": dt.datetime.now(dt.UTC).isoformat(),
    "state": state,
    "reason": reason,
    "depth_receipts": receipts,
    "exact_passed_count": int(exact_passes),
    "same_image_target_passed_count": int(target_passes),
    "dated_graph_comparison_passed_count": int(dated_passes),
    "quality_return_code": int(quality_rc),
    "startup_graph_identity_passed": startup_ok == "1",
    "cleanup_passed": cleanup_ok == "1",
    "tp2_worker_topology_passed": topology_ok == "1",
    "rank_cache_isolation_passed": cache_ok == "1",
    "objective_quality_passed": objective_ok == "1",
    "same_topology_baseline_passed": baseline_ok == "1",
    "runner_return_code": int(runner_rc),
    "valid_depths": valid_depths,
    "invalid_or_quarantined_depths": [depth for depth in depths if depth not in valid_depths],
    "automatic_publication_allowed": False,
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
    "schema": "neural.download.qwen38-official-autoround-tp2-mtp0-f16-piecewise-depth-terminal.v1",
    "campaign_id": campaign,
    "created_at_utc": dt.datetime.now(dt.UTC).isoformat(),
    "state": arm["state"],
    "terminal": True,
    "launch_git_head": launch_head,
    "runner_return_code": int(runner_rc),
    "arm": arm,
    "historical_replacement_allowed": False,
    "automatic_publication_allowed": False,
    "automatic_descendant_execution": False,
}
(root / "terminal-receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
PY
}

run_piecewise() {
  local startup_ok=0 exact_passes=0 target_passes=0 dated_passes=0 quality_rc=125 runner_rc=0 cleanup_ok=0 topology_ok=0 cache_ok=0 objective_ok=0 baseline_ok=0
  local state=failed reason=unknown observed_image observed_head versions healthy=0 running i depth depth_rc
  local -a args=(
    "$model" --host 0.0.0.0 --port 8000 --trust-remote-code
    --served-model-name "$served_model"
    --tensor-parallel-size 2 --pipeline-parallel-size 1 --data-parallel-size 1
    --max-model-len 32896 --max-num-seqs 1 --max-num-batched-tokens 1024
    --gpu-memory-utilization 0.60 --dtype float16
    --reasoning-parser qwen3 --default-chat-template-kwargs '{"enable_thinking": false}'
    --enable-prompt-tokens-details --no-enable-prefix-caching
    --enable-chunked-prefill --async-scheduling
    --compilation-config '{"cudagraph_mode":"PIECEWISE","cudagraph_capture_sizes":[1],"max_cudagraph_capture_size":1}'
  )
  printf '%q ' "${args[@]}" > "$root/server-args.shell.txt"
  printf '\n' >> "$root/server-args.shell.txt"

  if ! dockerc run -d --name "$name" --device /dev/dri --group-add 44 --group-add 992 \
      --ipc=host --shm-size 16g -v /dev/dri/by-path:/dev/dri/by-path:ro \
      -v "$model:$model:ro" -v "$cache_root:/run-cache" -p "127.0.0.1:$port:8000" \
      -e ZE_AFFINITY_MASK=0,1 \
      -e VLLM_NO_USAGE_STATS=1 -e PYTHONHASHSEED=0 \
      -e VLLM_XPU_ENABLE_XPU_GRAPH=1 \
      -e VLLM_CACHE_ROOT=/run-cache/vllm -e XDG_CACHE_HOME=/run-cache/xdg \
      -e CCL_ZE_IPC_EXCHANGE=sockets \
      "$image_ref" "${args[@]}" > "$root/container-id.txt"; then
    dockerc rm -f "$name" >/dev/null 2>&1 || true
    strict_postcleanup && cleanup_ok=1
    write_arm_result "$root/arm-result.json" failed docker-run-failed 0 0 0 125 0 31 "$cleanup_ok" 0 0 0 0 "$root"
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
  if (( healthy == 0 )); then
    cleanup_active
    strict_postcleanup && cleanup_ok=1
    write_arm_result "$root/arm-result.json" failed tp2-piecewise-startup-failed 0 0 0 125 0 32 "$cleanup_ok" 0 0 0 0 "$root"
    return 32
  fi

  observed_head=$(dockerc exec "$name" git -C /workspace/vllm rev-parse HEAD 2>/dev/null || true)
  versions=$(dockerc exec "$name" python3 -c 'import importlib.metadata as m; print(m.version("vllm")); print(m.version("vllm-xpu-kernels"))' 2>/dev/null || true)
  printf '%s\n' "$observed_head" > "$root/vllm-source-commit.txt"
  printf '%s\n' "$versions" > "$root/stack-versions.txt"
  if [[ "$observed_image" != "$image_id" || "$observed_head" != "$vllm_head" ]] || \
     ! grep -Fxq '0.27.2rc1.dev77+gac7509e2b.xpu' "$root/stack-versions.txt" || \
     ! grep -Fxq '0.1.12.3' "$root/stack-versions.txt" || \
     ! grep -Fq 'quantization=inc' "$root/server-startup.log" || \
     ! grep -Fq 'enforce_eager=False' "$root/server-startup.log" || \
     ! grep -Fq 'kv_cache_dtype=auto' "$root/server-startup.log" || \
     ! grep -Fq 'Capturing CUDA graphs (mixed prefill-decode, PIECEWISE)' "$root/server-startup.log" || \
     ! grep -Fq 'Graph capturing finished' "$root/server-startup.log" || \
     ! grep -Fq 'Compiling a graph for compile range' "$root/server-startup.log" || \
     grep -Fq 'Capturing CUDA graphs (decode, FULL)' "$root/server-startup.log" || \
     grep -Fq 'enforce_eager=True' "$root/server-startup.log" || \
     grep -Fq 'speculative_config=SpeculativeConfig' "$root/server-startup.log"; then
    cleanup_active
    strict_postcleanup && cleanup_ok=1
    write_arm_result "$root/arm-result.json" failed startup-identity-or-piecewise-gate-failed 0 0 0 125 0 33 "$cleanup_ok" 0 0 0 0 "$root"
    return 33
  fi
  startup_ok=1
  topology_ok=1
  for rank in 0 1; do
    grep -Eq "world_size=2 rank=$rank local_rank=$rank" "$root/server-startup.log" || topology_ok=0
  done
  grep -Fq 'world_size=2, local_world_size=2' "$root/server-startup.log" || topology_ok=0
  if (( topology_ok == 0 )); then
    cleanup_active
    strict_postcleanup && cleanup_ok=1
    write_arm_result "$root/arm-result.json" failed tp2-worker-topology-gate-failed 0 0 0 125 1 34 "$cleanup_ok" 0 0 0 0 "$root"
    return 34
  fi
  if ! curl -fsS "http://127.0.0.1:$port/v1/models" > "$root/models.json"; then
    runner_rc=35
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
    (( depth_rc == 0 )) && exact_passes=$((exact_passes + 1))
    if write_depth_verification "$depth"; then
      jq -e '.same_image_target_comparison.passed == true' "$root/verification/depth-$depth.json" >/dev/null 2>&1 && target_passes=$((target_passes + 1))
      jq -e '.dated_graph_comparison.passed == true' "$root/verification/depth-$depth.json" >/dev/null 2>&1 && dated_passes=$((dated_passes + 1))
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
  quality_objective_gate "$root/quality.json" >/dev/null 2>&1 && objective_ok=1
  jq -e '.baseline_match_all == true and (.baseline_comparisons | length) == 24' "$root/quality.json" >/dev/null 2>&1 && baseline_ok=1
  cleanup_active
  strict_postcleanup && cleanup_ok=1
  write_cache_isolation && cache_ok=1

  if (( cleanup_ok == 0 )); then
    state=failed; reason=strict-postcleanup-failed; runner_rc=39
  elif (( cache_ok == 0 )); then
    state=failed; reason=rank-cache-isolation-gate-failed; runner_rc=38
  elif (( runner_rc != 0 )); then
    state=failed; reason=models-or-verification-gate-failed
  elif (( objective_ok == 0 || baseline_ok == 0 )); then
    state=quarantined-target-or-quality-failed; reason=objective-or-same-topology-quality-gate-failed; runner_rc=40
  elif (( exact_passes == 6 && target_passes == 6 )); then
    state=passed-quality-clean-piecewise-depth; reason=all-six-depth-target-quality-graph-topology-cache-and-cleanup-gates-passed; runner_rc=0
  elif (( target_passes > 0 )); then
    state=partial-depth-expansion; reason=valid-depths-retained-with-one-or-more-exact-or-target-parity-failures; runner_rc=37
  else
    state=quarantined-target-or-quality-failed; reason=no-same-image-target-parity-depth-passed; runner_rc=40
  fi
  write_arm_result "$root/arm-result.json" "$state" "$reason" "$exact_passes" "$target_passes" "$dated_passes" "$quality_rc" "$startup_ok" "$runner_rc" "$cleanup_ok" "$topology_ok" "$cache_ok" "$objective_ok" "$baseline_ok" "$root"
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
    jq '{campaign_id,state,parent_oracles,run_identity,exact_depth_contract,quality_contract,graph_contract,execution,terminal_classification,interpretation}' "$manifest"
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
      "$eager_result" "$dated_graph_result" "$eager_terminal" "$eager_arm" \
      "$quality_baseline" "$fixture" "$model_manifest" "$model_verifier" \
      "$depth_helper" "$quality_helper" "$model_config" "$model_index" \
      "$quant_config" > "$root/input-sha256sums.txt"
    if ! "$model_verifier" "$model_manifest" "$model" --json "$root/model-verification.json" \
        > "$root/model-verification.log" 2>&1; then
      cleanup_ok=0
      strict_postcleanup && cleanup_ok=1
      write_arm_result "$root/arm-result.json" failed model-verification-failed 0 0 0 125 0 41 "$cleanup_ok" 0 0 0 0 "$root"
      terminal_receipt "$launch_head" 41
      exit 41
    fi
    run_piecewise
    runner_rc=$?
    terminal_receipt "$launch_head" "$runner_rc"
    printf '{"campaign_id":"%s","terminal_receipt":"%s/terminal-receipt.json"}\n' "$campaign" "$root"
    exit "$runner_rc"
    ;;
esac
