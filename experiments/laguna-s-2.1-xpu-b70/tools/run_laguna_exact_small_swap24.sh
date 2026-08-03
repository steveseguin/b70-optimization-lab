#!/bin/bash
# Arm one exact-small smoke with the proven nonpersistent 16 GiB validation
# swap, then always attempt to restore the ordinary 8 GiB swap-only layout.
set -euo pipefail
umask 077

readonly frozen_path=/home/steve/.venvs/deepseek-v4-xpu/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
if [[ "${LAGUNA_EXACT_SMALL_SWAP24_CLEAN_ENV:-0}" != 1 ]]; then
  exec /usr/bin/env -i \
    PATH="$frozen_path" HOME=/home/steve LANG=C.UTF-8 LC_ALL=C.UTF-8 \
    LAGUNA_EXACT_SMALL_SWAP24_CLEAN_ENV=1 /usr/bin/bash "$0" "$@"
fi
while IFS= read -r env_name; do
  case "$env_name" in
    HOME|LAGUNA_EXACT_SMALL_SWAP24_CLEAN_ENV|LANG|LC_ALL|PATH|PWD|SHLVL) ;;
    *) echo "unexpected swap24 coordinator environment variable: $env_name" >&2; exit 2 ;;
  esac
done < <(compgen -e)
export PATH="$frozen_path" HOME=/home/steve LANG=C.UTF-8 LC_ALL=C.UTF-8

tag="${1:?usage: run_laguna_exact_small_swap24.sh TAG}"
(( $# == 1 )) || { echo "exactly one tag is required" >&2; exit 2; }
[[ "$tag" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$ ]] \
  || { echo "invalid tag" >&2; exit 2; }

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
repo_root="$(git -C "$script_dir" rev-parse --show-toplevel)"
readonly core="$script_dir/run_laguna_exact_small_postrecovery.sh"
readonly lock="$script_dir/exact-small-swap24-lock.json"
readonly swap_helper="$script_dir/manage_laguna_swap_file.py"
readonly safety_helper="$script_dir/laguna_resource_safety.sh"
readonly sudo_password=/home/steve/SUDOPASSWORD.txt
readonly temporary_swap=/swap-laguna-longctx.img
readonly runs=/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs
readonly campaign_root="$runs/laguna-exact-small-postrecovery-$tag-campaign"
readonly smoke_root="$runs/laguna-exact-small-postrecovery-$tag-smoke"
readonly resource_root="$runs/laguna-exact-small-postrecovery-$tag-swap24-resource"
readonly expected_swap_layout=$'/swap-laguna-longctx.img:16777212\n/swap.img:8388604'
readonly resource_error_regex='nvme.*(error|fault|reset|timeout|abort|fail|controller)|pcie.*(error|aer|corrected|uncorrected)|aer.*(error|corrected|uncorrected)|guc.*(timeout|reset|error)|gpu.*(hang|reset|fault)|xe.*(timeout|reset|error|fail|fault|hang)|drm.*(timeout|reset|error|fail|fault|hang)'
resource_created=false
active_core_pid=""
core_pgid=""
deferred_signal=0
swap_identity_ready=false
swap_identity_args=()
resource_started_utc=""

die() { echo "Laguna exact-small swap24 coordinator: $*" >&2; exit 2; }
sha256() { sha256sum -- "$1" | awk '{print $1}'; }
sudo_do() { /usr/bin/sudo -S -p '' -- "$@" < "$sudo_password"; }
swap_layout() { awk 'NR > 1 {print $1 ":" $3}' /proc/swaps | LC_ALL=C sort; }

[[ -f "$lock" && -f "$core" && -f "$swap_helper" && -f "$safety_helper" \
   && -f "$sudo_password" \
   && ! -L "$sudo_password" && -r "$sudo_password" \
   && "$(stat -c %a -- "$sudo_password")" == 600 \
   && "$(stat -c %U -- "$sudo_password")" == steve ]] \
  || die "missing lock, core wrapper, or local sudo credential"
[[ -z "$(git -C "$repo_root" status --short)" ]] || die "main repository is dirty"
[[ "$(jq -r .schema "$lock")" == laguna-exact-small-swap24-execution-lock-v1 \
   && "$(jq -r .status "$lock")" == PASS ]] || die "execution lock is not PASS"
required_lock_files=(
  CURRENT.md
  data/laguna-device-recovery-scheduler-gate-20260802.json
  data/laguna-exact-small-portfolio-component-20260801.json
  data/laguna-exact-small-portfolio-runtime-lock-20260801.json
  data/laguna-exact-small-postrecovery-smoke-20260803.json
  data/laguna-shared-elementwise-m12-record-20260731.json
  experiments/laguna-s-2.1-xpu-b70/RESUME.md
  experiments/laguna-s-2.1-xpu-b70/notes/2026-08-01-exact-small-component-portfolio-preregistration.md
  experiments/laguna-s-2.1-xpu-b70/notes/2026-08-02-exact-small-postrecovery-preregistration.md
  experiments/laguna-s-2.1-xpu-b70/notes/2026-08-02-exact-small-postrecovery-result.md
  experiments/laguna-s-2.1-xpu-b70/notes/2026-08-02-exact-small-swap24-preregistration.md
  experiments/laguna-s-2.1-xpu-b70/realistic-suite-v1.json
  experiments/laguna-s-2.1-xpu-b70/tools/capture_laguna_m8_idle_snapshot.py
  experiments/laguna-s-2.1-xpu-b70/tools/compare_exact_runs.py
  experiments/laguna-s-2.1-xpu-b70/tools/exact-small-postrecovery-lock.json
  experiments/laguna-s-2.1-xpu-b70/tools/laguna_nvme_paths.sh
  experiments/laguna-s-2.1-xpu-b70/tools/laguna_resource_safety.sh
  experiments/laguna-s-2.1-xpu-b70/tools/manage_laguna_swap_file.py
  experiments/laguna-s-2.1-xpu-b70/tools/run_laguna_dflash_segmented_smoke.py
  experiments/laguna-s-2.1-xpu-b70/tools/run_laguna_exact_small_postrecovery.sh
  experiments/laguna-s-2.1-xpu-b70/tools/run_laguna_exact_small_swap24.sh
  experiments/laguna-s-2.1-xpu-b70/tools/run_laguna_replemb_measurement_leg.sh
  experiments/laguna-s-2.1-xpu-b70/tools/serve_laguna_mwide_graph_nvme.sh
  experiments/laguna-s-2.1-xpu-b70/tools/test_laguna_exact_small_postrecovery.py
  repro/laguna-s-2.1-int4-b70-102tps-20260726/manifests/model-release-files.sha256
  repro/laguna-s-2.1-int4-b70-102tps-20260726/verify-runtime.py
  scripts/bench-openai-realistic-suite.py
  scripts/qualify_realistic_window_metrics.py
)
observed_lock_files="$(jq -r '.files | if type == "object" then keys[] else error("files is not an object") end' "$lock")"
expected_lock_files="$(printf '%s\n' "${required_lock_files[@]}" | LC_ALL=C sort)"
[[ "$observed_lock_files" == "$expected_lock_files" ]] \
  || die "execution lock file set mismatch"
while IFS=$'\t' read -r relative expected_sha; do
  [[ "$(sha256 "$repo_root/$relative")" == "$expected_sha" ]] \
    || die "execution lock hash mismatch: $relative"
done < <(jq -r '.files | to_entries[] | [.key, .value] | @tsv' "$lock")
# shellcheck source=laguna_resource_safety.sh
source "$safety_helper"
lock_relative="${lock#"$repo_root/"}"
lock_commit="$(git -C "$repo_root" log -1 --format=%H -- "$lock")"
[[ "$(git -C "$repo_root" rev-parse HEAD)" == "$lock_commit" ]] \
  || die "execution lock must be the repository HEAD"
[[ "$(git -C "$repo_root" diff-tree --no-commit-id --name-only -r "$lock_commit")" == "$lock_relative" ]] \
  || die "execution-lock commit changed more than the lock"
[[ "$(git -C "$repo_root" rev-parse "$lock_commit^")" == "$(jq -r .harness_commit "$lock")" ]] \
  || die "execution lock is not bound to its harness commit"
[[ "$tag" == "$(jq -r .authorized.tag "$lock")" \
   && "$campaign_root" == "$(jq -r .authorized.campaign_root "$lock")" \
   && "$smoke_root" == "$(jq -r .authorized.smoke_root "$lock")" \
   && "$resource_root" == "$(jq -r .authorized.resource_root "$lock")" ]] \
  || die "tag or run roots differ from the one-shot authorization"

git_common_dir="$(git -C "$repo_root" rev-parse --git-common-dir)"
[[ "$git_common_dir" == /* ]] || git_common_dir="$repo_root/$git_common_dir"
readonly resource_mutex="$git_common_dir/laguna-exact-small-swap24-resource.lock"
exec 8>>"$resource_mutex"
flock -n 8 || die "another swap24 resource campaign holds the stable mutex"

for path in "$resource_root" "$campaign_root" "$smoke_root"; do
  [[ ! -e "$path" && ! -L "$path" ]] || die "refusing reused path: $path"
done
[[ "$(swap_layout)" == /swap.img:8388604 ]] \
  || die "ordinary 8 GiB pre-swap layout is not exact"
[[ ! -e "$temporary_swap" && ! -L "$temporary_swap" ]] \
  || die "temporary swap path already exists"
root_available_bytes="$(df -B1 --output=avail / | awk 'NR == 2 {print $1}')"
[[ "$root_available_bytes" =~ ^[0-9]+$ && "$root_available_bytes" -ge 34359738368 ]] \
  || die "root filesystem has less than the frozen 32 GiB free-space floor"

capture_resource_snapshot() {
  local phase="$1"
  {
    printf 'captured_at_utc=%s\nphase=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$phase"
    awk '/^(MemAvailable|SwapFree|SwapTotal):/ {print}' /proc/meminfo
    awk 'NR > 1 {print "swap=" $1 ":" $3}' /proc/swaps | LC_ALL=C sort
    df -B1 --output=source,size,used,avail,pcent,target /
    if [[ -e "$temporary_swap" || -L "$temporary_swap" ]]; then
      stat -c 'temporary_swap_type=%F size=%s mode=%a owner=%u:%g' -- "$temporary_swap"
    else
      printf 'temporary_swap=absent\n'
    fi
  } > "$resource_root/resource-${phase}.txt"
}

cleanup_recorded_service() {
  local pid signal attempts
  local pid_file="$smoke_root/server.pid"
  [[ -f "$pid_file" ]] || return 0
  pid="$(<"$pid_file")"
  [[ "$pid" =~ ^[1-9][0-9]*$ ]] || return 1
  if kill -0 "$pid" 2>/dev/null; then
    tr '\0' ' ' < "/proc/$pid/cmdline" \
      > "$resource_root/fallback-service-cmdline.txt" 2>/dev/null || return 1
    grep -Eq 'vllm|serve_laguna_mwide_graph_nvme' \
      "$resource_root/fallback-service-cmdline.txt" || return 1
  elif ! kill -0 -- -"$pid" 2>/dev/null; then
    return 0
  fi
  for signal in INT TERM KILL; do
    kill -"$signal" -- -"$pid" 2>/dev/null || true
    kill -"$signal" "$pid" 2>/dev/null || true
    case "$signal" in INT) attempts=20 ;; TERM) attempts=10 ;; KILL) attempts=5 ;; esac
    for _ in $(seq 1 "$attempts"); do
      if ! kill -0 "$pid" 2>/dev/null \
         && ! kill -0 -- -"$pid" 2>/dev/null; then
        return 0
      fi
      sleep 1
    done
  done
  ! kill -0 "$pid" 2>/dev/null && ! kill -0 -- -"$pid" 2>/dev/null
}

verify_no_model_survivors() {
  local process_status listener_status
  pgrep -af 'vllm serve|VLLM::EngineCore|VLLM::Worker|torchrun|run_laguna_replemb_measurement_leg.sh|run_laguna_exact_small_postrecovery.sh' \
    > "$resource_root/processes-after-core.txt" \
    2> "$resource_root/processes-after-core.stderr"
  process_status=$?
  ss -H -ltn 'sport = :8000 or sport = :18080' \
    > "$resource_root/listeners-after-core.txt" \
    2> "$resource_root/listeners-after-core.stderr"
  listener_status=$?
  (( process_status == 1 )) \
    && [[ ! -s "$resource_root/processes-after-core.stderr" ]] \
    && (( listener_status == 0 )) \
    && [[ ! -s "$resource_root/listeners-after-core.stderr" \
          && ! -s "$resource_root/listeners-after-core.txt" ]]
}

seal_core_roots() {
  local root writable_entries find_status
  for root in "$campaign_root" "$smoke_root"; do
    if [[ -d "$root" && ! -L "$root" ]]; then
      chmod -R a-w -- "$root" || return 1
      writable_entries="$(find "$root" -perm /222 -print -quit 2>/dev/null)"
      find_status=$?
      [[ "$find_status" == 0 && -z "$writable_entries" ]] || return 1
    elif [[ -e "$root" || -L "$root" ]]; then
      return 1
    fi
  done
}

swap_identity_matches() {
  [[ "$swap_identity_ready" == true ]] || return 1
  /usr/bin/python3 "$swap_helper" verify "${swap_identity_args[@]}" >/dev/null
}

load_swap_identity_record() {
  local identity_tsv device inode uid gid size mode
  [[ -f "$resource_root/swap-identity.json" \
     && ! -L "$resource_root/swap-identity.json" ]] || return 1
  identity_tsv="$(jq -er '
    if keys == ["device", "gid", "inode", "mode", "size", "uid"]
       and .uid == 0 and .gid == 0
       and .size == 17179869184 and .mode == 384
       and (.device | type == "number") and (.inode | type == "number")
    then [.device, .inode, .uid, .gid, .size, .mode] | @tsv
    else error("invalid swap identity record")
    end
  ' "$resource_root/swap-identity.json")" || return 1
  IFS=$'\t' read -r device inode uid gid size mode <<< "$identity_tsv"
  [[ "$device" =~ ^[0-9]+$ && "$inode" =~ ^[1-9][0-9]*$ \
     && "$uid" == 0 && "$gid" == 0 \
     && "$size" == 17179869184 && "$mode" == 384 ]] || return 1
  swap_identity_args=("$device" "$inode" "$uid" "$gid" "$size" "$mode")
  swap_identity_ready=true
  if ! swap_identity_matches; then
    swap_identity_args=()
    swap_identity_ready=false
    return 1
  fi
}

inspect_swap_state() {
  /usr/bin/python3 "$swap_helper" state
}

finalize_resource() {
  local status="$?" core_stop_status=0 service_cleanup_status=0 model_idle_status=0
  local core_group_status=0 core_seal_status=0 identity_status=0 state_status=0
  local swapoff_status=0
  local post_state_status=0 remove_status=0 journal_status=0 journal_grep_status=0
  local cleanup_status=0 seal_status=0
  local observed state post_state writable_entries find_status temporary_presence
  local stop_attempt_status=0
  trap - EXIT
  trap '' HUP INT TERM
  set +e
  if [[ -n "$active_core_pid" ]] \
     && laguna_process_is_running "$active_core_pid" \
     && ! laguna_process_group_exists "$core_pgid"; then
    laguna_stop_process_bounded "$active_core_pid"
    stop_attempt_status=$?
    (( stop_attempt_status == 0 )) || core_stop_status="$stop_attempt_status"
  fi
  if [[ -n "$core_pgid" ]] && laguna_process_group_exists "$core_pgid"; then
    laguna_stop_process_group_bounded "$core_pgid"
    stop_attempt_status=$?
    (( stop_attempt_status == 0 )) || core_stop_status="$stop_attempt_status"
  fi
  if [[ -n "$active_core_pid" ]]; then
    if ! laguna_process_is_running "$active_core_pid"; then
      wait "$active_core_pid" 2>/dev/null || true
      active_core_pid=""
    else
      (( core_stop_status != 0 )) || core_stop_status=1
      core_group_status=1
    fi
  fi
  if [[ "$resource_created" == true ]]; then
    cleanup_recorded_service || service_cleanup_status=1
    verify_no_model_survivors || model_idle_status=1
    if [[ -n "$core_pgid" ]] && laguna_process_group_exists "$core_pgid"; then
      core_group_status=1
    fi
    if (( service_cleanup_status == 0 && model_idle_status == 0 \
          && core_group_status == 0 )); then
      seal_core_roots || core_seal_status=1
    else
      core_seal_status=125
    fi
    if [[ ( -e "$temporary_swap" || -L "$temporary_swap" ) \
          && "$swap_identity_ready" != true ]]; then
      load_swap_identity_record || true
    fi
    state="$(inspect_swap_state \
      2> "$resource_root/swap-state-before-cleanup.stderr")"
    state_status=$?
    printf '%s\n' "$state" > "$resource_root/swap-state-before-cleanup.txt"
    if [[ -e "$temporary_swap" || -L "$temporary_swap" ]]; then
      swap_identity_matches || identity_status=1
    elif [[ "$swap_identity_ready" == true ]]; then
      identity_status=1
    elif [[ "$state_status" != 0 || "$state" != INACTIVE ]]; then
      identity_status=1
    fi
    if laguna_swapoff_allowed \
      "$service_cleanup_status" "$model_idle_status" "$core_group_status" \
      "$core_seal_status" "$identity_status" "$state_status" "$state"; then
      if [[ "$state" == ACTIVE ]]; then
        sudo_do /usr/sbin/swapoff "$temporary_swap" \
          > "$resource_root/swapoff.stdout" 2> "$resource_root/swapoff.stderr"
        swapoff_status=$?
      elif [[ "$state" != INACTIVE ]]; then
        swapoff_status=1
      fi
    else
      swapoff_status=125
    fi
    post_state="$(inspect_swap_state \
      2> "$resource_root/swap-state-after-swapoff.stderr")"
    post_state_status=$?
    printf '%s\n' "$post_state" > "$resource_root/swap-state-after-swapoff.txt"
    temporary_presence=ABSENT
    if [[ -e "$temporary_swap" || -L "$temporary_swap" ]]; then
      temporary_presence=PRESENT
    fi
    if laguna_remove_allowed \
      "$service_cleanup_status" "$model_idle_status" "$core_group_status" \
      "$core_seal_status" "$identity_status" "$state_status" \
      "$swapoff_status" "$post_state_status" "$post_state" \
      "$temporary_presence"; then
      sudo_do /usr/bin/python3 "$swap_helper" remove-inactive \
        "${swap_identity_args[@]}" \
        > "$resource_root/remove.stdout" 2> "$resource_root/remove.stderr"
      remove_status=$?
    elif [[ ! -e "$temporary_swap" && ! -L "$temporary_swap" \
            && "$post_state_status" == 0 && "$post_state" == INACTIVE ]]; then
      remove_status=0
    else
      remove_status=125
    fi
    capture_resource_snapshot postcleanup || cleanup_status=1
    journalctl -k -b --since "$resource_started_utc" --no-pager \
      > "$resource_root/kernel-journal-resource.log" \
      2> "$resource_root/kernel-journal-resource.stderr"
    journal_status=$?
    grep -Eai "$resource_error_regex" "$resource_root/kernel-journal-resource.log" \
      > "$resource_root/device-error-scan-resource.log" \
      2> "$resource_root/device-error-scan-resource.stderr"
    journal_grep_status=$?
    (( journal_status == 0 && journal_grep_status == 1 )) \
      && [[ ! -s "$resource_root/kernel-journal-resource.stderr" \
            && ! -s "$resource_root/device-error-scan-resource.stderr" \
            && ! -s "$resource_root/device-error-scan-resource.log" ]] \
      || cleanup_status=1
    observed="$(swap_layout)"
    temporary_presence=ABSENT
    if [[ -e "$temporary_swap" || -L "$temporary_swap" ]]; then
      temporary_presence=PRESENT
    fi
    laguna_cleanup_passes \
      "$core_stop_status" "$service_cleanup_status" "$model_idle_status" \
      "$core_group_status" "$core_seal_status" "$identity_status" \
      "$state_status" "$swapoff_status" "$post_state_status" \
      "$remove_status" "$journal_status" "$journal_grep_status" \
      "$observed" "$temporary_presence" || cleanup_status=1
    (( status != 0 || cleanup_status == 0 )) || status=1
    printf 'preseal_exit_status=%s\ncore_stop_status=%s\nservice_cleanup_status=%s\nmodel_idle_status=%s\ncore_group_status=%s\ncore_seal_status=%s\nidentity_status=%s\nstate_status=%s\nswapoff_status=%s\npost_state_status=%s\nremove_status=%s\njournal_status=%s\njournal_grep_status=%s\ncleanup_status=%s\nseal_claim=UNVERIFIED_CHECK_PERMISSIONS_AND_PROCESS_EXIT\ncompleted_at_utc=%s\n' \
      "$status" "$core_stop_status" "$service_cleanup_status" \
      "$model_idle_status" "$core_group_status" "$core_seal_status" \
      "$identity_status" "$state_status" "$swapoff_status" "$post_state_status" \
      "$remove_status" "$journal_status" "$journal_grep_status" \
      "$cleanup_status" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
      > "$resource_root/resource-status.txt" || { status=1; seal_status=1; }
    chmod -R a-w -- "$resource_root" 2>/dev/null || seal_status=1
    writable_entries="$(find "$resource_root" -perm /222 -print -quit 2>/dev/null)"
    find_status=$?
    [[ "$find_status" == 0 && -z "$writable_entries" ]] || seal_status=1
    if (( seal_status != 0 )); then
      status=1
    fi
  fi
  exit "$status"
}
trap finalize_resource EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM

trap 'deferred_signal=129' HUP
trap 'deferred_signal=130' INT
trap 'deferred_signal=143' TERM
mkdir -m 700 "$resource_root"
resource_created=true
resource_started_utc="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM
if (( deferred_signal != 0 )); then
  exit "$deferred_signal"
fi
capture_resource_snapshot precreate
trap 'deferred_signal=129' HUP
trap 'deferred_signal=130' INT
trap 'deferred_signal=143' TERM
sudo_do /usr/bin/python3 "$swap_helper" create \
  > "$resource_root/swap-identity.json" 2> "$resource_root/swap-create.stderr"
load_swap_identity_record || die "exclusive swap identity verification failed"
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM
if (( deferred_signal != 0 )); then
  exit "$deferred_signal"
fi
sudo_do /usr/sbin/mkswap "$temporary_swap" \
  > "$resource_root/mkswap.stdout" 2> "$resource_root/mkswap.stderr"
sudo_do /usr/sbin/swapon "$temporary_swap" \
  > "$resource_root/swapon.stdout" 2> "$resource_root/swapon.stderr"
[[ "$(swap_layout)" == "$expected_swap_layout" \
   && "$(inspect_swap_state)" == ACTIVE ]] \
  || die "frozen 24 GiB swap preparation failed"
swap_identity_matches || die "active swap identity changed"
capture_resource_snapshot prepared
printf 'SWAP24_PASS\n' > "$resource_root/prepared-status.txt"

trap 'deferred_signal=129' HUP
trap 'deferred_signal=130' INT
trap 'deferred_signal=143' TERM
/usr/bin/setsid /usr/bin/env -i \
  PATH="$frozen_path" HOME=/home/steve LANG=C.UTF-8 LC_ALL=C.UTF-8 \
  LAGUNA_EXACT_SMALL_CLEAN_ENV=1 LAGUNA_EXACT_SMALL_SWAP24_ARMED=1 \
  /usr/bin/bash "$core" "$tag" \
  > "$resource_root/core.stdout" 2>&1 &
active_core_pid="$!"
core_pgid="$active_core_pid"
laguna_wait_for_dedicated_group "$core_pgid" 100 0.01 \
  || die "core did not establish its dedicated process group"
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM
if (( deferred_signal != 0 )); then
  exit "$deferred_signal"
fi
set +e
wait "$active_core_pid"
core_status=$?
set -e
active_core_pid=""
exit "$core_status"
