#!/usr/bin/env bash
# Launch a frozen Flash-Next attempt the way the September deterministic-line
# runs were launched by hand: preflight, host reset, validate, launch the root
# host wrapper in the background, then start the attempt's driver.
#
#   q38-launch-frozen-attempt.sh <attempt> <driver-script> [log-dir]
#
# <attempt> names the packet (run-q38-a<attempt>-host-controlled.sh in this
# directory); <driver-script> is the client or diagnostic driver to start once
# the wrapper is up (it must wait for the server itself). Logs go to
# <log-dir> (default /tmp/q38-attempt-logs). The sudo password is read from
# /home/steve/SUDOPASSWORD.txt and never printed.
#
# Preflight (all fail closed): no vLLM engine processes, no listener on the
# packet's port, no kernel GPU event since the previous attempt, at least
# 220 GB free on the root NVMe, model mounts as the wrapper expects. Host
# reset: swap off/on (the wrapper refuses any used swap), page cache dropped
# (a warm cache plus PLE pinning trips the memory-PSI guard). Then the
# wrapper's own static validation (Q38_A<N>_HOST_VALIDATE_ONLY=1) must pass.
set -Eeuo pipefail

attempt=${1:?attempt number}
driver=${2:?driver script}
log_dir=${3:-/tmp/q38-attempt-logs}
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
password_file=/home/steve/SUDOPASSWORD.txt
wrapper="${script_dir}/run-q38-a${attempt}-host-controlled.sh"
root() { sudo -S -p '' "$@" <"${password_file}"; }
fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }

[[ -x "$wrapper" ]] || fail "no host wrapper for attempt ${attempt}: ${wrapper}"
[[ -x "$driver" ]] || fail "driver is not executable: ${driver}"
[[ -r "$password_file" ]] || fail "sudo password file is not readable"
mkdir -p "$log_dir"
# (grep exits 1 when a form is absent; under pipefail that must not abort.)
port=$(grep -h -o 'PORT=[0-9]*' "${script_dir}"/launch-*-a"${attempt}"-*.sh 2>/dev/null | head -1 | cut -d= -f2 || true)
[[ "$port" =~ ^[0-9]+$ ]] || fail "cannot determine the packet port"

# Preflight. The process check uses `ps -eo args` with a bracketed pattern so
# this script's own command line cannot match it.
if ps -eo args | grep -q "[E]ngineCore\|[W]orker_TP\|[v]llm serve"; then
  fail "a vLLM engine is still running; wait for the previous wrapper's .rc file"
fi
ss -ltn | grep -q ":${port} " && fail "port ${port} already has a listener"
avail=$(df --output=avail -B1 / | tail -1)
(( avail >= 220000000000 )) || fail "root NVMe free space ${avail} < 220000000000"
[[ "$(findmnt -no SOURCE,FSTYPE --target /mnt/usb-models)" == "/dev/sda2 fuseblk" ]] || fail "evidence mount changed"
[[ "$(findmnt -no SOURCE,FSTYPE --target /mnt/fast-ai)" == "/dev/nvme0n1p2 ext4" ]] || fail "model mount changed"
if root journalctl -k --since "-6h" --no-pager 2>/dev/null | grep -Eiq 'xe 0000:(23|27|43|47):00\.0.*(reset|fault|timeout|timed out|fatal|wedged|failed)'; then
  fail "kernel GPU event in the last six hours; inspect before launching"
fi

# Host reset: unused swap, cold page cache.
root sh -c 'swapoff /swap.img; swapon --priority -1 /swap.img; sync; echo 1 > /proc/sys/vm/drop_caches'
swap_used=$(swapon --show=NAME,USED --noheadings --raw --bytes | awk '$1 == "/swap.img" {print $2}')
[[ "$swap_used" == 0 ]] || fail "swap still in use after reset: ${swap_used} bytes"
mem_available_kib=$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)
(( mem_available_kib >= 120000000 )) || fail "MemAvailable ${mem_available_kib} KiB < 120000000 after cache drop"

# The wrapper's own static validation, then the launch.
validate_var="Q38_A${attempt}_HOST_VALIDATE_ONLY"
root env "${validate_var}=1" "$wrapper" | tail -1
host_log="${log_dir}/a${attempt}-host.log"
driver_log="${log_dir}/a${attempt}-driver.log"
( root "$wrapper" >"$host_log" 2>&1 & )
sleep 3
ps -eo args | grep -q "[r]un-q38-a${attempt}-host-controlled.sh" || fail "host wrapper did not stay up; see ${host_log}"
( nohup bash "$driver" >"$driver_log" 2>&1 & )
sleep 2
printf 'launched attempt %s on port %s at %s; host log %s; driver log %s\n' \
  "$attempt" "$port" "$(date +%H:%M:%S)" "$host_log" "$driver_log"
