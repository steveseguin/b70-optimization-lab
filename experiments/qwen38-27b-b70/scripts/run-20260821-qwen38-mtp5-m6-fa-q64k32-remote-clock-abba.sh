#!/usr/bin/bash
set -euo pipefail

# Source-only preregistered remote campaign.  Stable passive host/telemetry
# values are frozen below, but launch and clock-writer gates remain false.

repo=/home/steve/b70-optimization-lab
host=steve-TURIND8-2L2T
python=/home/steve/.venvs/vllm-xpu/bin/python
venv_lib=/home/steve/.venvs/vllm-xpu/lib
torch_lib=/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/lib
campaign=$repo/experiments/qwen38-27b-b70/scripts/qwen38_mtp5_m6_fa_q64k32_remote_clock_campaign.py
qualifier=$repo/experiments/qwen38-27b-b70/scripts/qwen38_mtp5_m6_fa_q64k32_operator.py
base_qualifier=$repo/experiments/qwen38-27b-b70/scripts/qwen38_mtp5_m6_fa_operator.py
preparer=$repo/experiments/qwen38-27b-b70/scripts/prepare-qwen38-m6-head256-q64k32-remote-stage-20260821.sh
control=/home/steve/staged-xpu-commitfix-graphfa-composite-20260820
candidate_root=/home/steve/qwen38-m6-head256-q64k32-attn-override-20260821-r2
candidate=$candidate_root/runtime
candidate_manifest=$candidate_root/qwen38-m6-head256-q64k32-r2-candidate-stage.json
result=/home/steve/qwen38-mtp5-m6-fa-q64k32-remote-clock-abba-20260821-r1

campaign_sha=7577f9313b60d4bb51b328eb63608ab8c3bf9af31b1e84e1390164f71ee1e2fb
preparer_sha=c3a99abb5bd401b1e6d14ad5576f7493ec7dd9e5b106e3d03892d04dcd9ae6d9
qualifier_sha=31862ea6a8b9e11a59d643e0d3500179d938261e62b93fb920439c664ce21fbc
base_qualifier_sha=0dd7b945ef35a11ff4d0a1ec085e604920524b996d539e089d89b4a019a5de1f
authorized_repo_head=REMOTE_REPO_HEAD_TO_FREEZE
authorized_stage_json_sha=REMOTE_STAGE_JSON_SHA256_TO_FREEZE
authorized_device0_uuid=00000000-0000-0003-0000-0000e2238086
authorized_device0_bdf=0000:03:00.0
authorized_device1_uuid=00000000-0000-00e3-0000-0000e2238086
authorized_device1_bdf=0000:e3:00.0
authorized_xpu_smi_schema_sha=afb4b7fe6d1ea9847559734fae1b73241f18587f036ae3d18376c146fa6eafba
authorized_xpu_smi_sha=01c7b83881e99754642b827ba05418d263aed615933e3df35821af7733eb8d83
authorized_xpu_smi_version=$'CLI:\n  Version: 2.0.0.20250225\n  Build ID: 8389eee7\n\nService:\n  Version: 2.0.0.20250225\n  Build ID: 8389eee7\n  Level Zero Version: 1.28.6'
authorized_system_runtime_inventory_sha=REMOTE_SYSTEM_RUNTIME_INVENTORY_SHA256_TO_FREEZE
xpu_smi=/usr/bin/xpu-smi
launch_authorized=false
driver_signal_ownership_authorized=true
clock_writer_exclusion_authorized=false
driver_environment_authorized=true

# Every management executable is addressed by an absolute source-pinned path.
# xpu-smi additionally has frozen bytes/version above; the remaining tool-byte
# inventory is still part of the overall false launch gate review.
bash_bin=/usr/bin/bash
env_bin=/usr/bin/env
git_bin=/usr/bin/git
hostname_bin=/usr/bin/hostname
realpath_bin=/usr/bin/realpath
sha256sum_bin=/usr/bin/sha256sum
awk_bin=/usr/bin/awk
jq_bin=/usr/bin/jq
timeout_bin=/usr/bin/timeout
sudo_bin=/usr/bin/sudo
chmod_bin=/usr/bin/chmod
mv_bin=/usr/bin/mv
rm_bin=/usr/bin/rm
mkdir_bin=/usr/bin/mkdir
seq_bin=/usr/bin/seq
sleep_bin=/usr/bin/sleep
kill_bin=/usr/bin/kill
true_bin=/usr/bin/true
clean_path=/usr/bin:/bin
clean_marker=remote-q64k32-management-v1

die() { printf 'error: %s\n' "$*" >&2; exit 2; }
verify() {
  local path=$1 expected=$2 actual
  [[ -f $path ]] || die "missing: $path"
  [[ $expected =~ ^[0-9a-f]{64}$ ]] || die "unfrozen SHA for $path"
  actual=$("$sha256sum_bin" -- "$path" | "$awk_bin" '{print $1}')
  [[ $actual == "$expected" ]] || die "SHA mismatch: $path"
}
usage() {
  printf 'usage: %s audit | run | compare\n' "$0" >&2
  exit 2
}

action=${1:-}
[[ $# -eq 1 ]] || usage
[[ $action == audit || $action == run || $action == compare ]] || usage

if [[ $action == run ]]; then
  # First operation: no directory, sudo, clock, XPU, or subprocess mutation may
  # precede this source-only authorization gate.
  [[ $launch_authorized == true && $driver_signal_ownership_authorized == true && \
     $clock_writer_exclusion_authorized == true && $driver_environment_authorized == true ]] || die \
    'launch blocked pending identity, supervisor ownership, clock-writer exclusion, and clean-env gates'
fi

# Audit, compare, and the future authorized run all re-exec before any host,
# Git, Python, xpu-smi, sudo, filesystem, or GPU-facing operation.  The marker
# is accepted only when the complete exported-name inventory and every value
# match the child contract and no exported Bash function exists.  Subsequent
# management subprocesses use exact paths or a second env -i boundary.
if [[ ${QWEN38_REMOTE_DRIVER_CLEAN:-} != "$clean_marker" ]]; then
  case $0 in
    /*) clean_driver=$0 ;;
    *) clean_driver=$PWD/$0 ;;
  esac
  cd -- /home/steve || die 'cannot enter canonical management working directory'
  exec "$env_bin" -i \
    HOME=/home/steve USER=steve LOGNAME=steve SHELL="$bash_bin" LANG=C.UTF-8 \
    PATH="$clean_path" PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 \
    QWEN38_REMOTE_DRIVER_CLEAN="$clean_marker" \
    "$bash_bin" "$clean_driver" "$@"
fi
[[ $PATH == "$clean_path" && $PWD == /home/steve && $HOME == /home/steve && $USER == steve && \
   $LOGNAME == steve && $SHELL == "$bash_bin" && \
   $LANG == C.UTF-8 && $SHLVL == 1 && \
   ${PYTHONHASHSEED:-} == 0 && ${PYTHONDONTWRITEBYTECODE:-} == 1 && \
   $QWEN38_REMOTE_DRIVER_CLEAN == "$clean_marker" ]] || \
  die 'management clean-environment identity differs'
mapfile -t exported_environment_names < <(compgen -e)
for exported_name in "${exported_environment_names[@]}"; do
  case $exported_name in
    HOME|LANG|LOGNAME|PATH|PWD|PYTHONDONTWRITEBYTECODE|PYTHONHASHSEED|QWEN38_REMOTE_DRIVER_CLEAN|SHELL|SHLVL|USER) ;;
    *) die "unexpected exported management environment: $exported_name" ;;
  esac
done
[[ ${#exported_environment_names[@]} -eq 11 ]] || \
  die 'exported management environment inventory differs'
[[ -z $(declare -Fx) ]] || die 'exported Bash function reached management shell'

management_python() {
  "$env_bin" -i \
    HOME=/home/steve USER=steve LOGNAME=steve SHELL="$bash_bin" LANG=C.UTF-8 \
    PATH="$clean_path" PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 \
    QWEN38_REMOTE_DRIVER_CLEAN="$clean_marker" \
    "$python" -B "$campaign" "$@"
}

[[ $("$hostname_bin") == "$host" ]] || die "requires $host"
[[ $("$realpath_bin" -e -- "$repo") == "$repo" ]] || die 'repo path is absent/noncanonical'
[[ $("$git_bin" -C "$repo" branch --show-current) == main ]] || die 'requires main'
[[ -z $("$git_bin" -C "$repo" status --porcelain --untracked-files=normal) ]] || die 'requires clean repo'
repo_head=$("$git_bin" -C "$repo" rev-parse HEAD)
[[ $repo_head == "$authorized_repo_head" ]] || die 'remote repository HEAD is not frozen identity'
[[ $repo_head == $("$git_bin" -C "$repo" rev-parse origin/main) ]] || die 'requires main == origin/main'
verify "$campaign" "$campaign_sha"
verify "$preparer" "$preparer_sha"
verify "$qualifier" "$qualifier_sha"
verify "$base_qualifier" "$base_qualifier_sha"
verify "$candidate_manifest" "$authorized_stage_json_sha"
[[ -x $python ]] || die 'XPU Python is absent'

if [[ $action == audit ]]; then
  management_python audit --repo "$repo" --require-host --require-stages
  exit
fi

# Stable passive values are frozen.  Repo/stage/runtime values remain explicit
# placeholders, and every boot-dynamic device/range/service fact is rechecked.
for frozen in \
  "$authorized_device0_uuid" "$authorized_device0_bdf" \
  "$authorized_device1_uuid" "$authorized_device1_bdf" \
  "$authorized_xpu_smi_schema_sha" \
  "$authorized_xpu_smi_sha" "$authorized_xpu_smi_version" \
  "$authorized_system_runtime_inventory_sha"; do
  [[ $frozen != *_TO_FREEZE ]] || die 'device/telemetry identity is not frozen'
done
verify "$xpu_smi" "$authorized_xpu_smi_sha"
[[ $("$realpath_bin" -e -- "$xpu_smi") == "$xpu_smi" ]] || \
  die 'xpu-smi path is not canonical'
[[ $("$env_bin" -i PATH="$clean_path" ZES_ENABLE_SYSMAN=1 \
      "$xpu_smi" --version) == "$authorized_xpu_smi_version" ]] || \
  die 'xpu-smi version differs from frozen identity'
audit_json=$(management_python audit --repo "$repo" --require-host --require-stages)
[[ $("$jq_bin" -er '.authorized_system_runtime_inventory_sha256' <<<"$audit_json") == \
   "$authorized_system_runtime_inventory_sha" ]] || \
  die 'driver/source system-runtime inventory binding differs'
[[ $("$jq_bin" -er '.authorized_xpu_smi.path' <<<"$audit_json") == "$xpu_smi" && \
   $("$jq_bin" -er '.authorized_xpu_smi.sha256' <<<"$audit_json") == "$authorized_xpu_smi_sha" && \
   $("$jq_bin" -er '.authorized_xpu_smi.version' <<<"$audit_json") == "$authorized_xpu_smi_version" ]] || \
  die 'driver/source xpu-smi identity binding differs'

if [[ $action == compare ]]; then
  [[ -d $result ]] || die "missing result root: $result"
  terminals=()
  for ordinal in $("$seq_bin" 1 16); do
    terminals+=("$result/arm-$(printf '%02d' "$ordinal").terminal.json")
  done
  default_packets=(
    "$result/arm-01.json" "$result/arm-02.json" "$result/arm-03.json" "$result/arm-04.json"
    "$result/arm-13.json" "$result/arm-14.json" "$result/arm-15.json" "$result/arm-16.json"
  )
  fixed_packets=(
    "$result/arm-09.json" "$result/arm-10.json" "$result/arm-11.json" "$result/arm-12.json"
    "$result/arm-05.json" "$result/arm-06.json" "$result/arm-07.json" "$result/arm-08.json"
  )
  block_boundary_receipts=(
    "$result/clock-1-block-1-inactive-pre.json"
    "$result/clock-0-block-1-active-post.json"
    "$result/clock-1-block-1-inactive-post.json"
    "$result/clock-0-block-2-inactive-pre.json"
    "$result/clock-1-block-2-active-post.json"
    "$result/clock-0-block-2-inactive-post.json"
    "$result/clock-1-block-3-inactive-pre.json"
    "$result/clock-0-block-3-active-post.json"
    "$result/clock-1-block-3-inactive-post.json"
    "$result/clock-0-block-4-inactive-pre.json"
    "$result/clock-1-block-4-active-post.json"
    "$result/clock-0-block-4-inactive-post.json"
  )
  arm_post_receipts=()
  for ordinal in $("$seq_bin" 1 16); do
    if [[ $ordinal -le 4 || ( $ordinal -ge 9 && $ordinal -le 12 ) ]]; then
      device=0
    else
      device=1
    fi
    arm_post_receipts+=("$result/clock-${device}-arm-${ordinal}-post.json")
  done
  set +e
  management_python compare-operator --repo "$repo" --clock-state default \
    --output "$result/default-clock-operator-comparison.json" "${default_packets[@]}"
  default_rc=$?
  management_python compare-operator --repo "$repo" --clock-state fixed \
    --output "$result/fixed-clock-operator-comparison.json" "${fixed_packets[@]}"
  fixed_rc=$?
  management_python compare-terminals \
    --output "$result/campaign-comparison.json" \
    --restoration-terminal "$result/campaign-restoration-terminal.json" \
    --default-operator-comparison "$result/default-clock-operator-comparison.json" \
    --fixed-operator-comparison "$result/fixed-clock-operator-comparison.json" \
    --block-boundary-receipts "${block_boundary_receipts[@]}" \
    --arm-post-receipts "${arm_post_receipts[@]}" \
    "${terminals[@]}"
  campaign_rc=$?
  set -e
  [[ $default_rc -eq 0 || $default_rc -eq 14 ]] && \
    [[ $fixed_rc -eq 0 || $fixed_rc -eq 14 ]] || \
    die "operator comparison infrastructure failed: default=$default_rc fixed=$fixed_rc"
  [[ $campaign_rc -eq 0 || $campaign_rc -eq 14 ]] || \
    die "campaign comparison infrastructure failed: rc=$campaign_rc"
  [[ $campaign_rc -eq 0 ]] || exit 14
  printf 'PASS: remote-only comparisons written; absolute local timing pooling remains forbidden\n'
  exit 0
fi

[[ ! -e $result ]] || die "refusing existing result root: $result"
[[ -x $xpu_smi ]] || die 'xpu-smi is absent'
[[ -x $timeout_bin && -x $sudo_bin && -x $env_bin ]] || die 'pinned management tool is absent'
"$sudo_bin" -n "$true_bin" >/dev/null 2>&1 || die 'noninteractive sudo prerequisite is not satisfied'

# Future telemetry parser must validate exact ID->UUID/BDF and effective min/max
# from these JSON receipts before the source launch gate may be enabled.
clock_receipt() {
  local device=$1 label=$2 output="$result/clock-${device}-${label}.json"
  local config_tmp="$result/.clock-${device}-${label}.config.tmp.json"
  local discovery_tmp="$result/.clock-${device}-${label}.discovery.tmp.json"
  [[ ! -e $output ]] || die "clock receipt collision: $output"
  [[ ! -e $config_tmp && ! -e $discovery_tmp ]] || \
    die "clock raw-receipt collision for GPU$device/$label"
  "$timeout_bin" -k 5s 30s "$env_bin" -i PATH="$clean_path" \
    ZES_ENABLE_SYSMAN=1 "$xpu_smi" config -d "$device" -t 0 -j >"$config_tmp"
  "$timeout_bin" -k 5s 30s "$env_bin" -i PATH="$clean_path" \
    ZES_ENABLE_SYSMAN=1 "$xpu_smi" discovery -j >"$discovery_tmp"
  management_python seal-clock-receipt --device "$device" \
    --config "$config_tmp" --discovery "$discovery_tmp" --output "$output" \
    >/dev/null
  "$rm_bin" -- "$config_tmp" "$discovery_tmp"
}
parse_range() {
  local device=$1 receipt=$2 parsed minimum maximum uuid bdf schema expected_uuid expected_bdf
  parsed=$(management_python parse-clock-receipt --device "$device" "$receipt")
  minimum=$("$jq_bin" -er '.min_mhz | select(type == "number" and floor == .)' <<<"$parsed") || \
    die 'parsed minimum clock is absent/nonintegral'
  maximum=$("$jq_bin" -er '.max_mhz | select(type == "number" and floor == .)' <<<"$parsed") || \
    die 'parsed maximum clock is absent/nonintegral'
  uuid=$("$jq_bin" -er '.uuid | select(type == "string" and length > 0)' <<<"$parsed") || \
    die 'parsed UUID is absent'
  bdf=$("$jq_bin" -er '.bdf | select(type == "string" and length > 0)' <<<"$parsed") || \
    die 'parsed BDF is absent'
  schema=$("$jq_bin" -er '.schema_sha256 | select(type == "string")' <<<"$parsed") || \
    die 'parsed telemetry schema is absent'
  if [[ $device -eq 0 ]]; then
    expected_uuid=$authorized_device0_uuid; expected_bdf=$authorized_device0_bdf
  else
    expected_uuid=$authorized_device1_uuid; expected_bdf=$authorized_device1_bdf
  fi
  [[ $uuid == "$expected_uuid" && $bdf == "$expected_bdf" ]] || \
    die "parsed GPU$device UUID/BDF differs from driver identity"
  [[ $schema == "$authorized_xpu_smi_schema_sha" ]] || \
    die 'parsed xpu-smi schema differs from driver identity'
  printf '%s,%s\n' "$minimum" "$maximum"
}
set_clock() {
  local device=$1 range=$2 label=$3 effective_receipt effective
  "$timeout_bin" -k 5s 30s "$sudo_bin" -n "$env_bin" -i PATH="$clean_path" \
    ZES_ENABLE_SYSMAN=1 "$xpu_smi" config -d "$device" -t 0 --frequencyrange "$range" -j \
    >"$result/clock-${device}-${label}-set.json.tmp"
  "$chmod_bin" 0444 "$result/clock-${device}-${label}-set.json.tmp"
  "$mv_bin" -- "$result/clock-${device}-${label}-set.json.tmp" \
    "$result/clock-${device}-${label}-set.json"
  clock_receipt "$device" "$label-effective"
  effective_receipt="$result/clock-${device}-${label}-effective.json"
  effective=$(parse_range "$device" "$effective_receipt")
  [[ $effective == "$range" ]] || \
    die "effective clock differs for GPU$device: $effective != $range"
}

"$mkdir_bin" -- "$result"
arm_terminals=()
for arm_ordinal in $("$seq_bin" 1 16); do
  arm_terminals+=("$result/arm-$(printf '%02d' "$arm_ordinal").terminal.json")
done
declare -a original_ranges
# Capture and parse both persistent-service ranges before changing either card.
# The exit trap restores these exact dynamic values, not an assumed default.
clock_receipt 0 pre-run
original_ranges[0]=$(parse_range 0 "$result/clock-0-pre-run.json")
clock_receipt 1 pre-run
original_ranges[1]=$(parse_range 1 "$result/clock-1-pre-run.json")
restore_rc=0
cleanup_state=idle
active_supervisor_pid=
active_supervisor_terminal=
active_forward_signal=TERM
supervisor_spawn_state=idle
deferred_signal=
deferred_exit_code=

quiesce_active_supervisor() {
  local counter=0 supervisor_rc=0
  [[ -n $active_supervisor_pid ]] || return 0
  if "$kill_bin" -0 "$active_supervisor_pid" 2>/dev/null; then
    "$kill_bin" -s "$active_forward_signal" "$active_supervisor_pid" 2>/dev/null || true
    while "$kill_bin" -0 "$active_supervisor_pid" 2>/dev/null && [[ $counter -lt 600 ]]; do
      "$sleep_bin" 0.05
      counter=$((counter + 1))
    done
  fi
  if "$kill_bin" -0 "$active_supervisor_pid" 2>/dev/null; then
    printf 'FATAL: active supervisor did not quiesce; clock restoration is forbidden\n' >&2
    return 1
  fi
  set +e
  wait "$active_supervisor_pid"
  supervisor_rc=$?
  set -e
  if ! management_python validate-cleanup-terminal "$active_supervisor_terminal" >/dev/null; then
    printf 'FATAL: active supervisor terminal does not prove worker-group absence (rc=%s)\n' \
      "$supervisor_rc" >&2
    return 1
  fi
  active_supervisor_pid=
  active_supervisor_terminal=
  return 0
}

restore_pre_run_ranges() {
  local original_rc=$1
  local terminal_rc
  [[ $cleanup_state == idle ]] || return
  cleanup_state=quiescing
  # Repeated signals cannot recurse into restoration.  The first signal is
  # forwarded to the owned supervisor; subsequent signals are held harmless
  # while cleanup and exact restoration complete.
  trap '' EXIT INT TERM HUP
  if ! quiesce_active_supervisor; then
    printf 'FATAL: refusing clock restoration while supervisor/worker absence is unproved\n' >&2
    exit 99
  fi
  cleanup_state=restoring
  set +e
  restore_all_devices
  restore_rc=$?
  set -e
  [[ $restore_rc -eq 0 ]] || printf 'FATAL: exact pre-run clock restoration was not proved\n' >&2
  set +e
  management_python seal-restoration \
    --output "$result/campaign-restoration-terminal.json" \
    --original-exit-code "$original_rc" --restore-rc "$restore_rc" \
    --pre-run-0 "$result/clock-0-pre-run.json" \
    --pre-run-1 "$result/clock-1-pre-run.json" \
    --restored-0 "$result/clock-0-restore-effective.json" \
    --restored-1 "$result/clock-1-restore-effective.json" \
    "${arm_terminals[@]}"
  terminal_rc=$?
  set -e
  [[ $terminal_rc -eq 0 ]] || printf 'FATAL: restoration terminal was not successful\n' >&2
  if [[ $restore_rc -ne 0 ]]; then exit 97; fi
  if [[ $terminal_rc -ne 0 ]]; then exit 98; fi
  exit "$original_rc"
}

restore_one_device() {
  local device=$1 set_tmp="$result/clock-${device}-restore-set.json.tmp"
  local set_output="$result/clock-${device}-restore-set.json" restored_range
  if ! "$timeout_bin" -k 5s 30s "$sudo_bin" -n "$env_bin" -i PATH="$clean_path" \
    ZES_ENABLE_SYSMAN=1 "$xpu_smi" config -d "$device" -t 0 \
    --frequencyrange "${original_ranges[$device]}" -j >"$set_tmp"; then
    "$rm_bin" -f -- "$set_tmp" 2>/dev/null || true
    return 1
  fi
  if ! "$chmod_bin" 0444 "$set_tmp" || ! "$mv_bin" -- "$set_tmp" "$set_output"; then
    "$rm_bin" -f -- "$set_tmp" 2>/dev/null || true
    return 1
  fi
  if ! (clock_receipt "$device" restore-effective); then
    return 1
  fi
  if ! restored_range=$(parse_range "$device" "$result/clock-${device}-restore-effective.json"); then
    return 1
  fi
  [[ $restored_range == "${original_ranges[$device]}" ]]
}

restore_all_devices() {
  local device aggregate_rc=0
  for device in 0 1; do
    restore_one_device "$device" || aggregate_rc=1
  done
  return "$aggregate_rc"
}

handle_driver_signal() {
  local signal_name=$1 exit_code=$2
  active_forward_signal=$signal_name
  if [[ $supervisor_spawn_state == spawning ]]; then
    deferred_signal=$signal_name
    deferred_exit_code=$exit_code
    return 0
  fi
  restore_pre_run_ranges "$exit_code"
}

claim_active_supervisor() {
  local supervisor_pid=$1
  [[ $supervisor_spawn_state == spawning && -n $supervisor_pid ]] || \
    die 'supervisor ownership publication state differs'
  active_supervisor_pid=$supervisor_pid
  supervisor_spawn_state=owned
  if [[ -n $deferred_signal ]]; then
    active_forward_signal=$deferred_signal
    restore_pre_run_ranges "$deferred_exit_code"
  fi
}

trap 'exit_rc=$?; active_forward_signal=TERM; restore_pre_run_ranges "$exit_rc"' EXIT
trap 'handle_driver_signal INT 130' INT
trap 'handle_driver_signal TERM 143' TERM
trap 'handle_driver_signal HUP 129' HUP

driver=$("$realpath_bin" -e -- "$0")
driver_sha=$("$sha256sum_bin" -- "$driver" | "$awk_bin" '{print $1}')
run_arm() {
  local ordinal=$1 device=$2 clock=$3 slot=$4 role=$5 suffix=$6 clock_path=$7
  local stage policy outer inner terminal_path supervisor_rc
  outer="gpu${device}-${clock}-${suffix}"
  inner="gpu${device}-${suffix}"
  terminal_path="$result/arm-$(printf '%02d' "$ordinal").terminal.json"
  if [[ $role == control ]]; then stage=$control; policy=0; else stage=$candidate; policy=1; fi
  active_supervisor_terminal=$terminal_path
  supervisor_spawn_state=spawning
  "$env_bin" -i \
    HOME=/home/steve USER=steve LOGNAME=steve SHELL="$bash_bin" LANG=C.UTF-8 \
    PATH="$clean_path" \
    PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH="$stage" LD_LIBRARY_PATH="$stage/vllm_xpu_kernels:$venv_lib:$torch_lib" \
    ZE_AFFINITY_MASK="$device" VLLM_XPU_FA2_FORCE_CHUNK_DECODE=1 \
    VLLM_XPU_FA2_M6_HEAD256_Q64K32_POLICY="$policy" \
    QWEN38_FA_Q64K32_CAMPAIGN_DRIVER="$driver" \
    QWEN38_FA_Q64K32_CAMPAIGN_DRIVER_SHA256="$driver_sha" \
    QWEN38_FA_Q64K32_LAB_REPO_HEAD="$repo_head" \
    "$python" -B "$campaign" supervise --ordinal "$ordinal" \
      --terminal "$terminal_path" \
      --stderr "$result/arm-$(printf '%02d' "$ordinal").supervisor.log" \
      --success "$result/arm-$(printf '%02d' "$ordinal").json" \
      --clock-receipt "$clock_path" \
      --timeout-seconds 900 --grace-seconds 10 -- \
      "$python" -B "$campaign" worker --repo "$repo" --ordinal "$ordinal" \
      --physical-gpu "$device" --role "$role" --outer-arm-id "$outer" \
      --inner-arm-id "$inner" \
      --campaign-slot "$slot" --output "$result/arm-$(printf '%02d' "$ordinal").json" &
  claim_active_supervisor "$!"
  set +e
  wait "$active_supervisor_pid"
  supervisor_rc=$?
  set -e
  management_python validate-terminal "$terminal_path" >/dev/null || return 2
  active_supervisor_pid=
  active_supervisor_terminal=
  supervisor_spawn_state=idle
  return "$supervisor_rc"
}

ordinal=0
block_index=0
# Establish and record a known default for both cards before either block.  The
# non-active card remains at default, avoiding an unregistered board-power
# interaction during the other card's paired operator measurements.
set_clock 0 400,2800 initial-default
set_clock 1 400,2800 initial-default
for block in '0 default' '1 fixed' '0 fixed' '1 default'; do
  read -r device state <<<"$block"
  block_index=$((block_index + 1))
  inactive=$((1 - device))
  if [[ $state == default ]]; then set_clock "$device" 400,2800 "$state"; else set_clock "$device" 2800,2800 "$state"; fi
  clock_receipt "$inactive" "block-${block_index}-inactive-pre"
  [[ $(parse_range "$inactive" "$result/clock-${inactive}-block-${block_index}-inactive-pre.json") == 400,2800 ]] || \
    die "inactive GPU$inactive was not at experimental default before block $block_index"
  for spec in '1 control a1' '2 candidate b1' '3 candidate b2' '4 control a2'; do
    read -r slot role suffix <<<"$spec"
    ordinal=$((ordinal + 1))
    expected_range=400,2800
    [[ $state == default ]] || expected_range=2800,2800
    clock_receipt "$device" "arm-${ordinal}-pre"
    [[ $(parse_range "$device" "$result/clock-${device}-arm-${ordinal}-pre.json") == "$expected_range" ]] || \
      die "active GPU$device drifted before arm $ordinal"
    run_arm "$ordinal" "$device" "$state" "$slot" "$role" "$suffix" \
      "$result/clock-${device}-arm-${ordinal}-pre.json"
    clock_receipt "$device" "arm-${ordinal}-post"
    [[ $(parse_range "$device" "$result/clock-${device}-arm-${ordinal}-post.json") == "$expected_range" ]] || \
      die "active GPU$device drifted during arm $ordinal"
  done
  clock_receipt "$device" "block-${block_index}-active-post"
  expected_range=400,2800
  [[ $state == default ]] || expected_range=2800,2800
  [[ $(parse_range "$device" "$result/clock-${device}-block-${block_index}-active-post.json") == "$expected_range" ]] || \
    die "active GPU$device drifted during block $block_index"
  clock_receipt "$inactive" "block-${block_index}-inactive-post"
  [[ $(parse_range "$inactive" "$result/clock-${inactive}-block-${block_index}-inactive-post.json") == 400,2800 ]] || \
    die "inactive GPU$inactive drifted during block $block_index"
  set_clock "$device" 400,2800 "post-${state}-default"
done
[[ $ordinal -eq 16 ]] || die 'internal plan did not emit 16 arms'
printf 'PASS: 16 remote arms complete; run compare separately\n'
