#!/usr/bin/env bash
set -euo pipefail

# Source-only preregistered remote campaign.  The run command remains blocked
# until the reference host identity and xpu-smi telemetry schema are frozen in
# both this driver and its Python supervisor.

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

campaign_sha=821574440cc7111f049d6188ddba69ebfd0a2e63ab08af039e0b351ea256969e
preparer_sha=e20b1f09363b3361e5a90fa868f1a8dffced87b482dc1e9ebb016e9d945a4ea8
qualifier_sha=31862ea6a8b9e11a59d643e0d3500179d938261e62b93fb920439c664ce21fbc
base_qualifier_sha=0dd7b945ef35a11ff4d0a1ec085e604920524b996d539e089d89b4a019a5de1f
authorized_repo_head=REMOTE_REPO_HEAD_TO_FREEZE
authorized_stage_json_sha=REMOTE_STAGE_JSON_SHA256_TO_FREEZE
authorized_device0_uuid=REMOTE_GPU0_UUID_TO_FREEZE
authorized_device0_bdf=REMOTE_GPU0_BDF_TO_FREEZE
authorized_device1_uuid=REMOTE_GPU1_UUID_TO_FREEZE
authorized_device1_bdf=REMOTE_GPU1_BDF_TO_FREEZE
authorized_xpu_smi_schema_sha=REMOTE_XPU_SMI_SCHEMA_SHA256_TO_FREEZE
authorized_xpu_smi_sha=REMOTE_XPU_SMI_BINARY_SHA256_TO_FREEZE
authorized_xpu_smi_version=REMOTE_XPU_SMI_VERSION_TO_FREEZE
authorized_system_runtime_inventory_sha=REMOTE_SYSTEM_RUNTIME_INVENTORY_SHA256_TO_FREEZE
xpu_smi=/usr/bin/xpu-smi
launch_authorized=false
driver_signal_ownership_authorized=false
clock_writer_exclusion_authorized=false
driver_environment_authorized=false

die() { printf 'error: %s\n' "$*" >&2; exit 2; }
verify() {
  local path=$1 expected=$2 actual
  [[ -f $path ]] || die "missing: $path"
  [[ $expected =~ ^[0-9a-f]{64}$ ]] || die "unfrozen SHA for $path"
  actual=$(sha256sum -- "$path" | awk '{print $1}')
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

[[ $(hostname) == "$host" ]] || die "requires $host"
[[ $(realpath -e -- "$repo") == "$repo" ]] || die 'repo path is absent/noncanonical'
[[ $(git -C "$repo" branch --show-current) == main ]] || die 'requires main'
[[ -z $(git -C "$repo" status --porcelain --untracked-files=normal) ]] || die 'requires clean repo'
repo_head=$(git -C "$repo" rev-parse HEAD)
[[ $repo_head == "$authorized_repo_head" ]] || die 'remote repository HEAD is not frozen identity'
[[ $repo_head == $(git -C "$repo" rev-parse origin/main) ]] || die 'requires main == origin/main'
verify "$campaign" "$campaign_sha"
verify "$preparer" "$preparer_sha"
verify "$qualifier" "$qualifier_sha"
verify "$base_qualifier" "$base_qualifier_sha"
verify "$candidate_manifest" "$authorized_stage_json_sha"
[[ -x $python ]] || die 'XPU Python is absent'

if [[ $action == audit ]]; then
  "$python" -B "$campaign" audit --repo "$repo" --require-host --require-stages
  exit
fi

# These values are deliberately placeholders until a passive, post-recovery
# inventory is captured and reviewed.  No ordinal-only identity is accepted.
for frozen in \
  "$authorized_device0_uuid" "$authorized_device0_bdf" \
  "$authorized_device1_uuid" "$authorized_device1_bdf" \
  "$authorized_xpu_smi_schema_sha" \
  "$authorized_xpu_smi_sha" "$authorized_xpu_smi_version" \
  "$authorized_system_runtime_inventory_sha"; do
  [[ $frozen != *_TO_FREEZE ]] || die 'device/telemetry identity is not frozen'
done
verify "$xpu_smi" "$authorized_xpu_smi_sha"
[[ $(realpath -e -- "$xpu_smi") == "$xpu_smi" ]] || \
  die 'xpu-smi path is not canonical'
[[ $($xpu_smi --version) == "$authorized_xpu_smi_version" ]] || \
  die 'xpu-smi version differs from frozen identity'
audit_json=$("$python" -B "$campaign" audit --repo "$repo" --require-host --require-stages)
[[ $(jq -er '.authorized_system_runtime_inventory_sha256' <<<"$audit_json") == \
   "$authorized_system_runtime_inventory_sha" ]] || \
  die 'driver/source system-runtime inventory binding differs'
[[ $(jq -er '.authorized_xpu_smi.path' <<<"$audit_json") == "$xpu_smi" && \
   $(jq -er '.authorized_xpu_smi.sha256' <<<"$audit_json") == "$authorized_xpu_smi_sha" && \
   $(jq -er '.authorized_xpu_smi.version' <<<"$audit_json") == "$authorized_xpu_smi_version" ]] || \
  die 'driver/source xpu-smi identity binding differs'

if [[ $action == compare ]]; then
  [[ -d $result ]] || die "missing result root: $result"
  terminals=()
  for ordinal in $(seq 1 16); do
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
  for ordinal in $(seq 1 16); do
    if [[ $ordinal -le 4 || ( $ordinal -ge 9 && $ordinal -le 12 ) ]]; then
      device=0
    else
      device=1
    fi
    arm_post_receipts+=("$result/clock-${device}-arm-${ordinal}-post.json")
  done
  set +e
  "$python" -B "$campaign" compare-operator --repo "$repo" --clock-state default \
    --output "$result/default-clock-operator-comparison.json" "${default_packets[@]}"
  default_rc=$?
  "$python" -B "$campaign" compare-operator --repo "$repo" --clock-state fixed \
    --output "$result/fixed-clock-operator-comparison.json" "${fixed_packets[@]}"
  fixed_rc=$?
  "$python" -B "$campaign" compare-terminals \
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
command -v timeout >/dev/null || die 'timeout is absent'
sudo -n true >/dev/null 2>&1 || die 'noninteractive sudo prerequisite is not satisfied'

# Future telemetry parser must validate exact ID->UUID/BDF and effective min/max
# from these JSON receipts before the source launch gate may be enabled.
clock_receipt() {
  local device=$1 label=$2 output="$result/clock-${device}-${label}.json"
  local config_tmp="$result/.clock-${device}-${label}.config.tmp.json"
  local discovery_tmp="$result/.clock-${device}-${label}.discovery.tmp.json"
  [[ ! -e $output ]] || die "clock receipt collision: $output"
  [[ ! -e $config_tmp && ! -e $discovery_tmp ]] || \
    die "clock raw-receipt collision for GPU$device/$label"
  timeout -k 5s 30s "$xpu_smi" config -d "$device" -t 0 -j >"$config_tmp"
  timeout -k 5s 30s "$xpu_smi" discovery -j >"$discovery_tmp"
  "$python" -B "$campaign" seal-clock-receipt --device "$device" \
    --config "$config_tmp" --discovery "$discovery_tmp" --output "$output" \
    >/dev/null
  rm -- "$config_tmp" "$discovery_tmp"
}
parse_range() {
  local device=$1 receipt=$2 parsed minimum maximum uuid bdf schema expected_uuid expected_bdf
  parsed=$("$python" -B "$campaign" parse-clock-receipt --device "$device" "$receipt")
  minimum=$(jq -er '.min_mhz | select(type == "number" and floor == .)' <<<"$parsed") || \
    die 'parsed minimum clock is absent/nonintegral'
  maximum=$(jq -er '.max_mhz | select(type == "number" and floor == .)' <<<"$parsed") || \
    die 'parsed maximum clock is absent/nonintegral'
  uuid=$(jq -er '.uuid | select(type == "string" and length > 0)' <<<"$parsed") || \
    die 'parsed UUID is absent'
  bdf=$(jq -er '.bdf | select(type == "string" and length > 0)' <<<"$parsed") || \
    die 'parsed BDF is absent'
  schema=$(jq -er '.schema_sha256 | select(type == "string")' <<<"$parsed") || \
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
  timeout -k 5s 30s sudo -n "$xpu_smi" config -d "$device" -t 0 --frequencyrange "$range" -j \
    >"$result/clock-${device}-${label}-set.json.tmp"
  chmod 0444 "$result/clock-${device}-${label}-set.json.tmp"
  mv -- "$result/clock-${device}-${label}-set.json.tmp" \
    "$result/clock-${device}-${label}-set.json"
  clock_receipt "$device" "$label-effective"
  effective_receipt="$result/clock-${device}-${label}-effective.json"
  effective=$(parse_range "$device" "$effective_receipt")
  [[ $effective == "$range" ]] || \
    die "effective clock differs for GPU$device: $effective != $range"
}

mkdir -- "$result"
arm_terminals=()
for arm_ordinal in $(seq 1 16); do
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
restore_pre_run_ranges() {
  trap '' EXIT INT TERM HUP
  local original_rc=$1
  local terminal_rc
  for device in 0 1; do
    if ! timeout -k 5s 30s sudo -n "$xpu_smi" config -d "$device" -t 0 --frequencyrange "${original_ranges[$device]}" -j \
      >"$result/clock-${device}-restore-set.json.tmp"; then
      restore_rc=1
      continue
    fi
    chmod 0444 "$result/clock-${device}-restore-set.json.tmp"
    mv -- "$result/clock-${device}-restore-set.json.tmp" \
      "$result/clock-${device}-restore-set.json"
    if ! clock_receipt "$device" restore-effective; then
      restore_rc=1
    elif [[ $(parse_range "$device" "$result/clock-${device}-restore-effective.json") != "${original_ranges[$device]}" ]]; then
      restore_rc=1
    fi
  done
  [[ $restore_rc -eq 0 ]] || printf 'FATAL: exact pre-run clock restoration was not proved\n' >&2
  set +e
  "$python" -B "$campaign" seal-restoration \
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
trap 'restore_pre_run_ranges $?' EXIT
trap 'restore_pre_run_ranges 130' INT
trap 'restore_pre_run_ranges 143' TERM
trap 'restore_pre_run_ranges 129' HUP

driver=$(realpath -e -- "$0")
driver_sha=$(sha256sum -- "$driver" | awk '{print $1}')
run_arm() {
  local ordinal=$1 device=$2 clock=$3 slot=$4 role=$5 suffix=$6 clock_path=$7
  local stage policy outer inner terminal_path supervisor_rc
  outer="gpu${device}-${clock}-${suffix}"
  inner="gpu${device}-${suffix}"
  terminal_path="$result/arm-$(printf '%02d' "$ordinal").terminal.json"
  if [[ $role == control ]]; then stage=$control; policy=0; else stage=$candidate; policy=1; fi
  set +e
  env -i \
    HOME=/home/steve USER=steve LOGNAME=steve SHELL=/bin/bash LANG=C.UTF-8 \
    PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
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
      --campaign-slot "$slot" --output "$result/arm-$(printf '%02d' "$ordinal").json"
  supervisor_rc=$?
  set -e
  "$python" -B "$campaign" validate-terminal "$terminal_path" || return 2
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
