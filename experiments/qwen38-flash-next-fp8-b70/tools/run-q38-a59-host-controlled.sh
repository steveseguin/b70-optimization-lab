#!/usr/bin/env bash
set -Eeuo pipefail

supervisor=/home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/tools/supervise-tp4-mtp0-2304-ple-only-a59-fullgraph-w13n32.sh
expected_supervisor=770d9fc44f2bb7cf3afd4b7ee582e77c76ebca5fd194a574c56cc073eac0a554
aspm_policy=/sys/module/pcie_aspm/parameters/policy
original_policy=""
original_swap_path=""
original_swap_priority=""
child=""
swap_restore_required=0
aspm_restore_required=0

restore_host() {
  local rc=$? restore_rc=0 restored_policy restored_swap
  set +e
  if [[ "$child" =~ ^[1-9][0-9]*$ ]] && kill -0 "$child" 2>/dev/null; then
    kill -TERM "$child" 2>/dev/null
    for _ in $(seq 1 30); do
      kill -0 "$child" 2>/dev/null || break
      sleep 1
    done
    kill -KILL "$child" 2>/dev/null || true
    for _ in $(seq 1 10); do
      kill -0 "$child" 2>/dev/null || break
      sleep 1
    done
    if kill -0 "$child" 2>/dev/null; then
      printf 'FAIL: A59 child remained live after bounded teardown\n' >&2
      restore_rc=1
    else
      wait "$child" 2>/dev/null || true
    fi
  fi
  if (( aspm_restore_required == 1 )) && [[ -n "$original_policy" ]]; then
    printf '%s\n' "$original_policy" >"$aspm_policy" || restore_rc=1
    restored_policy=$(sed -n 's/.*\[\([^]]*\)\].*/\1/p' "$aspm_policy")
    [[ "$restored_policy" == "$original_policy" ]] || restore_rc=1
  fi
  if (( swap_restore_required == 1 )) && [[ -n "$original_swap_path" ]]; then
    swapon --priority "$original_swap_priority" "$original_swap_path" || restore_rc=1
    restored_swap=$(swapon --show=NAME,USED,PRIO --noheadings --raw --bytes | \
      awk -v path="$original_swap_path" '$1 == path {print $1, $3}')
    [[ "$restored_swap" == "$original_swap_path $original_swap_priority" ]] || restore_rc=1
  fi
  if (( restore_rc != 0 )); then
    printf 'FAIL: A59 host-control restoration was incomplete\n' >&2
    rc=71
  fi
  trap - EXIT
  exit "$rc"
}
trap restore_host EXIT
trap 'exit 130' INT TERM HUP

[[ $EUID == 0 ]] || { printf 'FAIL: A59 host control must run as root\n' >&2; exit 1; }
[[ $# == 0 ]] || { printf 'FAIL: A59 host control takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$supervisor" | cut -d' ' -f1)" == "$expected_supervisor" ]] || {
  printf 'FAIL: A59 supervisor hash changed\n' >&2
  exit 1
}
[[ "$(findmnt -no SOURCE,FSTYPE --target /mnt/usb-models)" == "/dev/sda2 fuseblk" ]] || {
  printf 'FAIL: A59 evidence mount is not /dev/sda2 fuseblk\n' >&2
  exit 1
}
[[ "$(findmnt -no SOURCE,FSTYPE --target /mnt/fast-ai)" == "/dev/nvme0n1p2 ext4" ]] || {
  printf 'FAIL: A59 model mount is not /dev/nvme0n1p2 ext4\n' >&2
  exit 1
}
original_policy=$(sed -n 's/.*\[\([^]]*\)\].*/\1/p' "$aspm_policy")
[[ -n "$original_policy" ]] || { printf 'FAIL: cannot identify original ASPM policy\n' >&2; exit 1; }
mapfile -t active_swaps < <(swapon --show=NAME,USED,PRIO --noheadings --raw --bytes)
[[ "${#active_swaps[@]}" == 1 ]] || { printf 'FAIL: A59 requires exactly one active swap device\n' >&2; exit 1; }
read -r original_swap_path original_swap_used original_swap_priority <<<"${active_swaps[0]}"
[[ "$original_swap_path" == /swap.img && "$original_swap_used" == 0 && \
   "$original_swap_priority" =~ ^-?[0-9]+$ ]] || {
  printf 'FAIL: A59 requires an unused /swap.img with a recorded priority\n' >&2
  exit 1
}
mem_available_kib=$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)
(( mem_available_kib >= 120000000 )) || { printf 'FAIL: A59 host-control memory floor failed\n' >&2; exit 1; }
if [[ "${Q38_A59_HOST_VALIDATE_ONLY:-0}" == 1 ]]; then
  printf 'PASS: A59 host-control static identity; ASPM=%s swap=%s used=%s priority=%s\n' \
    "$original_policy" "$original_swap_path" "$original_swap_used" "$original_swap_priority"
  exit 0
fi

swap_restore_required=1
swapoff "$original_swap_path"
aspm_restore_required=1
printf 'performance\n' >"$aspm_policy"
[[ "$(awk '/^SwapTotal:/ {print $2}' /proc/meminfo)" == 0 ]]
grep -Fq '[performance]' "$aspm_policy"
root_port_pci=$(lspci -vv -s 00:03.1)
nvme_pci=$(lspci -vv -s 01:00.0)
grep -Eq 'LnkCtl:[[:space:]]+ASPM Disabled' <<<"$root_port_pci"
grep -Eq 'LnkCtl:[[:space:]]+ASPM Disabled' <<<"$nvme_pci"
export Q38_A59_NVME_AER_BASELINE
export Q38_A59_ROOT_AER_BASELINE
export Q38_A59_NVME_SECTORS_READ_BASELINE
Q38_A59_NVME_AER_BASELINE=$(awk '$1 == "TOTAL_ERR_COR" {print $2}' \
  /sys/bus/pci/devices/0000:01:00.0/aer_dev_correctable)
Q38_A59_ROOT_AER_BASELINE=$(< /sys/bus/pci/devices/0000:00:03.1/aer_rootport_total_err_cor)
Q38_A59_NVME_SECTORS_READ_BASELINE=$(awk '$3 == "nvme0n1" {print $6}' /proc/diskstats)
[[ "$Q38_A59_NVME_AER_BASELINE" =~ ^[0-9]+$ && "$Q38_A59_ROOT_AER_BASELINE" =~ ^[0-9]+$ && \
   "$Q38_A59_NVME_SECTORS_READ_BASELINE" =~ ^[0-9]+$ ]] || {
  printf 'FAIL: A59 could not establish numeric AER baselines\n' >&2
  exit 1
}

runuser -u steve -- "$supervisor" &
child=$!
set +e
wait "$child"
rc=$?
set -e
child=""
exit "$rc"
