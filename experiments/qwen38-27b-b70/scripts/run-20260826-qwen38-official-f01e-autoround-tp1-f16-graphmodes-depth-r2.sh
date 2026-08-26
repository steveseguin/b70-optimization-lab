#!/usr/bin/env bash
set -uo pipefail

repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)
campaign=qwen38-official-f01e-autoround-tp1-f16-graphmodes-depth-20260826-r2
ack_expected="RUN $campaign"
manifest="$repo/experiments/qwen38-27b-b70/data/2026-08-26-qwen38-official-f01e-autoround-tp1-f16-graphmodes-depth-r2-prereg.json"
note="$repo/experiments/qwen38-27b-b70/notes/2026-08-26-qwen38-official-f01e-autoround-tp1-f16-graphmodes-depth-r2-preregistration.md"
self=$(realpath -- "${BASH_SOURCE[0]}")
test_file="$repo/experiments/qwen38-27b-b70/scripts/test_qwen38_official_f01e_autoround_tp1_f16_graphmodes_depth_r2.py"
model=/mnt/usb-models/llm-models/qwen3.8-27b-int4-autoround-devan
model_manifest="$repo/repro/qwen38-27b-autoround-int4-b70/manifests/model.json"
model_verifier="$repo/repro/qwen38-27b-autoround-int4-b70/scripts/verify-model-direct.py"
fixture="$repo/data/qwen27-exact-depth/qwen38-bce40ca-exact-depth-v1.json"
depth_helper="$repo/scripts/bench-openai-token-depth-suite.py"
quality_helper="$repo/scripts/qwen38-text-quality-suite.py"
quality_baseline=/mnt/usb-models/bench-results/qwen38-27b-autoround-int4-b70/nightly-strict-20260823/tp1-mtp0-f16-graph-seed0-natural-eos-replay-a-baseline-quality/quality.json
venv_python=/home/steve/.venvs/vllm-xpu/bin/python
image_ref=vllm/vllm-openai-xpu@sha256:f01e24f6c7ff01f1e0662234255a1372297d1dbd89d003cf13c8fad3eab1ba4f
image_id=sha256:f01e24f6c7ff01f1e0662234255a1372297d1dbd89d003cf13c8fad3eab1ba4f
vllm_head=ac7509e2b1db40fec2f03dde1ed4e9dfdc2338c9
root=/mnt/fast-ai/bench-results/$campaign
cache_root=/home/steve/qwen38-current-main-runs/cache-official-f01e-autoround-tp1-f16-graphmodes-depth-20260826-r2
sudo_pass_file=${SUDO_PASS_FILE:-/home/steve/SUDOPASSWORD.txt}
depths=(2048 4096 8192 16384 24576 32768)

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

sha_is() {
  local path=$1 expected=$2
  [[ -f "$path" ]] || die "missing frozen input: $path"
  local observed
  observed=$(sha256sum "$path" | awk '{print $1}') || die "cannot hash $path"
  [[ "$observed" == "$expected" ]] || die "frozen input changed: $path ($observed)"
}

static_check() {
  sha_is "$fixture" ebe507b725af6ec0713de4084d0bf52fbbab48b151511e0019c1bac2c5051bd9
  sha_is "$model_manifest" 731d851b39d37f3d58c5a74ad6a7cd3ade1c9e8543ef1612a5d55131ff8331b8
  sha_is "$model_verifier" 5bca853ae644099cb18c58b458dd04dfcc0844d7644f074c4350539504d80ce9
  sha_is "$depth_helper" 8f162c1ab9fde7e0daffed2c4f0d6ff061ad6076c5de716e36f3d883ab4a1067
  sha_is "$quality_helper" 67e65fc342393e5ae6903a332c929b3a2693e1f943c8a819b8447284fe835f6d
  sha_is "$quality_baseline" 738b8ed03746ed976c157bf9c392a2637de7c477b719c55f2d533b398adbef18
  jq -e --arg id "$campaign" --arg image "$image_ref" '
    .schema == "neural.download.qwen38-official-autoround-graphmodes-depth-prereg.v1" and
    .campaign_id == $id and .state == "preregistered-not-launched" and
    .run_identity.image == $image and .run_identity.tensor_parallel == 1 and
    .run_identity.mtp_depth == 0 and .run_identity.kv_cache_dtype == "float16" and
    .run_identity.max_model_len == 32896 and
    [.arms[].graph_mode] == ["off", "PIECEWISE"] and
    .exact_depth_contract.depths == [2048,4096,8192,16384,24576,32768] and
    .interpretation.historical_replacement_allowed == false
  ' "$manifest" >/dev/null || die "manifest invariant failed"
  bash -n "$self" || die "runner shell syntax failed"
  "$venv_python" "$test_file" >/dev/null || die "inert tests failed"
}

require_clean_pushed_main() {
  [[ "$(git -C "$repo" branch --show-current)" == main ]] || die "repository must be on main"
  [[ -z "$(git -C "$repo" status --porcelain=v1 --untracked-files=all)" ]] || die "repository must be clean"
  local head cached live
  head=$(git -C "$repo" rev-parse HEAD) || die "cannot resolve HEAD"
  cached=$(git -C "$repo" rev-parse origin/main) || die "cannot resolve origin/main"
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

require_idle() {
  [[ -z "$(dockerc ps -q)" ]] || die "a Docker container is already running"
  if pgrep -af '[E]ngineCore|[v]llm serve|[l]lama-server' >/dev/null; then
    die "a model server process is already running"
  fi
  [[ -z "$(render_users)" ]] || die "a process already owns a render node"
  local port
  for port in 19464 19465; do
    [[ -z "$(ss -ltnH "sport = :$port" 2>/dev/null)" ]] || die "port $port is occupied"
  done
  [[ ! -e "$root" ]] || die "output root already exists: $root"
  [[ ! -e "$cache_root" ]] || die "cache root already exists: $cache_root"
  [[ "$(findmnt -n -o FSTYPE -T "$(dirname "$root")")" == ext4 ]] || die "output root must be ext4"
  [[ "$(findmnt -n -o FSTYPE -T "$(dirname "$cache_root")")" == ext4 ]] || die "cache root must be ext4"
}

write_arm_result() {
  local arm_dir=$1 state=$2 reason=$3 depth_passed=$4 quality_rc=$5 startup_ok=$6 runner_rc=$7
  "$venv_python" - "$arm_dir/arm-result.json" "$state" "$reason" "$depth_passed" "$quality_rc" "$startup_ok" "$runner_rc" <<'PY'
import datetime as dt, json, pathlib, sys
path, state, reason, depth_passed, quality_rc, startup_ok, runner_rc = sys.argv[1:]
value = {
    "schema": "neural.download.qwen38-official-autoround-graphmode-depth-arm.v1",
    "created_at_utc": dt.datetime.now(dt.UTC).isoformat(),
    "state": state,
    "reason": reason,
    "passed_depth_count": int(depth_passed),
    "quality_return_code": int(quality_rc),
    "startup_identity_passed": startup_ok == "1",
    "runner_return_code": int(runner_rc),
    "historical_replacement_allowed": False,
}
pathlib.Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
PY
}

run_arm() {
  local arm=$1 graph_mode=$2 port=$3
  local arm_dir="$root/$arm" cache_dir="$cache_root/$arm" name="q38-f01e-ar-${arm}-r2"
  mkdir "$arm_dir" "$cache_dir" || return 30
  local startup_ok=0 depth_passed=0 quality_rc=125 runner_rc=0 reason=unknown state=failed
  local container_started=0
  cleanup_arm() {
    if (( container_started )); then
      dockerc logs "$name" > "$arm_dir/server.log" 2>&1 || true
      dockerc inspect "$name" > "$arm_dir/container-inspect.json" 2>/dev/null || true
      dockerc rm -f "$name" >/dev/null 2>&1 || true
      container_started=0
    fi
  }

  local -a args=(
    "$model" --host 0.0.0.0 --port 8000 --trust-remote-code
    --served-model-name qwen38-official-f01e-autoround-tp1
    --tensor-parallel-size 1 --pipeline-parallel-size 1 --data-parallel-size 1
    --max-model-len 32896 --max-num-seqs 1 --max-num-batched-tokens 1024
    --gpu-memory-utilization 0.90 --dtype float16 --reasoning-parser qwen3
    --default-chat-template-kwargs '{"enable_thinking": false}'
    --enable-prompt-tokens-details --no-enable-prefix-caching
    --enable-chunked-prefill --async-scheduling
  )
  local -a env_args=(
    -e ZE_AFFINITY_MASK=0 -e ONEAPI_DEVICE_SELECTOR=level_zero:0
    -e VLLM_NO_USAGE_STATS=1 -e PYTHONHASHSEED=0
    -e VLLM_CACHE_ROOT=/run-cache/vllm -e XDG_CACHE_HOME=/run-cache/xdg
    -e CCL_ZE_IPC_EXCHANGE=sockets
  )
  if [[ "$graph_mode" == off ]]; then
    args+=(--enforce-eager)
  else
    env_args+=(-e VLLM_XPU_ENABLE_XPU_GRAPH=1)
    args+=(--compilation-config '{"cudagraph_mode":"PIECEWISE","cudagraph_capture_sizes":[1],"max_cudagraph_capture_size":1}')
  fi
  printf '%q ' "${args[@]}" > "$arm_dir/server-args.shell.txt"
  printf '\n' >> "$arm_dir/server-args.shell.txt"

  if ! dockerc run -d --name "$name" --device /dev/dri --group-add 44 --group-add 992 \
      --ipc=host --shm-size 16g -v /dev/dri/by-path:/dev/dri/by-path:ro \
      -v "$model:$model:ro" -v "$cache_dir:/run-cache" -p "127.0.0.1:$port:8000" \
      "${env_args[@]}" "$image_ref" "${args[@]}" > "$arm_dir/container-id.txt"; then
    reason=docker-run-failed; runner_rc=31
    write_arm_result "$arm_dir" failed "$reason" 0 125 0 "$runner_rc"
    return "$runner_rc"
  fi
  container_started=1
  local healthy=0 i running
  for i in $(seq 1 240); do
    if curl -fsS "http://127.0.0.1:$port/health" > "$arm_dir/health.json" 2>/dev/null; then healthy=1; break; fi
    running=$(dockerc inspect --format '{{.State.Running}}' "$name" 2>/dev/null || printf false)
    [[ "$running" == true ]] || break
    sleep 5
  done
  dockerc logs "$name" > "$arm_dir/server-startup.log" 2>&1 || true
  if (( ! healthy )); then
    reason=startup-failed; runner_rc=32
    cleanup_arm
    write_arm_result "$arm_dir" failed "$reason" 0 125 0 "$runner_rc"
    return "$runner_rc"
  fi

  local observed_image observed_head versions
  observed_image=$(dockerc inspect --format '{{.Image}}' "$name" 2>/dev/null || true)
  observed_head=$(dockerc exec "$name" git -C /workspace/vllm rev-parse HEAD 2>/dev/null || true)
  versions=$(dockerc exec "$name" python3 -c 'import importlib.metadata as m; print(m.version("vllm")); print(m.version("vllm-xpu-kernels"))' 2>/dev/null || true)
  printf '%s\n' "$observed_head" > "$arm_dir/vllm-source-commit.txt"
  printf '%s\n' "$versions" > "$arm_dir/stack-versions.txt"
  if [[ "$observed_image" != "$image_id" || "$observed_head" != "$vllm_head" ]] || \
     ! grep -Fxq '0.27.2rc1.dev77+gac7509e2b.xpu' "$arm_dir/stack-versions.txt" || \
     ! grep -Fxq '0.1.12.3' "$arm_dir/stack-versions.txt" || \
     ! grep -Fq 'quantization=inc' "$arm_dir/server-startup.log"; then
    reason=startup-identity-mismatch; runner_rc=33
    cleanup_arm
    write_arm_result "$arm_dir" failed "$reason" 0 125 0 "$runner_rc"
    return "$runner_rc"
  fi
  if [[ "$graph_mode" == off ]]; then
    grep -Fq 'enforce_eager=True' "$arm_dir/server-startup.log" && \
      ! grep -Fq 'Graph capturing finished' "$arm_dir/server-startup.log" || {
        reason=eager-marker-gate-failed; runner_rc=34; cleanup_arm
        write_arm_result "$arm_dir" failed "$reason" 0 125 0 "$runner_rc"; return "$runner_rc";
      }
  else
    grep -Fq 'enforce_eager=False' "$arm_dir/server-startup.log" && \
      grep -Fq 'Capturing CUDA graphs (mixed prefill-decode, PIECEWISE)' "$arm_dir/server-startup.log" && \
      grep -Fq 'Graph capturing finished' "$arm_dir/server-startup.log" && \
      ! grep -Fq 'Capturing CUDA graphs (decode, FULL)' "$arm_dir/server-startup.log" || {
        reason=piecewise-marker-gate-failed; runner_rc=35; cleanup_arm
        write_arm_result "$arm_dir" failed "$reason" 0 125 0 "$runner_rc"; return "$runner_rc";
      }
  fi
  startup_ok=1
  curl -fsS "http://127.0.0.1:$port/v1/models" > "$arm_dir/models.json" || runner_rc=36

  local depth rc
  mkdir "$arm_dir/exact-depth"
  for depth in "${depths[@]}"; do
    "$venv_python" "$depth_helper" --execute --fixture "$fixture" --depth "$depth" \
      --case-id "depth-$depth" --response-adapter vllm \
      --base-url "http://127.0.0.1:$port" --model qwen38-official-f01e-autoround-tp1 \
      --timeout 900 --out "$arm_dir/exact-depth/depth-$depth.json" \
      > "$arm_dir/exact-depth/depth-$depth.stdout.json" \
      2> "$arm_dir/exact-depth/depth-$depth.stderr.log"
    rc=$?
    printf '%s\n' "$rc" > "$arm_dir/exact-depth/depth-$depth.rc"
    if (( rc == 0 )); then depth_passed=$((depth_passed + 1)); else runner_rc=37; fi
  done

  "$venv_python" "$quality_helper" --base-url "http://127.0.0.1:$port" \
    --model qwen38-official-f01e-autoround-tp1 --tokenizer "$model" --timeout 900 \
    --repeat-runs 8 --long-context-tokens 8192 \
    --request-id-prefix "$campaign-$arm" \
    --chat-template-kwargs-json '{"enable_thinking":false}' \
    --baseline-json "$quality_baseline" --require-baseline \
    --output-json "$arm_dir/quality.json" > "$arm_dir/quality.stdout.log" 2>&1
  quality_rc=$?
  cleanup_arm

  if (( depth_passed == 6 && quality_rc == 0 && runner_rc == 0 )); then
    state=passed; reason=exact-depth-and-full-quality-passed
  elif (( depth_passed > 0 )); then
    state=screened-needs-review; reason=one-or-more-exact-depths-passed-but-full-arm-gate-did-not
    runner_rc=38
  else
    state=failed; reason=no-exact-depth-receipt-passed; runner_rc=39
  fi
  write_arm_result "$arm_dir" "$state" "$reason" "$depth_passed" "$quality_rc" "$startup_ok" "$runner_rc"
  return "$runner_rc"
}

terminal_receipt() {
  local launch_head=$1 eager_rc=$2 piecewise_rc=$3
  "$venv_python" - "$root" "$campaign" "$launch_head" "$eager_rc" "$piecewise_rc" <<'PY'
import datetime as dt, hashlib, json, pathlib, sys
root, campaign, launch_head, eager_rc, piecewise_rc = sys.argv[1:]
root = pathlib.Path(root)
arms = {}
for arm in ("eager-f16", "piecewise-f16"):
    path = root / arm / "arm-result.json"
    arms[arm] = json.loads(path.read_text()) if path.is_file() else {"state": "missing"}
passed = all(value.get("state") == "passed" for value in arms.values())
receipt = {
    "schema": "neural.download.qwen38-official-autoround-graphmodes-depth-terminal.v1",
    "campaign_id": campaign,
    "created_at_utc": dt.datetime.now(dt.UTC).isoformat(),
    "state": "passed" if passed else "terminal-with-screened-or-failed-arm",
    "terminal": True,
    "launch_git_head": launch_head,
    "arm_return_codes": {"eager-f16": int(eager_rc), "piecewise-f16": int(piecewise_rc)},
    "arms": arms,
    "depth_zero_state": "missing",
    "historical_replacement_allowed": False,
    "protected_full_and_piecewise_profile_untouched": True,
}
(root / "terminal-receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
PY
}

action=help ack=
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
    jq '{campaign_id,state,arms,exact_depth_contract,execution,interpretation}' "$manifest"
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
    sha256sum "$manifest" "$note" "$self" "$test_file" "$fixture" "$model_manifest" \
      "$model_verifier" "$depth_helper" "$quality_helper" > "$root/input-sha256sums.txt"
    "$model_verifier" "$model_manifest" "$model" --json "$root/model-verification.json" \
      > "$root/model-verification.log" 2>&1 || die "model verification failed"
    run_arm eager-f16 off 19464; eager_rc=$?
    [[ -z "$(dockerc ps -q)" ]] || die "container survived eager arm"
    [[ -z "$(render_users)" ]] || die "render owner survived eager arm"
    run_arm piecewise-f16 PIECEWISE 19465; piecewise_rc=$?
    [[ -z "$(dockerc ps -q)" ]] || die "container survived piecewise arm"
    [[ -z "$(render_users)" ]] || die "render owner survived piecewise arm"
    terminal_receipt "$launch_head" "$eager_rc" "$piecewise_rc"
    printf '{"campaign_id":"%s","terminal_receipt":"%s/terminal-receipt.json"}\n' "$campaign" "$root"
    [[ "$eager_rc" == 0 && "$piecewise_rc" == 0 ]]
    ;;
esac
