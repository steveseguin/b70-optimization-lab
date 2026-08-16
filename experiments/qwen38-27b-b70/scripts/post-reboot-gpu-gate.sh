#!/usr/bin/env bash
set -euo pipefail

fail() {
    printf 'FAIL: %s\n' "$*" >&2
    exit 1
}

[[ -r /proc/sys/kernel/tainted ]] || fail 'cannot read kernel taint state'
taint=$(< /proc/sys/kernel/tainted)

# This host reproducibly emits one display-only dma_buf_vmap WARN from the KMS
# thread during boot. It sets TAINT_WARN (bit 9 / value 512) before any compute
# workload. Allow only that exact, audited warning; every other taint bit,
# additional WARNING, or missing KMS signature remains a hard failure.
if [[ ${taint} != 0 ]]; then
    (( (taint & ~512) == 0 )) || fail "kernel taint contains unexpected bits: ${taint}"
    boot_warnings=$(journalctl -k -b --no-pager 2>/dev/null | grep -c 'WARNING:' || true)
    kms_dma_warnings=$(journalctl -k -b --no-pager 2>/dev/null |
        grep -c 'WARNING: drivers/dma-buf/dma-buf.c:1612.*KMS thread' || true)
    [[ ${boot_warnings} == 1 && ${kms_dma_warnings} == 1 ]] || {
        fail "TAINT_WARN is not solely the audited one-time KMS dma_buf_vmap warning (warnings=${boot_warnings}, known=${kms_dma_warnings})"
    }
    printf 'WARN: allowing audited boot-only KMS dma_buf_vmap warning (taint=%s)\n' "${taint}" >&2
fi

command -v xpu-smi >/dev/null || fail 'xpu-smi is not installed'
discovery=$(xpu-smi discovery 2>&1) || fail 'xpu-smi discovery failed'
normal_count=$(grep -c 'Device State: normal' <<<"${discovery}" || true)
[[ ${normal_count} == 2 ]] || {
    printf '%s\n' "${discovery}" >&2
    fail "expected exactly two normal B70 devices, found ${normal_count}"
}

b70_count=$(grep -c 'Arc(TM) Pro B70' <<<"${discovery}" || true)
[[ ${b70_count} == 2 ]] || {
    printf '%s\n' "${discovery}" >&2
    fail "expected exactly two Intel Arc Pro B70 devices, found ${b70_count}"
}

if pgrep -x llama-server >/dev/null || pgrep -x llama-bench >/dev/null; then
    fail 'an existing llama.cpp GPU workload is active'
fi

kernel_log=$(journalctl -k -b --no-pager 2>/dev/null || true)
fault_pattern='Kernel-submitted job timed out|reset done|GuC.*tim(e|ed)[ -]?out|xe.*(device.?lost|fault|reset|hung|hang[: ]|tim(e|ed)[ -]?out)'
if grep -Eiq "${fault_pattern}" <<<"${kernel_log}"; then
    grep -Ei "${fault_pattern}" <<<"${kernel_log}" | tail -n 40 >&2
    fail 'current boot contains an Xe/GuC timeout, fault, reset, or hang'
fi

printf '%s\n' "${discovery}"
printf 'PASS: audited boot state, two normal B70s, no active llama.cpp workload, no current-boot Xe/GuC fault signature\n'
