#!/usr/bin/env bash
set -euo pipefail

# Fresh-process, isolated eager mtp.fc BF16-vs-W4A16 operator screen.
# This driver is intentionally launch-blocked until a later tracked
# preregistration names the final driver bytes and explicitly authorizes Q1.
# No argument or environment variable can remove that block.

repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd -P)
driver=$(realpath -- "$0")
operator="$repo/experiments/qwen38-27b-b70/scripts/qwen38_mtp_fc_int4_operator.py"
health_supervisor="$repo/experiments/qwen38-27b-b70/scripts/qwen38_gpu3_incumbent_control_health_supervisor.py"
python=/home/steve/.venvs/vllm-xpu/bin/python
stage=/home/steve/staged-xpu-commitfix-graphfa-composite-20260820
stage_package="$stage/vllm_xpu_kernels"
extension="$stage_package/_xpu_C.abi3.so"
stage_manifest="$repo/repro/qwen38-27b-autoround-int4-b70/manifests/staged-xpu-commitfix-graphfa-composite-20260820.graph.sha256"
torch_lib=/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/lib
venv_lib=/home/steve/.venvs/vllm-xpu/lib
cache_root=/mnt/usb-models/llm-runtime/vllm-cache/qwen38-postrecovery-marginfree-mtp5-20260820/torch_compile_cache
operator_sha=228da7aa46b6521e253a8507265192a529b786a09c3f885cd4d63a50c17beca9
health_supervisor_sha=eb619535786a3c7a8929b2d3b1c3848486d3edc1b96804c79831eaf8c3923375
extension_sha=4dd336013d155aab004fb1c916118957cb9349b491938da65769f2d8af18ffb0
stage_manifest_sha=47861e8391b6b25dd9c3eb25e25c5939753aa470858b667d5bdf181344db18da
physical_gpu=2
action=${1:-}

usage() {
  printf 'usage: %s check HEALTH_TERMINAL HEALTH_TERMINAL_SHA256 | run HEALTH_TERMINAL HEALTH_TERMINAL_SHA256 OUTPUT_ROOT | compare OUTPUT_ROOT\n' "$0" >&2
  exit 2
}

case "$action" in
  check)
    [[ $# -eq 3 ]] || usage
    health_terminal=$2
    health_terminal_sha=$3
    output_root=
    ;;
  run)
    [[ $# -eq 4 ]] || usage
    health_terminal=$2
    health_terminal_sha=$3
    output_root=$4
    ;;
  compare)
    [[ $# -eq 2 ]] || usage
    health_terminal=
    health_terminal_sha=
    output_root=$2
    ;;
  *) usage ;;
esac

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 3
}

verify_sha() {
  local path=$1 expected=$2 label=$3 actual
  [[ -f "$path" && ! -L "$path" ]] || fail "$label is not a regular file: $path"
  [[ "$expected" =~ ^[0-9a-f]{64}$ ]] || fail "$label expected SHA-256 is malformed"
  actual=$(sha256sum -- "$path" | awk '{print $1}')
  [[ "$actual" == "$expected" ]] || \
    fail "$label SHA-256 mismatch: actual=$actual expected=$expected"
}

require_clean_repo() {
  [[ "$(git -C "$repo" branch --show-current)" == main ]] || fail 'requires main'
  [[ -z "$(git -C "$repo" status --porcelain --untracked-files=normal)" ]] || \
    fail 'requires a clean lab repository'
  [[ "$(git -C "$repo" rev-parse HEAD)" == \
    "$(git -C "$repo" rev-parse origin/main)" ]] || \
    fail 'requires local main == origin/main'
}

require_static_identity() {
  require_clean_repo
  [[ -x "$python" ]] || fail "missing XPU Python: $python"
  command -v jq >/dev/null || fail 'jq is required'
  command -v sha256sum >/dev/null || fail 'sha256sum is required'
  [[ "$stage" == "$(realpath -- "$stage")" ]] || fail 'stage is not canonical'
  [[ "$cache_root" == "$(realpath -- "$cache_root")" ]] || \
    fail 'compile-cache root is absent or not canonical'
  verify_sha "$operator" "$operator_sha" mtp-fc-int4-qualifier
  verify_sha "$health_supervisor" "$health_supervisor_sha" gpu3-health-supervisor
  verify_sha "$extension" "$extension_sha" pinned-xpu-extension
  verify_sha "$stage_manifest" "$stage_manifest_sha" composite-stage-graph-manifest
}

clean_python() {
  env -i \
    HOME=/home/steve \
    USER=steve \
    LOGNAME=steve \
    SHELL=/bin/bash \
    LANG=C.UTF-8 \
    PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
    PYTHONHASHSEED=0 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH="$stage" \
    LD_LIBRARY_PATH="$stage_package:$venv_lib:$torch_lib" \
    "$python" "$@"
}

validate_health_terminal() {
  local supplied_path=$1 supplied_sha=$2 health_root validation
  [[ "$supplied_path" == /* ]] || fail 'GPU3 health terminal path must be absolute'
  [[ "$supplied_sha" =~ ^[0-9a-f]{64}$ ]] || \
    fail 'GPU3 health terminal SHA-256 is malformed'
  [[ -f "$supplied_path" && ! -L "$supplied_path" ]] || \
    fail "GPU3 health terminal is not a regular file: $supplied_path"
  [[ "$supplied_path" == "$(realpath -- "$supplied_path")" ]] || \
    fail 'GPU3 health terminal path must be canonical'
  [[ "$(basename -- "$supplied_path")" == terminal.json ]] || \
    fail 'GPU3 health terminal basename must be terminal.json'
  [[ "$(stat -c '%a' -- "$supplied_path")" == 444 ]] || \
    fail 'GPU3 health terminal must have mode 0444'
  verify_sha "$supplied_path" "$supplied_sha" passing-gpu3-health-terminal
  health_root=$(dirname -- "$supplied_path")
  validation=$(clean_python "$health_supervisor" validate "$health_root") || \
    fail 'pinned supervisor rejected the GPU3 health terminal'
  jq -e \
    --arg terminal "$supplied_path" \
    '.passed == true and
     .classification == "gpu3-incumbent-control-health-pass" and
     .terminal == $terminal' <<<"$validation" >/dev/null || \
    fail 'pinned supervisor did not return the exact passing health identity'
}

discover_four_b70s() {
  local discovery b70_count device_count
  discovery=$(xpu-smi discovery 2>&1) || fail 'xpu-smi discovery failed'
  b70_count=$(grep -c 'Device Name: Intel(R) Arc(TM) Pro B70 Graphics' \
    <<<"$discovery" || true)
  device_count=$(grep -Ec '^\|[[:space:]]*[0-9]+[[:space:]]*\| Device Name:' \
    <<<"$discovery" || true)
  [[ "$b70_count" -eq 4 && "$device_count" -eq 4 ]] || \
    fail "expected exactly four B70 devices, found B70=$b70_count total=$device_count"
}

validate_packet() {
  local packet=$1 label=$2 expected_schema=$3 expected_pass=$4 validation
  [[ -f "$packet" && ! -L "$packet" ]] || fail "$label packet missing: $packet"
  [[ "$(stat -c '%a' -- "$packet")" == 444 ]] || \
    fail "$label packet must have mode 0444: $packet"
  validation=$(clean_python "$operator" validate --packet "$packet") || \
    fail "$label packet failed deep validation: $packet"
  jq -e --arg schema "$expected_schema" --arg pass "$expected_pass" \
    '.schema == $schema and
     (($pass == "absent" and (has("passed") | not)) or
      ($pass == "true" and .passed == true) or
      ($pass == "false" and .passed == false))' "$packet" >/dev/null || \
    fail "$label packet schema/pass mismatch: $packet"
  jq -e --arg schema "$expected_schema" \
    '.validated == true and .schema == $schema' <<<"$validation" >/dev/null || \
    fail "$label validator response mismatch: $packet"
}

require_output_root_outside_repo() {
  local canonical=$1
  [[ "$canonical" != "$repo" && "$canonical" != "$repo/"* ]] || \
    fail 'output root must be outside the lab repository'
}

require_output_root_absent() {
  local requested=$1 parent canonical
  [[ "$requested" == /* ]] || fail 'output root must be absolute'
  [[ ! -e "$requested" && ! -L "$requested" ]] || \
    fail "refusing existing output root: $requested"
  parent=$(dirname -- "$requested")
  [[ -d "$parent" && ! -L "$parent" ]] || \
    fail "output-root parent must be an existing non-symlink directory: $parent"
  canonical="$(realpath -- "$parent")/$(basename -- "$requested")"
  [[ "$requested" == "$canonical" ]] || fail 'output root must be canonical'
  require_output_root_outside_repo "$canonical"
}

require_arm_paths_absent() {
  local output=$1 stderr_log=$2 path
  for path in "$output" "$output.tmp" "$stderr_log" "$stderr_log.tmp"; do
    [[ ! -e "$path" && ! -L "$path" ]] || fail "refusing arm path collision: $path"
  done
}

# The only way to authorize execution is a reviewed source edit made together
# with a tracked preregistration.  Do not replace this with an env/CLI gate.
if [[ "$action" == run ]]; then
  fail 'LAUNCH BLOCKED: a future tracked preregistration must authorize Q1 and refreeze this driver before run is enabled'
fi

require_static_identity
repo_head=$(git -C "$repo" rev-parse HEAD)
driver_sha=$(sha256sum -- "$driver" | awk '{print $1}')

if [[ "$action" == check ]]; then
  validate_health_terminal "$health_terminal" "$health_terminal_sha"
  discover_four_b70s
  printf 'PASS: FC-INT4 operator static, four-B70, and passing-GPU3-health gates passed; launch remains blocked\n'
  exit 0
fi

if [[ "$action" == run ]]; then
  # Unreachable until the launch-block statement above is deliberately revised.
  validate_health_terminal "$health_terminal" "$health_terminal_sha"
  discover_four_b70s
  require_output_root_absent "$output_root"
  mkdir -m 0700 -- "$output_root"

  cache_packet="$output_root/cache-snapshot.json"
  preflight_packet="$output_root/preflight.json"
  clean_python "$operator" cache-snapshot \
    --output "$cache_packet" --root "$cache_root" >/dev/null
  validate_packet "$cache_packet" cache-snapshot qwen38-mtp-fc-int4-cache-snapshot-v1 absent
  cache_sha=$(sha256sum -- "$cache_packet" | awk '{print $1}')

  clean_python "$operator" preflight \
    --output "$preflight_packet" \
    --physical-gpu "$physical_gpu" \
    --script-sha256 "$operator_sha" \
    --driver "$driver" \
    --driver-sha256 "$driver_sha" \
    --repo-head "$repo_head" \
    --health-packet "$health_terminal" \
    --health-sha256 "$health_terminal_sha" \
    --cache-snapshot "$cache_packet" \
    --cache-sha256 "$cache_sha" >/dev/null
  validate_packet "$preflight_packet" preflight qwen38-mtp-fc-int4-preflight-v1 true
  preflight_sha=$(sha256sum -- "$preflight_packet" | awk '{print $1}')

  run_one() {
    local rank=$1 slot=$2 role=$3 suffix=$4 output stderr_log rc
    output="$output_root/rank${rank}-${slot}-${role}.json"
    stderr_log="$output_root/rank${rank}-${slot}-${role}.stderr.log"
    require_arm_paths_absent "$output" "$stderr_log"
    set +e
    env -i \
      HOME=/home/steve \
      USER=steve \
      LOGNAME=steve \
      SHELL=/bin/bash \
      LANG=C.UTF-8 \
      PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
      PYTHONHASHSEED=0 \
      PYTHONDONTWRITEBYTECODE=1 \
      PYTHONPATH="$stage" \
      LD_LIBRARY_PATH="$stage_package:$venv_lib:$torch_lib" \
      ZE_AFFINITY_MASK="$physical_gpu" \
      VLLM_XPU_ONEDNN_INT4_COMPLETION_BARRIER=1 \
      "$python" "$operator" run \
        --role "$role" \
        --tp-rank "$rank" \
        --physical-gpu "$physical_gpu" \
        --arm-id "rank${rank}-${suffix}" \
        --campaign-slot "$slot" \
        --preflight "$preflight_packet" \
        --preflight-sha256 "$preflight_sha" \
        --stderr-log "$stderr_log" \
        --output "$output" \
        --samples 40 \
        --launches-per-sample 100 \
        --stability-replays 32
    rc=$?
    set -e
    if [[ $rc -ne 0 ]]; then
      [[ -f "$output" ]] || \
        fail "rank${rank}-${suffix} failed rc=$rc before publishing a packet"
      [[ $rc -eq 3 ]] || \
        fail "rank${rank}-${suffix} returned unexpected rc=$rc"
      validate_packet "$output" "rank${rank}-${suffix}" \
        qwen38-mtp-fc-int4-operator-invalid-v1 false
      fail "rank${rank}-${suffix} failed rc=$rc; validated immutable failure packet preserved"
    fi
    [[ -f "$output" ]] || fail "rank${rank}-${suffix} omitted its success packet"
    validate_packet "$output" "rank${rank}-${suffix}" \
      qwen38-mtp-fc-int4-operator-run-v1 true
    [[ -f "$stderr_log" && "$(stat -c '%a' -- "$stderr_log")" == 444 ]] || \
      fail "rank${rank}-${suffix} omitted immutable stderr evidence"
    [[ ! -e "$output.tmp" && ! -L "$output.tmp" && \
      ! -e "$stderr_log.tmp" && ! -L "$stderr_log.tmp" ]] || \
      fail "rank${rank}-${suffix} left a temporary output"
  }

  # Exactly eight non-overlapping fresh processes: rank-0 ABBA, then rank-1 ABBA.
  for rank in 0 1; do
    run_one "$rank" 1 control a1
    run_one "$rank" 2 candidate b1
    run_one "$rank" 3 candidate b2
    run_one "$rank" 4 control a2
  done
  printf 'PASS: eight fresh-process FC-INT4 packets written; run compare separately\n'
  exit 0
fi

[[ -d "$output_root" && ! -L "$output_root" ]] || \
  fail "missing canonical output root: $output_root"
[[ "$output_root" == "$(realpath -- "$output_root")" ]] || \
  fail 'comparison output root is not canonical'
require_output_root_outside_repo "$output_root"
comparison="$output_root/comparison.json"
[[ ! -e "$comparison" && ! -L "$comparison" && \
  ! -e "$comparison.tmp" && ! -L "$comparison.tmp" ]] || \
  fail "refusing comparison output collision: $comparison"
packets=()
for rank in 0 1; do
  for spec in '1 control' '2 candidate' '3 candidate' '4 control'; do
    read -r slot role <<<"$spec"
    packet="$output_root/rank${rank}-${slot}-${role}.json"
    stderr_log="$output_root/rank${rank}-${slot}-${role}.stderr.log"
    validate_packet "$packet" "rank${rank}-${slot}-${role}" \
      qwen38-mtp-fc-int4-operator-run-v1 true
    jq -e \
      --arg qualifier_sha "$operator_sha" \
      --arg current_driver_sha "$driver_sha" \
      --arg current_repo_head "$repo_head" \
      '.preflight.qualifier_sha256 == $qualifier_sha and
       .preflight.driver_sha256 == $current_driver_sha and
       .preflight.lab_repo_head == $current_repo_head' "$packet" >/dev/null || \
      fail "run packet is not bound to the current qualifier/driver/repo: $packet"
    [[ -f "$stderr_log" && ! -L "$stderr_log" && \
      "$(stat -c '%a' -- "$stderr_log")" == 444 ]] || \
      fail "missing immutable stderr evidence: $stderr_log"
    [[ ! -e "$packet.tmp" && ! -L "$packet.tmp" && \
      ! -e "$stderr_log.tmp" && ! -L "$stderr_log.tmp" ]] || \
      fail "temporary arm artifact remains for rank${rank}-${slot}-${role}"
    packets+=("$packet")
  done
done

set +e
clean_python "$operator" compare --output "$comparison" "${packets[@]}"
compare_rc=$?
set -e
[[ -f "$comparison" ]] || fail "comparison failed rc=$compare_rc without a packet"
if [[ $compare_rc -eq 0 ]]; then
  validate_packet "$comparison" comparison \
    qwen38-mtp-fc-int4-operator-compare-v1 true
elif [[ $compare_rc -eq 14 ]]; then
  validate_packet "$comparison" comparison \
    qwen38-mtp-fc-int4-operator-compare-v1 false
  printf 'FAIL: comparison completed with validated terminal rc=%d: %s\n' \
    "$compare_rc" "$comparison" >&2
  exit "$compare_rc"
else
  fail "comparison returned unexpected rc=$compare_rc"
fi
printf 'PASS: FC-INT4 rank-local ABBA comparison passed: %s\n' "$comparison"
