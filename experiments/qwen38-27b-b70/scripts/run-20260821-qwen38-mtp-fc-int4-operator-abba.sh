#!/usr/bin/env bash
set -euo pipefail

# Fresh-process, isolated eager mtp.fc BF16-vs-W4A16 operator screen.
# Q1 authorized 2026-08-22 by the tracked preregistration committed with
# this revision: the GPU3 health r2 pass terminal is source-pinned below
# (never a caller input), every arm runs under a bounded process-group
# watchdog with immutable receipts, GPU2's live BDF/UUID is rederived and
# bound, and an enclosing campaign terminal records the outcome.

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
operator_sha=5aff20b03aa520b76d8a204003416831cb5318c47df4aa794533844c2dd591b9
health_supervisor_sha=eb619535786a3c7a8929b2d3b1c3848486d3edc1b96804c79831eaf8c3923375
extension_sha=4dd336013d155aab004fb1c916118957cb9349b491938da65769f2d8af18ffb0
stage_manifest_sha=47861e8391b6b25dd9c3eb25e25c5939753aa470858b667d5bdf181344db18da
physical_gpu=2
# xpu-smi discovery -j reports the BDF-encoded UUID form; the level-zero form
# (868023e2-0000-0000-4300-000000000000) is separately enforced inside the
# worker by the qualifier. Both encode physical GPU2 at 0000:43:00.0.
expected_gpu2_uuid=00000000-0000-0043-0000-0000e2238086
expected_gpu2_bdf=0000:43:00.0
# Source-pinned same-boot GPU3 health authorization (Q1). Never a caller input.
health_terminal=/home/steve/qwen38-gpu3-incumbent-control-health-20260821-r2/terminal.json
health_terminal_sha=7c04155e969dbbc97b00268fe7bcbefda0b232feabdd47db817d26aa5a631ae2
health_boot_id=256bc838-c015-4c91-a8f9-363d281f7555
arm_deadline_seconds=900
action=${1:-}

usage() {
  printf 'usage: %s check | run OUTPUT_ROOT | compare OUTPUT_ROOT\n' "$0" >&2
  exit 2
}

case "$action" in
  check)
    [[ $# -eq 1 ]] || usage
    output_root=
    ;;
  run)
    [[ $# -eq 2 ]] || usage
    output_root=$2
    ;;
  compare)
    [[ $# -eq 2 ]] || usage
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

gpu2_live_bdf=
discover_four_b70s() {
  local discovery_json b70_count gpu2_uuid
  discovery_json=$(/usr/bin/xpu-smi discovery -j 2>/dev/null) || \
    fail 'xpu-smi discovery -j failed'
  b70_count=$(jq -r \
    '[.device_list[] | select(.device_name | contains("B70"))] | length' \
    <<<"$discovery_json") || fail 'discovery JSON is unparseable'
  [[ "$b70_count" == 4 ]] || \
    fail "expected exactly four B70 devices, found $b70_count"
  gpu2_uuid=$(jq -r --argjson id "$physical_gpu" \
    '.device_list[] | select(.device_id == $id) | .uuid' <<<"$discovery_json")
  [[ "$gpu2_uuid" == "$expected_gpu2_uuid" ]] || \
    fail "GPU$physical_gpu UUID $gpu2_uuid is not the expected $expected_gpu2_uuid"
  gpu2_live_bdf=$(jq -r --argjson id "$physical_gpu" \
    '.device_list[] | select(.device_id == $id) | .pci_bdf_address' \
    <<<"$discovery_json")
  [[ "$gpu2_live_bdf" =~ ^[0-9a-f]{4}:[0-9a-f]{2}:[0-9a-f]{2}\.[0-9a-f]$ ]] || \
    fail "GPU$physical_gpu live BDF is malformed: $gpu2_live_bdf"
  [[ "$gpu2_live_bdf" == "$expected_gpu2_bdf" ]] || \
    fail "GPU$physical_gpu live BDF $gpu2_live_bdf is not the expected $expected_gpu2_bdf"
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

# Q1 launch authorization is a reviewed source property of this exact file
# revision plus the source-pinned health terminal above; there is still no
# env/CLI gate. Same-boot binding is enforced before any run.
require_same_boot() {
  local current
  current=$(cat /proc/sys/kernel/random/boot_id)
  [[ "$current" == "$health_boot_id" ]] || \
    fail "host boot $current is not the authorized GPU3-health boot $health_boot_id"
}

require_static_identity
repo_head=$(git -C "$repo" rev-parse HEAD)
driver_sha=$(sha256sum -- "$driver" | awk '{print $1}')

if [[ "$action" == check ]]; then
  require_same_boot
  validate_health_terminal "$health_terminal" "$health_terminal_sha"
  discover_four_b70s
  printf 'PASS: FC-INT4 operator static, four-B70, passing-GPU3-health, and same-boot gates passed; Q1 run is authorized by this revision\n'
  exit 0
fi

if [[ "$action" == run ]]; then
  require_same_boot
  validate_health_terminal "$health_terminal" "$health_terminal_sha"
  discover_four_b70s
  require_output_root_absent "$output_root"
  mkdir -m 0700 -- "$output_root"

  arm_inventory=()
  active_arm_pgid=
  active_arm_id=

  publish_receipt() {
    local path=$1 tmp="$1.tmp"
    cat > "$tmp"
    jq -e . "$tmp" >/dev/null || fail "malformed receipt JSON for $path"
    chmod 0444 -- "$tmp"
    mv -- "$tmp" "$path"
  }

  write_campaign_terminal() {
    local outcome=$1 note=$2 terminal="$output_root/campaign-terminal.json" inv
    [[ ! -e "$terminal" ]] || return 0
    if [[ ${#arm_inventory[@]} -gt 0 ]]; then
      inv=$(printf '%s\n' "${arm_inventory[@]}" | jq -R . | jq -s .)
    else
      inv='[]'
    fi
    jq -n \
      --arg schema qwen38-mtp-fc-int4-campaign-terminal-v1 \
      --arg outcome "$outcome" --arg note "$note" \
      --arg boot "$health_boot_id" \
      --arg health "$health_terminal" --arg health_sha "$health_terminal_sha" \
      --arg gpu2_bdf "$gpu2_live_bdf" --arg gpu2_uuid "$expected_gpu2_uuid" \
      --arg driver_sha "$driver_sha" --arg operator_sha "$operator_sha" \
      --arg repo_head "$repo_head" --argjson arms "$inv" \
      '{schema:$schema, outcome:$outcome, note:$note, boot_id:$boot,
        health_terminal:$health, health_terminal_sha256:$health_sha,
        gpu2_live_bdf:$gpu2_bdf, gpu2_uuid:$gpu2_uuid,
        driver_sha256:$driver_sha, qualifier_sha256:$operator_sha,
        lab_repo_head:$repo_head, arms:$arms}' | publish_receipt "$terminal"
  }

  run_fail() {
    write_campaign_terminal failed "$*" || true
    fail "$@"
  }

  kill_active_group() {
    local pgid=$1
    kill -s TERM -- "-$pgid" 2>/dev/null || true
    sleep 5
    if kill -0 -- "-$pgid" 2>/dev/null; then
      kill -s KILL -- "-$pgid" 2>/dev/null || true
      sleep 5
    fi
    ! kill -0 -- "-$pgid" 2>/dev/null
  }

  on_run_signal() {
    trap '' INT TERM
    if [[ -n "$active_arm_pgid" ]]; then
      kill_active_group "$active_arm_pgid" || true
    fi
    write_campaign_terminal interrupted "signal during ${active_arm_id:-pre-arm}" || true
    exit 130
  }
  trap 'on_run_signal' INT TERM

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
    local rank=$1 slot=$2 role=$3 suffix=$4 arm_id output stderr_log rc pid
    local receipt_base waited
    arm_id="rank${rank}-${suffix}"
    output="$output_root/rank${rank}-${slot}-${role}.json"
    stderr_log="$output_root/rank${rank}-${slot}-${role}.stderr.log"
    receipt_base="$output_root/rank${rank}-${slot}-${role}"
    require_arm_paths_absent "$output" "$stderr_log"
    jq -n --arg arm "$arm_id" --arg role "$role" --argjson slot "$slot" \
      --argjson time_ns "$(date +%s%N)" \
      '{schema:"qwen38-mtp-fc-int4-arm-receipt-v1", phase:"before-spawn",
        arm:$arm, role:$role, slot:$slot, time_ns:$time_ns}' | \
      publish_receipt "$receipt_base.before-spawn.json"
    setsid env -i \
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
        --arm-id "$arm_id" \
        --campaign-slot "$slot" \
        --preflight "$preflight_packet" \
        --preflight-sha256 "$preflight_sha" \
        --stderr-log "$stderr_log" \
        --output "$output" \
        --samples 40 \
        --launches-per-sample 100 \
        --stability-replays 32 &
    pid=$!
    active_arm_pgid=$pid
    active_arm_id=$arm_id
    jq -n --arg arm "$arm_id" --argjson pid "$pid" \
      --argjson deadline "$arm_deadline_seconds" \
      --argjson time_ns "$(date +%s%N)" \
      '{schema:"qwen38-mtp-fc-int4-arm-receipt-v1", phase:"spawned",
        arm:$arm, pid:$pid, pgid:$pid, deadline_seconds:$deadline,
        time_ns:$time_ns}' | \
      publish_receipt "$receipt_base.spawned.json"
    waited=0
    while kill -0 "$pid" 2>/dev/null && (( waited < arm_deadline_seconds )); do
      sleep 1
      waited=$((waited + 1))
    done
    if kill -0 "$pid" 2>/dev/null; then
      jq -n --arg arm "$arm_id" --argjson waited "$waited" \
        --argjson time_ns "$(date +%s%N)" \
        '{schema:"qwen38-mtp-fc-int4-arm-receipt-v1", phase:"timeout-before-term",
          arm:$arm, waited_seconds:$waited, time_ns:$time_ns}' | \
        publish_receipt "$receipt_base.timeout.json"
      kill_active_group "$pid" || \
        run_fail "$arm_id timed out and its process group is unkillable"
      active_arm_pgid=
      run_fail "$arm_id exceeded the ${arm_deadline_seconds}s watchdog deadline; group terminated and verified absent"
    fi
    set +e
    wait "$pid"
    rc=$?
    set -e
    if kill -0 -- "-$pid" 2>/dev/null; then
      kill_active_group "$pid" || \
        run_fail "$arm_id left an unkillable descendant group"
      run_fail "$arm_id leader exited but left live descendants; group terminated"
    fi
    active_arm_pgid=
    active_arm_id=
    if [[ $rc -ne 0 ]]; then
      [[ -f "$output" ]] || \
        run_fail "$arm_id failed rc=$rc before publishing a packet"
      [[ $rc -eq 3 ]] || \
        run_fail "$arm_id returned unexpected rc=$rc"
      validate_packet "$output" "$arm_id" \
        qwen38-mtp-fc-int4-operator-invalid-v1 false
      run_fail "$arm_id failed rc=$rc; validated immutable failure packet preserved"
    fi
    [[ -f "$output" ]] || run_fail "$arm_id omitted its success packet"
    validate_packet "$output" "$arm_id" \
      qwen38-mtp-fc-int4-operator-run-v1 true
    [[ -f "$stderr_log" && "$(stat -c '%a' -- "$stderr_log")" == 444 ]] || \
      run_fail "$arm_id omitted immutable stderr evidence"
    [[ ! -e "$output.tmp" && ! -L "$output.tmp" && \
      ! -e "$stderr_log.tmp" && ! -L "$stderr_log.tmp" ]] || \
      run_fail "$arm_id left a temporary output"
    arm_inventory+=("$arm_id:$(sha256sum -- "$output" | awk '{print $1}'):$(sha256sum -- "$stderr_log" | awk '{print $1}')")
  }

  # Exactly eight non-overlapping fresh sessions: rank-0 ABBA, then rank-1 ABBA.
  for rank in 0 1; do
    run_one "$rank" 1 control a1
    run_one "$rank" 2 candidate b1
    run_one "$rank" 3 candidate b2
    run_one "$rank" 4 control a2
  done
  trap - INT TERM
  write_campaign_terminal complete 'eight validated packets; run compare separately'
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
