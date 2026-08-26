#!/usr/bin/env bash
set -uo pipefail

repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)
campaign=qwen38-official-f01e-autoround-tp1-mtp2-f16-piecewise-4k-sentinel-20260826-r1
ack_expected="RUN $campaign"
lane="$repo/experiments/qwen38-27b-b70"
manifest="$lane/data/2026-08-26-qwen38-official-f01e-autoround-tp1-mtp2-f16-piecewise-4k-sentinel-r1-prereg.json"
note="$lane/notes/2026-08-26-qwen38-official-f01e-autoround-tp1-mtp2-f16-piecewise-4k-sentinel-r1-preregistration.md"
self=$(realpath -- "${BASH_SOURCE[0]}")
test_file="$lane/scripts/test_qwen38_official_f01e_autoround_tp1_mtp2_f16_piecewise_4k_sentinel_r1.py"
adjudication="$lane/data/2026-08-26-qwen38-official-f01e-autoround-tp1-mtp0-f16-piecewise-depth-r3-human-adjudication-result.json"
protected_manifest="$lane/data/2026-08-23-qwen38-current-main-overlay-manifest.json"
model=/mnt/usb-models/llm-models/qwen3.8-27b-int4-autoround-devan
model_manifest="$repo/repro/qwen38-27b-autoround-int4-b70/manifests/model.json"
model_verifier="$repo/repro/qwen38-27b-autoround-int4-b70/scripts/verify-model-direct.py"
fixture="$repo/data/qwen27-exact-depth/qwen38-bce40ca-exact-depth-v1.json"
depth_helper="$repo/scripts/bench-openai-token-depth-suite.py"
quality_helper="$repo/scripts/qwen38-text-quality-suite.py"
raw_parent=/mnt/fast-ai/bench-results/qwen38-official-f01e-autoround-tp1-f16-graphmodes-depth-20260826-r3
eager_parent="$raw_parent/eager-f16/exact-depth/depth-4096.json"
graph_parent="$raw_parent/piecewise-f16/exact-depth/depth-4096.json"
quality_baseline="$raw_parent/piecewise-f16/quality.json"
parent_terminal="$raw_parent/terminal-receipt.json"
mechanism_result="$lane/data/2026-08-26-qwen38-official-f01e-autoround-tp1-mtp2-f16-eager-depth-expansion-r1-result.json"
mechanism_root=/mnt/fast-ai/bench-results/qwen38-official-f01e-autoround-tp1-mtp2-f16-eager-depth-expansion-20260826-r1
mechanism_exact="$mechanism_root/exact-depth/depth-4096.json"
mechanism_verification="$mechanism_root/verification/depth-4096.json"
mechanism_quality="$mechanism_root/quality.json"
mechanism_terminal="$mechanism_root/terminal-receipt.json"
cross_graph_root=/mnt/fast-ai/bench-results/qwen38-official-f01e-autoround-tp2-mtp1-f16-piecewise-4k-sentinel-20260826-r1
cross_graph_exact="$cross_graph_root/exact-depth/depth-4096.json"
cross_graph_verification="$cross_graph_root/verification-gates.json"
cross_graph_quality="$cross_graph_root/quality.json"
cross_graph_terminal="$cross_graph_root/terminal-receipt.json"
model_config="$model/config.json"
model_index="$model/model.safetensors.index.json"
mtp_tensors="$model/model_extra_tensors.safetensors"
quant_config="$model/quantization_config.json"
venv_python=/home/steve/.venvs/vllm-xpu/bin/python
image_ref=vllm/vllm-openai-xpu@sha256:f01e24f6c7ff01f1e0662234255a1372297d1dbd89d003cf13c8fad3eab1ba4f
image_id=sha256:f01e24f6c7ff01f1e0662234255a1372297d1dbd89d003cf13c8fad3eab1ba4f
vllm_head=ac7509e2b1db40fec2f03dde1ed4e9dfdc2338c9
root=/mnt/fast-ai/bench-results/$campaign
cache_root=/home/steve/qwen38-current-main-runs/cache-official-f01e-autoround-tp1-mtp2-f16-piecewise-4k-sentinel-20260826-r1
port=19526
name=q38-f01e-ar-tp1-mtp2-pw-f16-4k-r1
served_model=qwen38-f01e-ar-tp1-mtp2-pw-f16-4k-r1
sudo_pass_file=${SUDO_PASS_FILE:-/home/steve/SUDOPASSWORD.txt}

active_name=
active_dir=
die() { printf 'error: %s\n' "$*" >&2; exit 2; }

dockerc() {
  if docker info >/dev/null 2>&1; then docker "$@"
  elif [[ -r "$sudo_pass_file" ]]; then sudo -S -p '' docker "$@" < "$sudo_pass_file"
  else return 126
  fi
}

cleanup_active() {
  [[ -n "$active_name" ]] || return 0
  if [[ -n "$active_dir" && -d "$active_dir" ]]; then
    dockerc logs "$active_name" > "$active_dir/server.log" 2>&1 || true
    dockerc inspect "$active_name" > "$active_dir/container-inspect.json" 2>/dev/null || true
  fi
  dockerc rm -f "$active_name" >/dev/null 2>&1 || true
  if ! dockerc inspect "$active_name" >/dev/null 2>&1; then active_name=; active_dir=; fi
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

quality_contract_passed() {
  "$venv_python" - "$1" <<'PY'
import json, pathlib, sys
value = json.loads(pathlib.Path(sys.argv[1]).read_text())
exact = value.get("exact_cases", [])
repeat = value.get("repeat_case", {})
long_context = value.get("long_context_case", {})
comparisons = value.get("baseline_comparisons", {})
requests = exact + repeat.get("runs", []) + [long_context]
cache_values = [
    r.get("usage", {}).get("prompt_tokens_details", {}).get("cached_tokens") == 0
    for r in requests
]
passed = (
    value.get("pass_all") is True
    and value.get("baseline_match_all") is True
    and len(exact) == 7 and all(c.get("pass") is True for c in exact)
    and repeat.get("pass") is True and repeat.get("repeats") == 8
    and len(repeat.get("runs", [])) == 8
    and len(repeat.get("unique_hashes", [])) == 1
    and long_context.get("pass") is True
    and isinstance(comparisons, dict) and len(comparisons) == 24
    and all(v is True for v in comparisons.values())
    and all(cache_values) and len(cache_values) == 16
)
raise SystemExit(0 if passed else 1)
PY
}

static_check() {
  sha_is "$adjudication" 565687bd30aea3b07c3bd4212f3fdcfb961809258403ba2bcdef82fd03e64a49
  sha_is "$protected_manifest" 4eb3eeb81e40099a64ba0444743074e6b044295ff566c1abc11d864902abb454
  sha_is "$fixture" ebe507b725af6ec0713de4084d0bf52fbbab48b151511e0019c1bac2c5051bd9
  sha_is "$model_manifest" 731d851b39d37f3d58c5a74ad6a7cd3ade1c9e8543ef1612a5d55131ff8331b8
  sha_is "$model_verifier" 5bca853ae644099cb18c58b458dd04dfcc0844d7644f074c4350539504d80ce9
  sha_is "$depth_helper" 8f162c1ab9fde7e0daffed2c4f0d6ff061ad6076c5de716e36f3d883ab4a1067
  sha_is "$quality_helper" 67e65fc342393e5ae6903a332c929b3a2693e1f943c8a819b8447284fe835f6d
  sha_is "$eager_parent" c9dbfb8b9cf8ef23bea5ebe2cb3199c82d678988106e2f619221236e4726dd9e
  sha_is "$graph_parent" dbe7523591ee8bf5722eeba2555dfa9243d00b35bf80bb758b2a26b2fa50b027
  sha_is "$quality_baseline" 347010956e862010faaa03ed909674f1e6fc3c9c951addc160ea3dd3a2c60d46
  sha_is "$parent_terminal" 6cb6b3c8ae06eefe0c516c0dac057c20ca7837e6bae3b96e012a250f41dafa02
  sha_is "$mechanism_result" 5eae8791ed38cdcd59bdf4590ba643d8bc654a0bc9d551319c3b6026baf83bf9
  sha_is "$mechanism_exact" fc29f96559ee4d013d624f6a8efdf5b020123cd016b32ea9b85c7f1966ac36da
  sha_is "$mechanism_verification" 9601176e555dc057c996135b48aa19403241aac324c5b696bf3bd5c95747b98e
  sha_is "$mechanism_quality" a5b9c2a569d02579e17872a2d6a5c8b5030c9496808aedeb4e85a22c829910be
  sha_is "$mechanism_terminal" 0db9ccaf6cd2c17d0edc89bfb594a52498b8fbf0b83e8f128978fb94a9b21724
  sha_is "$cross_graph_exact" e4a845074d3b3f6400e74685792c9869ff9fdb910c90147bbd07641e37e5a8a6
  sha_is "$cross_graph_verification" 2c8c87df733417ad87b0a0cb45717ad961a150ca9c5c83eca86f32fef76b1fdf
  sha_is "$cross_graph_quality" a21cefe783f50801c73d2d9e1964ebcefa4d847a0337f4851e9db77edfde5177
  sha_is "$cross_graph_terminal" 2613733ce0ef40448cd26b2c553fc419ea8551a02d7a8488443022a01ed7d59b
  sha_is "$model_config" 9a1c29a807e34529bec03cba92b4dc00ba61e37a703b029b08a3142b6dc08cd1
  sha_is "$model_index" adf387dee183d109e95cdc4d4988fcd966de326861ff4d66876692170f1e03ad
  sha_is "$mtp_tensors" 94102b67c6b84e65dbb9bae37c00bd88ac1a43ff577ce65fd8842d231c7e89de
  sha_is "$quant_config" 0d1be50a7ad0a3c7350b4b4a4c8c1d26412d2cb2f1503e3ea21b40f1b8470c14
  jq -e '.text_config.mtp_num_hidden_layers == 1 and .text_config.mtp_use_dedicated_embeddings == false' "$model_config" >/dev/null || die "embedded MTP config contract failed"
  jq -e '[.weight_map|to_entries[]|select(.key|startswith("mtp."))] as $m | ($m|length) == 29 and ([$m[].value]|unique) == ["model_extra_tensors.safetensors"]' "$model_index" >/dev/null || die "embedded MTP tensor binding contract failed"
  jq -e '.status == "passed" and .gate.passed == true and .run_identity.depth == 4096 and .run_identity.max_tokens == 128 and .gate.checks.cached_tokens_zero == true and (.response.token_ids|length) == 128 and .response.output_token_ids_sha256 == "3febb16ef2033c31e17817c6753ccdb95ad6e39db394ed4476ee12fb86af78b0"' "$eager_parent" "$graph_parent" >/dev/null || die "clean 4K parent gate failed"
  "$venv_python" - "$eager_parent" "$graph_parent" <<'PY' || die "parent_ids_equal gate failed"
import json, pathlib, sys
eager_ids = json.loads(pathlib.Path(sys.argv[1]).read_text())["response"]["token_ids"]
graph_ids = json.loads(pathlib.Path(sys.argv[2]).read_text())["response"]["token_ids"]
parent_ids_equal = len(eager_ids) == 128 and eager_ids == graph_ids
raise SystemExit(0 if parent_ids_equal else 1)
PY
  quality_contract_passed "$quality_baseline" || die "clean graph parent quality contract failed"
  jq -e '.status == "mixed-depth-human-adjudicated-grade-c" and .coverage.lab_measured_depths == [2048,4096,16384,24576,32768] and .coverage.quarantined_depths == [8192] and (.cells[]|select(.x==4096)|.target_parity) == true and (.cells[]|select(.x==8192)|.first_divergence.one_based) == 99 and .authority.graph_mtp_descendant_authority == false' "$adjudication" >/dev/null || die "corrective parent adjudication gate failed"
  jq -e '.terminal == true and .state == "passed" and .arms["eager-f16"].state == "passed" and .arms["piecewise-f16"].state == "passed"' "$parent_terminal" >/dev/null || die "parent cleanup receipt failed"
  jq -e '.status == "passed" and .gate.passed == true and .run_identity.depth == 4096 and (.response.token_ids|length) == 128 and .response.output_token_ids_sha256 == "3febb16ef2033c31e17817c6753ccdb95ad6e39db394ed4476ee12fb86af78b0"' "$mechanism_exact" >/dev/null || die "MTP2 eager exact-4K mechanism parent failed"
  jq -e '.acceptance.passed == true and .acceptance.accepted_tokens == 80 and .acceptance.drafted_tokens == 94 and .target_verification.passed == true' "$mechanism_verification" >/dev/null || die "MTP2 eager acceptance parent failed"
  quality_contract_passed "$mechanism_quality" || die "MTP2 eager quality parent failed"
  jq -e '.terminal == true and .state == "quarantined-target-verification-failed" and .arm.per_depth_verification["4096"].acceptance.passed == true and .arm.per_depth_verification["4096"].target_verification.passed == true' "$mechanism_terminal" >/dev/null || die "MTP2 eager partial-parent receipt changed"
  jq -e '.status == "passed" and .gate.passed == true and .run_identity.depth == 4096 and (.response.token_ids|length) == 128 and .response.output_token_ids_sha256 == "3febb16ef2033c31e17817c6753ccdb95ad6e39db394ed4476ee12fb86af78b0"' "$cross_graph_exact" >/dev/null || die "TP2/MTP1 graph precedent exact gate failed"
  jq -e '.acceptance.passed == true and .dual_parent_verification.passed == true and .exact.passed == true' "$cross_graph_verification" >/dev/null || die "TP2/MTP1 graph precedent mechanism gate failed"
  quality_contract_passed "$cross_graph_quality" || die "TP2/MTP1 graph precedent quality gate failed"
  jq -e '.terminal == true and .state == "passed-quality-clean-sentinel" and .launch_git_head == "2f31004069c004acaa32863e65b330165294578c" and .arm.publication_authorized == false and .arm.descendant_expansion_authorized == false' "$cross_graph_terminal" >/dev/null || die "TP2/MTP1 graph precedent receipt failed"
  jq -e --arg id "$campaign" --arg image "$image_ref" --arg root "$root" --argjson port "$port" '.campaign_id == $id and .state == "preregistered-not-launched" and .run_identity.image == $image and .run_identity.tensor_parallel == 1 and .run_identity.mtp_depth == 2 and .run_identity.graph_mode == "PIECEWISE" and .exact_depth_contract.depths == [4096] and .execution.output_root == $root and .execution.port == $port and .coverage_contract.id == "qwen38-tp1-vllm-xpu-autoround-mtp-matrix" and .coverage_contract.selectors.tp == 1 and .coverage_contract.selectors.mtp == 2 and .coverage_contract.selectors.active_context_tokens == 4096 and .coverage_contract.selectors.graph_mode == "PIECEWISE" and .coverage_contract.selectors.kv == "f16" and .coverage_contract.other_cells_authorized == 0 and .interpretation.automatic_publication == false and .interpretation.automatic_descendant_expansion == false' "$manifest" >/dev/null || die "manifest invariant failed"
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

render_users() { local node; for node in /dev/dri/renderD*; do [[ -e "$node" ]] || continue; fuser "$node" 2>/dev/null || true; done; }
port_users() { ss -ltnH "sport = :$port" 2>/dev/null || true; }
require_idle() {
  [[ -z "$(dockerc ps -q)" ]] || die "a Docker container is already running"
  ! pgrep -af '[E]ngineCore|[v]llm serve|[l]lama-server' >/dev/null || die "a model server process is already running"
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
  awk '{line=tolower($0); if (line ~ /(qwen3_next_mtp|speculative|speculator|mtp)/ && line ~ /(not supported|unsupported|unknown method|does not support)/) found=1} END {exit(found ? 0 : 1)}' "$root/server-startup.log" "$root/server.log" >/dev/null 2>&1
}

write_verification_gates() {
  "$venv_python" - "$root/metrics.before.prom" "$root/metrics.after-depth.prom" "$root/exact-depth/depth-4096.json" "$eager_parent" "$graph_parent" "$root/verification-gates.json" <<'PY'
import hashlib, json, pathlib, re, sys
before_path, after_path, candidate_path, eager_path, graph_path, out_path = map(pathlib.Path, sys.argv[1:])
def metric(path, name):
    pattern = re.compile(rf"^{re.escape(name)}(?:\{{[^}}]*\}})?\s+([-+0-9.eE]+)$")
    vals = [float(m.group(1)) for line in path.read_text(errors="replace").splitlines() if (m := pattern.match(line))]
    return sum(vals) if vals else None
draft_name = "vllm:spec_decode_num_draft_tokens_total"
accept_name = "vllm:spec_decode_num_accepted_tokens_total"
bd, ad = metric(before_path, draft_name), metric(after_path, draft_name)
ba, aa = metric(before_path, accept_name), metric(after_path, accept_name)
drafted = ad - bd if None not in (bd, ad) else None
accepted = aa - ba if None not in (ba, aa) else None
acceptance_pass = isinstance(drafted, float) and isinstance(accepted, float) and drafted > 0 and 0 < accepted <= drafted
def load(path):
    try: return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError): return {}
candidate, eager, graph = load(candidate_path), load(eager_path), load(graph_path)
candidate_ids = candidate.get("response", {}).get("token_ids")
eager_ids = eager.get("response", {}).get("token_ids")
graph_ids = graph.get("response", {}).get("token_ids")
candidate_exact = candidate.get("status") == "passed" and candidate.get("gate", {}).get("passed") is True and candidate.get("gate", {}).get("checks", {}).get("cached_tokens_zero") is True and isinstance(candidate_ids, list) and len(candidate_ids) == 128
parent_ids_equal = isinstance(eager_ids, list) and len(eager_ids) == 128 and eager_ids == graph_ids
dual_parent_pass = candidate_exact and parent_ids_equal and candidate_ids == eager_ids == graph_ids
def digest(ids): return hashlib.sha256(json.dumps(ids, separators=(",", ":")).encode()).hexdigest() if isinstance(ids, list) else None
def divergence(left, right):
    if not isinstance(left, list) or not isinstance(right, list): return {"reason": "missing-token-array"}
    for i, (a, b) in enumerate(zip(left, right)):
        if a != b: return {"zero_based": i, "one_based": i + 1, "candidate": a, "parent": b}
    return None if len(left) == len(right) else {"zero_based": min(len(left), len(right)), "reason": "length-mismatch"}
value = {
  "acceptance": {"passed": acceptance_pass, "drafted_tokens": drafted, "accepted_tokens": accepted, "acceptance_rate": accepted / drafted if acceptance_pass else None},
  "exact": {"passed": candidate_exact, "cached_tokens_zero": candidate.get("gate", {}).get("checks", {}).get("cached_tokens_zero")},
  "dual_parent_verification": {"passed": dual_parent_pass, "parent_ids_equal": parent_ids_equal, "candidate_ids_sha256": digest(candidate_ids), "eager_parent_ids_sha256": digest(eager_ids), "graph_parent_ids_sha256": digest(graph_ids), "candidate_vs_eager_first_divergence": divergence(candidate_ids, eager_ids), "candidate_vs_graph_first_divergence": divergence(candidate_ids, graph_ids), "contract": "candidate_ids == eager_ids == graph_ids"},
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
expected = ["rank_0_0"]
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
    "policy": "Only rank_0_0 is allowed for this TP1 run; shared AOT/cache files are inventoried separately.",
}
out.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
raise SystemExit(0 if value["passed"] else 1)
PY
}

write_arm_result() {
  local state=$1 reason=$2 depth_rc=$3 quality_rc=$4 startup_ok=$5 runner_rc=$6 cleanup_ok=$7 acceptance_ok=$8 parent_ok=$9 quality_ok=${10}
  "$venv_python" - "$root/arm-result.json" "$state" "$reason" "$depth_rc" "$quality_rc" "$startup_ok" "$runner_rc" "$cleanup_ok" "$acceptance_ok" "$parent_ok" "$quality_ok" <<'PY'
import datetime as dt, json, pathlib, sys
path, state, reason, depth_rc, quality_rc, startup_ok, runner_rc, cleanup_ok, acceptance_ok, parent_ok, quality_ok = sys.argv[1:]
cache_path = pathlib.Path(path).parent / "rank-cache-isolation.json"
try: cache_ok = json.loads(cache_path.read_text()).get("passed") is True
except (OSError, json.JSONDecodeError): cache_ok = False
value = {"schema":"neural.download.qwen38-official-autoround-mtp2-f16-piecewise-4k-sentinel-arm.v1", "created_at_utc":dt.datetime.now(dt.UTC).isoformat(), "state":state, "reason":reason, "exact_4k_return_code":int(depth_rc), "quality_return_code":int(quality_rc), "startup_identity_passed":startup_ok=="1", "rank_cache_isolation_passed":cache_ok, "cleanup_passed":cleanup_ok=="1", "acceptance_passed":acceptance_ok=="1", "dual_parent_verification_passed":parent_ok=="1", "quality_contract_passed":quality_ok=="1", "runner_return_code":int(runner_rc), "historical_replacement_allowed":False, "publication_authorized":False, "descendant_expansion_authorized":False, "descendant_execution_authorized":False}
pathlib.Path(path).write_text(json.dumps(value, indent=2, sort_keys=True)+"\n")
PY
}

terminal_receipt() {
  local launch_head=$1 runner_rc=$2
  "$venv_python" - "$root" "$campaign" "$launch_head" "$runner_rc" <<'PY'
import datetime as dt, json, pathlib, sys
root, campaign, launch_head, runner_rc = pathlib.Path(sys.argv[1]), sys.argv[2], sys.argv[3], sys.argv[4]
arm_path = root/"arm-result.json"
arm = json.loads(arm_path.read_text()) if arm_path.is_file() else {"state":"failed","reason":"arm-result-missing"}
value={"schema":"neural.download.qwen38-official-autoround-mtp2-f16-piecewise-4k-sentinel-terminal.v1","campaign_id":campaign,"created_at_utc":dt.datetime.now(dt.UTC).isoformat(),"state":arm["state"],"terminal":True,"launch_git_head":launch_head,"runner_return_code":int(runner_rc),"arm":arm,"historical_replacement_allowed":False,"protected_profiles_untouched":True,"automatic_publication":False,"automatic_descendant_expansion":False}
(root/"terminal-receipt.json").write_text(json.dumps(value,indent=2,sort_keys=True)+"\n")
PY
}

run_sentinel() {
  local startup_ok=0 depth_rc=125 quality_rc=125 runner_rc=0 cleanup_ok=0 acceptance_ok=0 parent_ok=0 quality_ok=0 cache_ok=0
  local state=failed reason=unknown observed_image observed_head versions healthy=0 running i
  local -a args=(
    "$model" --host 0.0.0.0 --port 8000 --trust-remote-code
    --served-model-name "$served_model"
    --tensor-parallel-size 1 --pipeline-parallel-size 1 --data-parallel-size 1
    --max-model-len 32896 --max-num-seqs 1 --max-num-batched-tokens 1024
    --gpu-memory-utilization 0.90 --dtype float16
    --reasoning-parser qwen3 --default-chat-template-kwargs '{"enable_thinking": false}'
    --enable-prompt-tokens-details --no-enable-prefix-caching
    --enable-chunked-prefill --async-scheduling
    --compilation-config '{"cudagraph_mode":"PIECEWISE","cudagraph_capture_sizes":[1],"max_cudagraph_capture_size":1}'
    --speculative-config '{"method":"qwen3_next_mtp","num_speculative_tokens":2}'
  )
  printf '%q ' "${args[@]}" > "$root/server-args.shell.txt"; printf '\n' >> "$root/server-args.shell.txt"

  if ! dockerc run -d --name "$name" --device /dev/dri --group-add 44 --group-add 992 \
      --ipc=host --shm-size 16g -v /dev/dri/by-path:/dev/dri/by-path:ro \
      -v "$model:$model:ro" -v "$cache_root:/run-cache" -p "127.0.0.1:$port:8000" \
      -e ZE_AFFINITY_MASK=0 -e ONEAPI_DEVICE_SELECTOR=level_zero:0 \
      -e VLLM_NO_USAGE_STATS=1 -e PYTHONHASHSEED=0 -e VLLM_XPU_ENABLE_XPU_GRAPH=1 \
      -e VLLM_CACHE_ROOT=/run-cache/vllm -e XDG_CACHE_HOME=/run-cache/xdg \
      -e CCL_ZE_IPC_EXCHANGE=sockets "$image_ref" "${args[@]}" > "$root/container-id.txt"; then
    dockerc rm -f "$name" >/dev/null 2>&1 || true
    strict_postcleanup && cleanup_ok=1
    write_arm_result failed docker-run-failed 125 125 0 31 "$cleanup_ok" 0 0 0
    return 31
  fi
  active_name=$name; active_dir=$root
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
    if explicit_speculator_unsupported; then state=unsupported; reason=explicit-mtp2-speculator-unsupported; runner_rc=42
    else state=failed; reason=startup-failed-without-explicit-speculator-classification; runner_rc=32
    fi
    strict_postcleanup && cleanup_ok=1
    write_arm_result "$state" "$reason" 125 125 0 "$runner_rc" "$cleanup_ok" 0 0 0
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
     ! grep -Fq 'enforce_eager=False' "$root/server-startup.log" || \
     ! grep -Fq 'kv_cache_dtype=auto' "$root/server-startup.log" || \
     ! grep -Fq "speculative_config=SpeculativeConfig(method='mtp', model='$model', num_spec_tokens=2)" "$root/server-startup.log" || \
     ! grep -Fq 'world_size=1 rank=0 local_rank=0' "$root/server-startup.log" || \
     ! grep -Fq 'TP rank 0' "$root/server-startup.log" || \
     ! grep -Fq 'Capturing CUDA graphs (mixed prefill-decode, PIECEWISE)' "$root/server-startup.log" || \
     ! grep -Fq 'Graph capturing finished' "$root/server-startup.log" || \
     grep -Fq 'Capturing CUDA graphs (decode, FULL)' "$root/server-startup.log"; then
    cleanup_active; strict_postcleanup && cleanup_ok=1
    write_arm_result failed startup-identity-graph-or-topology-gate-failed 125 125 0 33 "$cleanup_ok" 0 0 0
    return 33
  fi
  startup_ok=1
  curl -fsS "http://127.0.0.1:$port/v1/models" > "$root/models.json" || runner_rc=34

  mkdir "$root/exact-depth"
  curl -fsS "http://127.0.0.1:$port/metrics" > "$root/metrics.before.prom" || runner_rc=35
  "$venv_python" "$depth_helper" --execute --fixture "$fixture" --depth 4096 \
    --case-id depth-4096 --context-capacity 32896 --response-adapter vllm \
    --base-url "http://127.0.0.1:$port" --model "$served_model" \
    --timeout 900 --out "$root/exact-depth/depth-4096.json" \
    > "$root/exact-depth/depth-4096.stdout.json" 2> "$root/exact-depth/depth-4096.stderr.log"
  depth_rc=$?
  printf '%s\n' "$depth_rc" > "$root/exact-depth/depth-4096.rc"
  curl -fsS "http://127.0.0.1:$port/metrics" > "$root/metrics.after-depth.prom" || runner_rc=35
  write_verification_gates || runner_rc=36
  jq -e '.acceptance.passed == true' "$root/verification-gates.json" >/dev/null && acceptance_ok=1
  jq -e '.exact.passed == true and .dual_parent_verification.passed == true' "$root/verification-gates.json" >/dev/null && parent_ok=1

  "$venv_python" "$quality_helper" --base-url "http://127.0.0.1:$port" \
    --model "$served_model" --tokenizer "$model" --timeout 900 \
    --repeat-runs 8 --long-context-tokens 8192 --request-id-prefix "$campaign" \
    --chat-template-kwargs-json '{"enable_thinking":false}' \
    --baseline-json "$quality_baseline" --require-baseline \
    --output-json "$root/quality.json" > "$root/quality.stdout.log" 2>&1
  quality_rc=$?
  quality_contract_passed "$root/quality.json" && quality_ok=1
  write_cache_isolation && cache_ok=1
  cleanup_active; strict_postcleanup && cleanup_ok=1

  if (( cleanup_ok == 0 )); then state=failed; reason=strict-postcleanup-failed; runner_rc=39
  elif (( cache_ok == 0 )); then state=failed; reason=rank-cache-isolation-gate-failed; runner_rc=41
  elif (( runner_rc != 0 )); then state=failed; reason=models-metrics-or-verification-endpoint-failed; runner_rc=35
  elif (( depth_rc == 0 && quality_rc == 0 && acceptance_ok == 1 && parent_ok == 1 && quality_ok == 1 )); then state=passed-quality-clean-sentinel; reason=exact-4k-acceptance-dual-parent-quality-graph-topology-and-cleanup-passed; runner_rc=0
  elif (( depth_rc == 0 && acceptance_ok == 0 )); then state=quarantined-acceptance-failed; reason=exact-4k-passed-but-isolated-acceptance-failed; runner_rc=38
  elif (( depth_rc == 0 && parent_ok == 0 )); then state=quarantined-parent-parity-failed; reason=exact-4k-passed-but-dual-parent-parity-failed; runner_rc=39
  elif (( depth_rc == 0 && (quality_rc != 0 || quality_ok == 0) )); then state=quarantined-quality-failed; reason=exact-4k-passed-but-full-quality-contract-failed; runner_rc=40
  else state=quarantined-exact-depth-failed; reason=exact-4k-gate-failed-diagnostic-evidence-retained; runner_rc=37
  fi
  write_arm_result "$state" "$reason" "$depth_rc" "$quality_rc" "$startup_ok" "$runner_rc" "$cleanup_ok" "$acceptance_ok" "$parent_ok" "$quality_ok"
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
  help) printf 'usage: %s --check | --plan | --execute --ack %q\n' "$self" "$ack_expected" ;;
  check)
    static_check
    printf '{"campaign_id":"%s","status":"PASS","launch_performed":false}\n' "$campaign"
    ;;
  plan)
    static_check
    jq '{campaign_id,state,run_identity,parent_authority,historical_corruption_caveat,exact_depth_contract,quality_contract,topology_and_graph_contract,execution,terminal_classification,coverage_contract,interpretation}' "$manifest"
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
    sha256sum "$manifest" "$note" "$self" "$test_file" "$adjudication" "$protected_manifest" \
      "$fixture" "$model_manifest" "$model_verifier" "$depth_helper" "$quality_helper" \
      "$eager_parent" "$graph_parent" "$quality_baseline" "$parent_terminal" \
      "$mechanism_result" "$mechanism_exact" "$mechanism_verification" "$mechanism_quality" "$mechanism_terminal" \
      "$cross_graph_exact" "$cross_graph_verification" "$cross_graph_quality" "$cross_graph_terminal" \
      "$model_config" "$model_index" "$mtp_tensors" "$quant_config" > "$root/input-sha256sums.txt"
    if ! "$model_verifier" "$model_manifest" "$model" --json "$root/model-verification.json" > "$root/model-verification.log" 2>&1; then
      cleanup_ok=0; strict_postcleanup && cleanup_ok=1
      write_arm_result failed model-verification-failed 125 125 0 41 "$cleanup_ok" 0 0 0
      terminal_receipt "$launch_head" 41
      exit 41
    fi
    run_sentinel; runner_rc=$?
    terminal_receipt "$launch_head" "$runner_rc"
    printf '{"campaign_id":"%s","terminal_receipt":"%s/terminal-receipt.json"}\n' "$campaign" "$root"
    exit "$runner_rc"
    ;;
esac
