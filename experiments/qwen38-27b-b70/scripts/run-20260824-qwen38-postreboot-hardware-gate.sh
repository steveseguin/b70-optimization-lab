#!/usr/bin/env bash
set -Eeuo pipefail

# One-shot hardware gate after the 2026-08-24 unclean reboot. This deliberately
# does not combine ONEAPI_DEVICE_SELECTOR with ZE_AFFINITY_MASK. The first
# exact-current TP1 control arm supplies the subsequent model-generation canary
# before it starts its timed benchmark.

umask 077

script_path=$(realpath -e -- "${BASH_SOURCE[0]}")
script_dir=$(dirname -- "$script_path")
repo=$(git -C "$script_dir" rev-parse --show-toplevel)
python=/home/steve/.venvs/vllm-xpu/bin/python
probe=$repo/tools/xccl_probe.py
venv_lib=/home/steve/.venvs/vllm-xpu/lib
torch_xpu_lib=$venv_lib/python3.12/site-packages/torch/lib/libtorch_xpu.so
venv_sycl_lib=$venv_lib/libsycl.so.8
venv_ccl1_lib=$venv_lib/libccl.so.1
venv_ccl2_lib=$venv_lib/libccl.so.2
venv_ur_loader=$venv_lib/libur_loader.so.0
peer_binary=/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/w1-n128-device-lost-recovery-20260723T103343Z/no-reboot-validation/sycl-peer-read-test-oneapi2026
sycl_ls=/opt/intel/oneapi/compiler/2026.0/bin/sycl-ls
sudo_pass_file=${SUDO_PASS_FILE:-/home/steve/SUDOPASSWORD.txt}
result_root=${RESULT_ROOT:-/home/steve/qwen38-current-main-runs/postreboot-hardware-gate-20260824-086de284}

expected_boot_id=086de284-0771-4269-9cb2-e064fe303e40
expected_kernel=7.0.0-30-generic
expected_python_sha256=202c17d1671602a4ef1d43e9b2fdbef0769443f37bf5e51f6b603e0b2c27d9d8
expected_probe_sha256=6ecd340651a6780fdbe0bd57d346540efe168bf2e3175d54e10dd8660ed5b30a
expected_torch_xpu_sha256=ee584edab22b995637c5f6ec83fc10dea5931469c86cf2ad91952bb3e1108290
expected_venv_sycl_sha256=0336997fdfed9b2e6385e9f1cea2395eb5e130d3e5e9c943df5b0c10c1b5e57f
expected_venv_ccl1_sha256=ace144a390a53720b2743844decf127661c942b56f3b414900b9d8c11461acc3
expected_venv_ccl2_sha256=1185b0591e66f3b94f19b891367ad1c4ad5a95792f658f46d284fc7c643aedb7
expected_venv_ur_loader_sha256=68e273791752638dfad1ce3bb002b0ed8d00ceee21e491cd46dd0668d716bfa0
expected_peer_sha256=1ab3b96dd1c7cd46a2e5422b0b6bf705ba5b80f306102e968768f634ee4bf92c
expected_sycl_ls_sha256=90843629cfe9faaa5b5308524f82399b493b82a64b8db4956284b626d886dfb4
oneapi_ld_library_path=/opt/intel/oneapi/umf/1.1/lib:/opt/intel/oneapi/compiler/2026.0/lib:/opt/intel/oneapi/compiler/2026.0/opt/compiler/lib
torch_ld_library_path=$venv_lib
reject_pattern='Timedout job:|Kernel-submitted job timed out|VM job timed out|device coredump|GT.*reset|reset (queued|started|done)|TLB.*timeout|GuC.*(fail|error|timeout)|CT.*(fail|error|timeout)|xe.*(device.?lost|fault|reset|hung|hang[: ]|tim(e|ed)[ -]?out)|AER:.*(error|fatal|nonfatal)|Hardware Error|aer_status|RxErr|NonFatalErr|nvme.*(timeout|reset|I/O error)|EXT4-fs error|segfault|WARNING:|BUG:|Oops:'

die() {
  printf 'error: %s\n' "$*" >&2
  exit 1
}

check_sha256() {
  local path=$1 expected=$2 actual
  actual=$(sha256sum "$path" | awk '{print $1}')
  [[ $actual == "$expected" ]] ||
    die "hash mismatch for $path: $actual"
}

check_torch_loader_resolution() {
  local resolution path expected_name expected_path
  resolution=$(LD_LIBRARY_PATH="$torch_ld_library_path" ldd "$torch_xpu_lib") ||
    die 'could not resolve the frozen Torch XPU runtime'
  printf '%s\n' "$resolution" >"$result_root/torch-loader-resolution.txt"
  while IFS='|' read -r expected_name expected_path; do
    path=$(awk -v name="$expected_name" '$1 == name {print $3}' \
      "$result_root/torch-loader-resolution.txt")
    [[ -n $path && $(readlink -f -- "$path") == \
      "$(readlink -f -- "$expected_path")" ]] ||
      die "Torch runtime resolved $expected_name incoherently: ${path:-missing}"
  done <<EOF
libsycl.so.8|$venv_sycl_lib
libccl.so.1|$venv_ccl1_lib
libccl.so.2|$venv_ccl2_lib
libur_loader.so.0|$venv_ur_loader
EOF
  ! grep -Fq 'not found' "$result_root/torch-loader-resolution.txt" ||
    die 'Torch XPU runtime has an unresolved library'
}

require_one_fixed_marker() {
  local marker=$1 path=$2 count
  count=$(awk -v needle="$marker" '
    {
      line = $0
      while ((at = index(line, needle)) != 0) {
        count++
        line = substr(line, at + length(needle))
      }
    }
    END { print count + 0 }
  ' "$path") || die "could not count XCCL marker: $marker"
  [[ $count == 1 ]] ||
    die "expected one XCCL marker, observed $count: $marker"
}

validate_inherited_lock() {
  local fd=$1 expected_path=$2 actual_path competing_fd competing_rc
  [[ $fd =~ ^[0-9]+$ ]] || die "invalid inherited lock descriptor: $fd"
  [[ -e /proc/$$/fd/$fd ]] || die "inherited lock descriptor $fd is closed"
  actual_path=$(readlink -f -- "/proc/$$/fd/$fd")
  [[ $actual_path == "$(readlink -f -- "$expected_path")" ]] ||
    die "inherited lock path mismatch: $actual_path != $expected_path"
  exec {competing_fd}<>"$expected_path"
  if flock -n "$competing_fd"; then
    competing_rc=0
  else
    competing_rc=$?
  fi
  exec {competing_fd}>&-
  [[ $competing_rc -eq 1 ]] || {
    [[ $competing_rc -ne 0 ]] ||
      die "inherited descriptor was not pre-locked by its parent: $expected_path"
    die "could not verify inherited lock ownership: $expected_path"
  }
  flock -n "$fd" || die "inherited lock is not exclusively held: $expected_path"
}

check_render_idle() {
  local label=$1 rc
  if timeout --signal=TERM --kill-after=5s 20s sudo -S -p '' fuser \
      "${render_nodes[@]}" >"$result_root/render-holders.$label.stdout" \
      2>"$result_root/render-holders.$label.stderr" <"$sudo_pass_file"; then
    rc=0
  else
    rc=$?
  fi
  printf '%s\n' "$rc" >"$result_root/render-holders.$label.rc"
  [[ $rc -eq 1 && ! -s $result_root/render-holders.$label.stdout &&
     ! -s $result_root/render-holders.$label.stderr ]]
}

write_manifest() {
  (
    cd "$result_root" || exit 1
    find . -maxdepth 1 -type f ! -name 'SHA256SUMS*' ! -name '*.tmp' \
      -printf '%P\n' | LC_ALL=C sort | xargs -r sha256sum \
      >SHA256SUMS.tmp &&
      grep -Fxq 'summary.json' < <(awk '{print $2}' SHA256SUMS.tmp) &&
      grep -Fxq 'final.status' < <(awk '{print $2}' SHA256SUMS.tmp) &&
      if [[ $gate_complete == true ]]; then
        for required_name in hardware-gate.sh kernel-baseline.log \
          kernel-delta.log kernel-reject-events.log kernel-taint.pre.txt \
          kernel-taint.post.txt xpu-discovery.log xpu-discovery-post.log \
          xpu-discovery.check xpu-discovery.rc xpu-discovery-post.rc \
          started-utc.txt repo-head.txt uname.txt tool-identities.sha256 \
          torch-loader-resolution.txt \
          inherited-runtime-variable-names.txt \
          docker-running-containers.pre.txt docker-ps.pre.stderr \
          docker-ps.pre.rc model-processes.pre.log model-processes.pre.stderr \
          model-processes.pre.rc render-holders.pre.stdout \
          render-holders.pre.stderr render-holders.pre.rc \
          sycl-level-zero-gpu0.log sycl-level-zero-gpu1.log \
          sycl-level-zero-gpu2.log sycl-level-zero-gpu3.log \
          sycl-identity-gpu0.rc sycl-identity-gpu1.rc \
          sycl-identity-gpu2.rc sycl-identity-gpu3.rc \
          compute-gpu0.log compute-gpu1.log compute-gpu2.log compute-gpu3.log \
          compute-gpu0.rc compute-gpu1.rc compute-gpu2.rc compute-gpu3.rc \
          peer-read.log peer-read.rc xccl-allreduce.log xccl-allreduce.rc \
          render-holders.post.stdout render-holders.post.stderr \
          render-holders.post.rc docker-running-containers.post.txt \
          docker-ps.post.stderr docker-ps.post.rc \
          render-holders.final.stdout render-holders.final.stderr \
          render-holders.final.rc residual-probe-processes.log \
          residual-probe-processes.stderr residual-probe-processes.rc; do
          grep -Fxq "$required_name" < <(awk '{print $2}' SHA256SUMS.tmp) ||
            exit 1
        done
      fi &&
      mv -f -- SHA256SUMS.tmp SHA256SUMS
  )
}

mark_summary_failed() {
  local exit_code=$1
  [[ -f $result_root/summary.json ]] || return 1
  jq --argjson exit_code "$exit_code" \
    '.passed = false | .exit_code = $exit_code' \
    "$result_root/summary.json" >"$result_root/summary.json.tmp" &&
    mv -f -- "$result_root/summary.json.tmp" "$result_root/summary.json"
}

run_capture() {
  local label=$1
  shift
  set +e
  "$@" >"$result_root/$label.log" 2>&1
  local rc=$?
  set -e
  printf '%s\n' "$rc" >"$result_root/$label.rc"
  [[ $rc -eq 0 ]] || die "$label failed with rc=$rc"
}

capture_kernel_delta() {
  local journal_rc rg_rc
  [[ -n $journal_cursor ]] || return 2
  if timeout --signal=TERM --kill-after=5s 30s \
      journalctl -b -k --after-cursor "$journal_cursor" --no-pager \
      -o short-iso >"$result_root/kernel-delta.log"; then
    journal_rc=0
  else
    journal_rc=$?
  fi
  [[ $journal_rc -eq 0 ]] || return "$journal_rc"
  if rg -i "$reject_pattern" "$result_root/kernel-delta.log" \
      >"$result_root/kernel-reject-events.log"; then
    return 1
  else
    rg_rc=$?
  fi
  [[ $rg_rc -eq 1 ]] || return "$rg_rc"
  : >"$result_root/kernel-reject-events.log"
}

started_utc=not-started
gate_complete=false
failure_stage=preflight
journal_cursor=
repo_head=unresolved
sudo_ready=false
four_device_identity=false
per_card_compute=false
four_device_peer_read=false
four_rank_xccl_allreduce=false
repo_postflight=false
atomic_lock_handoff=false
torch_runtime_coherent=false
taint_pre=unread
taint_post=unread
result_root_created=false
declare -a render_nodes=()

finalize() {
  local rc=$? kernel_rc=0 manifest_rc=0 sync_rc=0 completed_utc reject_count
  local boot_id_final kernel_final
  trap - EXIT
  trap '' INT TERM HUP
  set +e
  if [[ $result_root_created == true && ! -d $result_root ]]; then
    [[ $rc -ne 0 ]] || rc=100
  elif [[ $result_root_created == true ]]; then
    capture_kernel_delta
    kernel_rc=$?
    if [[ $kernel_rc -ne 0 && $rc -eq 0 ]]; then
      rc=91
    fi
    taint_post=$(</proc/sys/kernel/tainted)
    printf '%s\n' "$taint_post" >"$result_root/kernel-taint.post.txt"
    if [[ $taint_post != 0 && $rc -eq 0 ]]; then
      rc=92
    fi
    if [[ $sudo_ready == true && ${#render_nodes[@]} -eq 4 ]]; then
      check_render_idle final
      if [[ $? -ne 0 && $rc -eq 0 ]]; then
        rc=93
      fi
    fi
    if pgrep -af '[t]orch.distributed.run|[x]ccl_probe.py|[s]ycl-peer-read-test-oneapi2026' \
        >"$result_root/residual-probe-processes.log" \
        2>"$result_root/residual-probe-processes.stderr"; then
      residual_pgrep_rc=0
    else
      residual_pgrep_rc=$?
    fi
    printf '%s\n' "$residual_pgrep_rc" \
      >"$result_root/residual-probe-processes.rc"
    if [[ $residual_pgrep_rc -ne 1 && $rc -eq 0 ]]; then
      rc=94
    fi
    if completed_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ); then
      :
    else
      [[ $rc -ne 0 ]] || rc=99
      completed_utc=invalid
    fi
    if IFS= read -r boot_id_final </proc/sys/kernel/random/boot_id; then
      :
    else
      [[ $rc -ne 0 ]] || rc=99
      boot_id_final=invalid
    fi
    if kernel_final=$(uname -r); then
      :
    else
      [[ $rc -ne 0 ]] || rc=99
      kernel_final=invalid
    fi
    if [[ $boot_id_final != "$expected_boot_id" ||
          $kernel_final != "$expected_kernel" ||
          ! $completed_utc =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$ ]]; then
      [[ $rc -ne 0 ]] || rc=99
    fi
    reject_count=0
    [[ -f $result_root/kernel-reject-events.log ]] &&
      reject_count=$(wc -l <"$result_root/kernel-reject-events.log")
    if ! jq -n \
      --arg started_utc "$started_utc" --arg completed_utc "$completed_utc" \
      --arg boot_id "$boot_id_final" \
      --arg kernel "$kernel_final" \
      --arg repo_head "$repo_head" --arg journal_cursor "$journal_cursor" \
      --arg reject_pattern "$reject_pattern" \
      --arg failure_stage "$failure_stage" \
      --arg taint_pre "$taint_pre" --arg taint_post "$taint_post" \
      --argjson exit_code "$rc" --argjson reject_count "$reject_count" \
      --argjson gate_complete "$gate_complete" \
      --argjson four_device_identity "$four_device_identity" \
      --argjson per_card_compute "$per_card_compute" \
      --argjson four_device_peer_read "$four_device_peer_read" \
      --argjson four_rank_xccl_allreduce "$four_rank_xccl_allreduce" \
      --argjson repo_postflight "$repo_postflight" \
      --argjson atomic_lock_handoff "$atomic_lock_handoff" \
      --argjson torch_runtime_coherent "$torch_runtime_coherent" '{
        schema: "neural-download-qwen38-postreboot-hardware-gate-v2",
        passed: ($exit_code == 0 and $gate_complete and $reject_count == 0 and
          $taint_pre == "0" and $taint_post == "0" and
          $four_device_identity and $per_card_compute and
          $four_device_peer_read and $four_rank_xccl_allreduce and
          $repo_postflight and $atomic_lock_handoff and
          $torch_runtime_coherent),
        exit_code: $exit_code,
        gate_complete: $gate_complete,
        failure_stage: $failure_stage,
        started_utc: $started_utc,
        completed_utc: $completed_utc,
        host: {
          boot_id: $boot_id,
          kernel: $kernel,
          taint_pre: $taint_pre,
          taint_post: $taint_post
        },
        repo_head: $repo_head,
        kernel_journal_scope: {
          after_cursor: $journal_cursor,
          reject_pattern: $reject_pattern
        },
        gates: {
          four_device_identity: $four_device_identity,
          per_card_compute: $per_card_compute,
          four_device_peer_read: $four_device_peer_read,
          four_rank_xccl_allreduce: $four_rank_xccl_allreduce,
          repo_postflight: $repo_postflight,
          atomic_lock_handoff: $atomic_lock_handoff,
          torch_runtime_coherent: $torch_runtime_coherent,
          selector_and_mask_combined: false,
          kernel_reject_events: $reject_count
        },
        next_gate: "exact-current TP1 untreated control performs a model identity check and exact canary before timing"
      }' >"$result_root/summary.json.tmp"; then
      [[ $rc -ne 0 ]] || rc=95
    elif ! mv -f -- "$result_root/summary.json.tmp" "$result_root/summary.json"; then
      [[ $rc -ne 0 ]] || rc=95
    fi
    if ! printf 'exit_status=%s\n' "$rc" >"$result_root/final.status.tmp" ||
        ! mv -f -- "$result_root/final.status.tmp" "$result_root/final.status"; then
      [[ $rc -ne 0 ]] || rc=96
    fi
    write_manifest
    manifest_rc=$?
    if [[ $manifest_rc -ne 0 ]]; then
      rc=97
      mark_summary_failed "$rc"
      printf 'exit_status=%s\n' "$rc" >"$result_root/final.status.tmp"
      mv -f -- "$result_root/final.status.tmp" "$result_root/final.status"
      write_manifest
    fi
    sync "$result_root"
    sync_rc=$?
    if [[ $sync_rc -ne 0 ]]; then
      rc=98
      mark_summary_failed "$rc"
      printf 'exit_status=%s\n' "$rc" >"$result_root/final.status.tmp"
      mv -f -- "$result_root/final.status.tmp" "$result_root/final.status"
      write_manifest
      sync "$result_root"
    fi
  fi
  exit "$rc"
}
trap finalize EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 129' HUP

[[ -r $sudo_pass_file ]] || die 'sudo password file is unreadable'
for command_name in awk cmp date docker env find findmnt flock fuser git grep jq \
  journalctl ldd pgrep readlink realpath rg sed sha256sum sort sync tail timeout wc \
  uname xargs xpu-smi; do
  command -v "$command_name" >/dev/null || die "$command_name is required"
done
[[ $(</proc/sys/kernel/random/boot_id) == "$expected_boot_id" ]] ||
  die 'boot identity changed; preregister a new health gate'
[[ $(uname -r) == "$expected_kernel" ]] || die 'host kernel changed'
taint_pre=$(</proc/sys/kernel/tainted)
[[ $taint_pre == 0 ]] || die 'kernel is tainted'
[[ -x $python && -f $probe && -f $torch_xpu_lib && -f $venv_sycl_lib &&
   -f $venv_ccl1_lib && -f $venv_ccl2_lib && -f $venv_ur_loader &&
   -x $peer_binary && -x $sycl_ls ]] ||
  die 'health tool is absent'
check_sha256 "$python" "$expected_python_sha256"
check_sha256 "$probe" "$expected_probe_sha256"
check_sha256 "$torch_xpu_lib" "$expected_torch_xpu_sha256"
check_sha256 "$venv_sycl_lib" "$expected_venv_sycl_sha256"
check_sha256 "$venv_ccl1_lib" "$expected_venv_ccl1_sha256"
check_sha256 "$venv_ccl2_lib" "$expected_venv_ccl2_sha256"
check_sha256 "$venv_ur_loader" "$expected_venv_ur_loader_sha256"
check_sha256 "$peer_binary" "$expected_peer_sha256"
check_sha256 "$sycl_ls" "$expected_sycl_ls_sha256"

if timeout --signal=TERM --kill-after=5s 20s sudo -S -p '' -v \
    <"$sudo_pass_file"; then
  sudo_ready=true
else
  die 'sudo authentication preflight failed'
fi

repo_status_pre=$(git -C "$repo" status --porcelain=v1 --untracked-files=all) ||
  die 'lab repository status check failed'
[[ -z $repo_status_pre ]] ||
  die 'lab repository must be clean'
[[ $(git -C "$repo" branch --show-current) == main ]] || die 'lab must be on main'
repo_head=$(git -C "$repo" rev-parse HEAD)
[[ $(git -C "$repo" rev-parse origin/main) == "$repo_head" ]] ||
  die 'local main must equal origin/main'
live_head=$(timeout --signal=TERM --kill-after=5s 30s \
  git -C "$repo" ls-remote --exit-code origin refs/heads/main |
  awk 'NR == 1 {print $1}')
[[ $live_head == "$repo_head" ]] || die 'local main must equal live origin/main'

[[ ! -e $result_root ]] || die "result root already exists: $result_root"
result_parent=$(dirname -- "$result_root")
mkdir -p -- "$result_parent"
[[ $(findmnt -n -o FSTYPE --target "$result_parent") == ext4 ]] ||
  die 'health evidence must be on ext4'
mkdir -- "$result_root"
result_root_created=true
started_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)
printf '%s\n' "$started_utc" >"$result_root/started-utc.txt"
printf '%s\n' "$repo_head" >"$result_root/repo-head.txt"
printf '%s\n' "$taint_pre" >"$result_root/kernel-taint.pre.txt"
uname -a >"$result_root/uname.txt"
cp -- "$script_path" "$result_root/hardware-gate.sh"
sha256sum "$script_path" "$python" "$probe" "$torch_xpu_lib" \
  "$venv_sycl_lib" "$venv_ccl1_lib" "$venv_ccl2_lib" \
  "$venv_ur_loader" "$peer_binary" "$sycl_ls" \
  >"$result_root/tool-identities.sha256"
failure_stage=torch-runtime-loader-preflight
check_torch_loader_resolution
torch_runtime_coherent=true

if runtime_variable_names=$(env | sed 's/=.*//' | LC_ALL=C sort -u); then
  :
else
  die 'environment-name collection failed'
fi
if inherited_runtime_output=$(printf '%s\n' "$runtime_variable_names" |
    rg '^(ONEAPI_.*|ZE_.*|ZES_.*|SYCL_.*|UR_.*|XPU_.*|PYTHONPATH|PYTHONHOME|LD_PRELOAD|LD_LIBRARY_PATH|CCL_.*|ONECCL_.*|FI_.*|I_MPI_.*|MPI_.*|PMI_.*|PMIX_.*|TORCH_XCCL_.*|VLLM_.*)$'); then
  inherited_runtime_scan_rc=0
else
  inherited_runtime_scan_rc=$?
fi
[[ $inherited_runtime_scan_rc -eq 0 || $inherited_runtime_scan_rc -eq 1 ]] ||
  die 'inherited runtime environment scan failed'
inherited_runtime_variables=()
if [[ $inherited_runtime_scan_rc -eq 0 ]]; then
  mapfile -t inherited_runtime_variables <<<"$inherited_runtime_output"
fi
: >"$result_root/inherited-runtime-variable-names.txt"
if [[ ${#inherited_runtime_variables[@]} -gt 0 ]]; then
  printf '%s\n' "${inherited_runtime_variables[@]}" \
    >>"$result_root/inherited-runtime-variable-names.txt"
fi
[[ ${#inherited_runtime_variables[@]} -eq 0 ]] ||
  die 'hardware gate inherited accelerator/runtime controls'

timeout --signal=TERM --kill-after=5s 30s \
  journalctl -b -k -n 1 --show-cursor --no-pager -o short-iso \
  >"$result_root/kernel-baseline.log"
journal_cursor=$(sed -n 's/^-- cursor: //p' "$result_root/kernel-baseline.log" |
  tail -1)
[[ -n $journal_cursor ]] || die 'failed to capture kernel cursor'

muse_lock_file=/run/lock/muse-glimmer-gpu-exclusive.lock
host_lock_file=/tmp/b70-benchmark.lock
[[ -n ${QWEN_CURRENT_MUSE_LOCK_FD:-} &&
   -n ${QWEN_CURRENT_HOST_LOCK_FD:-} &&
   -n ${QWEN_CURRENT_GPU_LEASE_FDS:-} ]] ||
  die 'hardware gate requires an atomic parent campaign lock handoff'
validate_inherited_lock "$QWEN_CURRENT_MUSE_LOCK_FD" "$muse_lock_file"
validate_inherited_lock "$QWEN_CURRENT_HOST_LOCK_FD" "$host_lock_file"
gpu_lease_dir=/run/user/$(id -u)/qwen36-b70-gpu-leases
mkdir -p -- "$gpu_lease_dir"
declare -a gpu_lease_fds=()
IFS=',' read -r -a inherited_gpu_lease_fds <<<"$QWEN_CURRENT_GPU_LEASE_FDS"
[[ ${#inherited_gpu_lease_fds[@]} -eq 4 ]] ||
  die 'hardware gate requires four inherited GPU lease descriptors'
for device in 0 1 2 3; do
  validate_inherited_lock "${inherited_gpu_lease_fds[$device]}" \
    "$gpu_lease_dir/gpu${device}.lock"
done
atomic_lock_handoff=true

failure_stage=host-idle-preflight
if timeout --signal=TERM --kill-after=5s 30s sudo -S -p '' docker ps -q \
    >"$result_root/docker-running-containers.pre.txt" \
    2>"$result_root/docker-ps.pre.stderr" \
    <"$sudo_pass_file"; then
  docker_ps_rc=0
else
  docker_ps_rc=$?
fi
printf '%s\n' "$docker_ps_rc" >"$result_root/docker-ps.pre.rc"
[[ $docker_ps_rc -eq 0 ]] || die 'Docker running-container scan failed'
[[ ! -s $result_root/docker-running-containers.pre.txt ]] ||
  die 'a Docker container is running'
if pgrep -af '[E]ngineCore|[v]llm serve|[l]lama-server' \
    >"$result_root/model-processes.pre.log" \
    2>"$result_root/model-processes.pre.stderr"; then
  model_pgrep_rc=0
else
  model_pgrep_rc=$?
fi
printf '%s\n' "$model_pgrep_rc" >"$result_root/model-processes.pre.rc"
if [[ $model_pgrep_rc -eq 0 ]]; then
  die 'a model process is running'
elif [[ $model_pgrep_rc -ne 1 ]]; then
  die 'model-process scan failed'
fi
mapfile -t render_nodes < <(find /dev/dri -maxdepth 1 -type c \
  -name 'renderD*' -print | sort)
[[ ${#render_nodes[@]} -eq 4 ]] || die 'expected four render nodes'
check_render_idle pre || die 'render-node occupancy scan failed or found a holder'

failure_stage=four-device-identity
run_capture xpu-discovery timeout --signal=TERM --kill-after=5s 20s \
  env -u ONEAPI_DEVICE_SELECTOR -u ZE_AFFINITY_MASK \
    -u SYCL_DEVICE_FILTER -u SYCL_DEVICE_ALLOWLIST -u UR_DEVICE_SELECTORS \
    xpu-smi discovery -j
jq -e '
  .device_list as $devices |
  ($devices | length) == 4 and
  ($devices | map(.device_name == "Intel(R) Arc(TM) Pro B70 Graphics") | all) and
  (($devices | sort_by(.device_id) |
    map([.device_id, .pci_bdf_address, .uuid])) == [
    [0, "0000:23:00.0", "00000000-0000-0023-0000-0000e2238086"],
    [1, "0000:27:00.0", "00000000-0000-0027-0000-0000e2238086"],
    [2, "0000:43:00.0", "00000000-0000-0043-0000-0000e2238086"],
    [3, "0000:47:00.0", "00000000-0000-0047-0000-0000e2238086"]
  ])
' "$result_root/xpu-discovery.log" >"$result_root/xpu-discovery.check"
four_device_identity=true

expected_sycl_uuids=(
  868023e2-0000-0000-2300-000000000000
  868023e2-0000-0000-2700-000000000000
  868023e2-0000-0000-4300-000000000000
  868023e2-0000-0000-4700-000000000000
)
failure_stage=per-card-compute
for physical_device in 0 1 2 3; do
  run_capture "sycl-identity-gpu${physical_device}" \
    timeout --signal=TERM --kill-after=10s 60s \
    env -u ONEAPI_DEVICE_SELECTOR -u SYCL_DEVICE_FILTER \
    -u SYCL_DEVICE_ALLOWLIST -u UR_DEVICE_SELECTORS -u PYTHONPATH \
    -u PYTHONHOME -u LD_PRELOAD \
    LD_LIBRARY_PATH="$oneapi_ld_library_path" \
    ZE_AFFINITY_MASK="$physical_device" "$sycl_ls" --verbose
  awk '
    /^Platform \[#1\]:/ {inside=1; next}
    /^Platform \[#2\]:/ {inside=0}
    inside {print}
  ' "$result_root/sycl-identity-gpu${physical_device}.log" \
    >"$result_root/sycl-level-zero-gpu${physical_device}.log"
  [[ $(grep -c '^[[:space:]]*Device \[#[0-9][0-9]*\]:' \
      "$result_root/sycl-level-zero-gpu${physical_device}.log") -eq 1 ]] ||
    die "ZE mask $physical_device did not expose exactly one Level-Zero device"
  grep -Eq \
    "^[[:space:]]*UUID[[:space:]]*: ${expected_sycl_uuids[$physical_device]}$" \
    "$result_root/sycl-level-zero-gpu${physical_device}.log" ||
    die "ZE mask $physical_device did not bind the expected UUID"
  run_capture "compute-gpu${physical_device}" \
    timeout --signal=TERM --kill-after=10s 40s \
    env -u ONEAPI_DEVICE_SELECTOR -u SYCL_DEVICE_FILTER \
    -u SYCL_DEVICE_ALLOWLIST -u UR_DEVICE_SELECTORS -u PYTHONPATH \
    -u PYTHONHOME -u LD_PRELOAD \
    LD_LIBRARY_PATH="$torch_ld_library_path" PYTHONNOUSERSITE=1 \
    PYTHONSAFEPATH=1 PYTHONDONTWRITEBYTECODE=1 \
    ZE_AFFINITY_MASK="$physical_device" \
    "$python" -c '
import torch
assert torch.xpu.is_available()
assert torch.xpu.device_count() == 1
torch.xpu.set_device(0)
x = torch.ones((1024, 1024), device="xpu")
y = float((x + 1).sum().cpu().item())
torch.xpu.synchronize()
assert y == 2097152.0
print("device_count 1")
print("ok 2097152.0")
'
done
capture_kernel_delta || die 'kernel rejected a per-card compute gate'
per_card_compute=true

failure_stage=four-device-peer-read
run_capture peer-read timeout --signal=TERM --kill-after=15s 180s \
  env -u ONEAPI_DEVICE_SELECTOR -u SYCL_DEVICE_FILTER \
  -u SYCL_DEVICE_ALLOWLIST -u UR_DEVICE_SELECTORS -u PYTHONPATH \
  -u PYTHONHOME -u LD_PRELOAD \
  LD_LIBRARY_PATH="$oneapi_ld_library_path" \
  ZE_AFFINITY_MASK=0,1,2,3 "$peer_binary"
grep -Fx 'peer kernel read ok across 4 devices' \
  "$result_root/peer-read.log" >/dev/null || die 'peer-read oracle changed'
capture_kernel_delta || die 'kernel rejected the peer-read gate'
four_device_peer_read=true

failure_stage=four-rank-xccl-allreduce
run_capture xccl-allreduce timeout --signal=TERM --kill-after=15s 180s \
  env -u ONEAPI_DEVICE_SELECTOR -u SYCL_DEVICE_FILTER \
  -u SYCL_DEVICE_ALLOWLIST -u UR_DEVICE_SELECTORS -u PYTHONPATH \
  -u PYTHONHOME -u LD_PRELOAD \
  LD_LIBRARY_PATH="$torch_ld_library_path" PYTHONNOUSERSITE=1 \
  PYTHONSAFEPATH=1 PYTHONDONTWRITEBYTECODE=1 \
  ZE_AFFINITY_MASK=0,1,2,3 CCL_ATL_TRANSPORT=ofi CCL_TOPO_P2P_ACCESS=1 \
  FI_TCP_IFACE=eth0 CCL_KVS_IFACE=eth0 TORCH_XCCL_ASYNC_ERROR_HANDLING=1 \
  "$python" -m torch.distributed.run --standalone --nproc_per_node=4 \
  "$probe" allreduce
for rank in 0 1 2 3; do
  require_one_fixed_marker "rank $rank init ok" \
    "$result_root/xccl-allreduce.log"
  require_one_fixed_marker "rank $rank barrier ok" \
    "$result_root/xccl-allreduce.log"
  require_one_fixed_marker "rank $rank allreduce ok 4.0" \
    "$result_root/xccl-allreduce.log"
done
capture_kernel_delta || die 'kernel rejected the XCCL gate'
four_rank_xccl_allreduce=true

failure_stage=host-postflight
sleep 5
run_capture xpu-discovery-post timeout --signal=TERM --kill-after=5s 20s \
  env -u ONEAPI_DEVICE_SELECTOR -u ZE_AFFINITY_MASK \
    -u SYCL_DEVICE_FILTER -u SYCL_DEVICE_ALLOWLIST -u UR_DEVICE_SELECTORS \
    xpu-smi discovery -j
cmp -s "$result_root/xpu-discovery.log" "$result_root/xpu-discovery-post.log" ||
  die 'XPU discovery identity changed across the gate'
capture_kernel_delta || die 'kernel journal is not clean after the health gate'
check_render_idle post || die 'render-node postflight failed or found a holder'

taint_post=$(</proc/sys/kernel/tainted)
printf '%s\n' "$taint_post" >"$result_root/kernel-taint.post.txt"
[[ $taint_post == 0 ]] || die 'kernel became tainted during the health gate'
repo_status_post=$(git -C "$repo" status --porcelain=v1 --untracked-files=all) ||
  die 'lab repository postflight status check failed'
[[ -z $repo_status_post ]] ||
  die 'lab repository became dirty during the health gate'
[[ $(git -C "$repo" branch --show-current) == main ]] ||
  die 'lab repository left main during the health gate'
[[ $(git -C "$repo" rev-parse HEAD) == "$repo_head" ]] ||
  die 'lab commit changed during the health gate'
[[ $(git -C "$repo" rev-parse origin/main) == "$repo_head" ]] ||
  die 'local origin/main changed during the health gate'
live_head_post=$(timeout --signal=TERM --kill-after=5s 30s \
  git -C "$repo" ls-remote --exit-code origin refs/heads/main |
  awk 'NR == 1 {print $1}')
[[ $live_head_post == "$repo_head" ]] ||
  die 'live origin/main changed during the health gate'
repo_postflight=true

if timeout --signal=TERM --kill-after=5s 30s sudo -S -p '' docker ps -q \
    >"$result_root/docker-running-containers.post.txt" \
    2>"$result_root/docker-ps.post.stderr" \
    <"$sudo_pass_file"; then
  docker_ps_post_rc=0
else
  docker_ps_post_rc=$?
fi
printf '%s\n' "$docker_ps_post_rc" >"$result_root/docker-ps.post.rc"
[[ $docker_ps_post_rc -eq 0 ]] || die 'Docker postflight scan failed'
[[ ! -s $result_root/docker-running-containers.post.txt ]] ||
  die 'a Docker container appeared during the health gate'

failure_stage=complete
gate_complete=true
