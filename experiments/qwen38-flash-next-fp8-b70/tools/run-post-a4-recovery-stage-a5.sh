#!/usr/bin/env bash
set -Eeuo pipefail

root=/home/steve/llm-optimizations
lane="${root}/experiments/qwen38-flash-next-fp8-b70"
out=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/post-a4-recovery-qualification-20260828-stage-a5
health="${root}/scripts/check-qwen36-xpu-xccl-health.sh"
runtime_clear="${lane}/tools/check-q38-recovery-runtime-clear.sh"
journal_start_epoch=$(date +%s)

write_atomic() {
  local path=$1 value=$2 temporary
  temporary="${path}.tmp.$$"
  printf '%s\n' "$value" >"$temporary"
  mv "$temporary" "$path"
}

capture_final() {
  local rc=$? device
  set +e
  mkdir -p "$out"
  write_atomic "${out}/command.rc" "$rc"
  journalctl -k --since "@${journal_start_epoch}" --no-pager \
    >"${out}/kernel-journal.log" 2>"${out}/kernel-journal.err"
  write_atomic "${out}/kernel-journal.rc" "$?"
  timeout 30s xpu-smi discovery -j >"${out}/xpu-discovery-after.json" \
    2>"${out}/xpu-discovery-after.err"
  for device in 0 1 2 3; do
    timeout 30s xpu-smi stats -d "$device" -j \
      >"${out}/xpu-stats-after-${device}.json" \
      2>"${out}/xpu-stats-after-${device}.err"
  done
  pgrep -af 'vllm|Qwen3.8-Flash-Next|torch.distributed|xccl_probe' \
    >"${out}/processes-after.txt" || true
  ss -ltnp >"${out}/listeners-after.txt" 2>&1 || true
  find "$out" -maxdepth 1 -type f ! -name evidence.sha256 -printf '%f\0' \
    | sort -z | xargs -0 -r -I{} sha256sum "${out}/{}" \
    >"${out}/evidence.sha256"
  exit "$rc"
}

[[ $# == 0 ]] || { printf 'FAIL: this gate takes no arguments\n' >&2; exit 2; }
[[ ! -e "$out" ]] || { printf 'FAIL: refusing to reuse %s\n' "$out" >&2; exit 1; }
mkdir -p "$out"
trap capture_final EXIT
write_atomic "${out}/journal-start-epoch.txt" "$journal_start_epoch"

cd "$root"
git status --short --branch >"${out}/git-status.txt"
[[ -z "$(git status --porcelain)" ]] || { printf 'FAIL: repository is dirty\n' >&2; exit 1; }
git rev-parse HEAD >"${out}/repo-head.txt"
git -C /home/steve/src/vllm-current-main rev-parse HEAD >"${out}/vllm-head.txt"
git -C /home/steve/src/vllm-current-main status --porcelain >"${out}/vllm-status.txt"
git -C /home/steve/src/vllm-xpu-kernels rev-parse HEAD >"${out}/kernels-head.txt"
git -C /home/steve/src/vllm-xpu-kernels status --porcelain --untracked-files=no \
  >"${out}/kernels-status.txt"
[[ "$(<"${out}/vllm-head.txt")" == 1372c62d975c554f4b465c8299bc5f3295301ceb ]]
[[ "$(<"${out}/kernels-head.txt")" == ad25aa9f69a2171612b9c6b83dfa82c69559f9e4 ]]
[[ ! -s "${out}/vllm-status.txt" && ! -s "${out}/kernels-status.txt" ]]

cat /proc/sys/kernel/random/boot_id >"${out}/boot-id.txt"
[[ "$(<"${out}/boot-id.txt")" == 3ce525f4-de7f-46f6-a9df-3b56af7301cf ]]
awk '/MemAvailable|SwapFree/ {print}' /proc/meminfo >"${out}/host-memory.txt"
mem_available=$(awk '/MemAvailable/ {print $2}' "${out}/host-memory.txt")
(( mem_available >= 110100480 )) || { printf 'FAIL: host-memory floor\n' >&2; exit 1; }
findmnt -no SOURCE,FSTYPE,OPTIONS --target /mnt/usb-models \
  >"${out}/external-mount.txt"
grep -Eq '^/dev/sda2 fuseblk rw,' "${out}/external-mount.txt"

"$runtime_clear" >"${out}/runtime-clear.txt"
timeout 30s xpu-smi discovery -j >"${out}/xpu-discovery-before.json"
jq -e '.device_list | map([.device_id, .device_name, .pci_bdf_address, .drm_device]) == [
  [0, "Intel(R) Arc(TM) Pro B70 Graphics", "0000:23:00.0", "/dev/dri/card3"],
  [1, "Intel(R) Arc(TM) Pro B70 Graphics", "0000:27:00.0", "/dev/dri/card4"],
  [2, "Intel(R) Arc(TM) Pro B70 Graphics", "0000:43:00.0", "/dev/dri/card0"],
  [3, "Intel(R) Arc(TM) Pro B70 Graphics", "0000:47:00.0", "/dev/dri/card2"]
]' "${out}/xpu-discovery-before.json" >/dev/null
for device in 0 1 2 3; do
  timeout 30s xpu-smi stats -d "$device" -j >"${out}/xpu-stats-before-${device}.json"
  memory=$(jq -er 'first(.device_level[] |
    select(.metrics_type == "XPUM_STATS_MEMORY_USED") | .value) |
    select(type == "number")' "${out}/xpu-stats-before-${device}.json")
  awk -v value="$memory" 'BEGIN { exit !(value < 256) }'
done

timeout --signal=TERM --kill-after=10s 300s env \
  ROOT="$root" PYTHON=/home/steve/.venvs/vllm-xpu/bin/python \
  PHYSICAL_DEVICES=0,1,2,3 XCCL_DEVICES=0,1,2,3 XCCL_NPROC=4 \
  TIMEOUT_S=120 FI_TCP_IFACE=lo CCL_KVS_IFACE=lo \
  "$health" >"${out}/health.log" 2>"${out}/health.err"
for rank in 0 1 2 3; do
  grep -Fq "rank ${rank} allreduce ok 4.0" "${out}/health.log"
done

ONEAPI_DEVICE_SELECTOR=level_zero:0,1,2,3 \
  /home/steve/.venvs/vllm-xpu/bin/python - <<'PY' >"${out}/peer-access.txt"
import torch

n = torch.xpu.device_count()
print("device_count", n, flush=True)
assert n == 4
for source in range(n):
    for target in range(n):
        if source == target:
            continue
        value = torch.xpu.can_device_access_peer(source, target)
        print("peer", source, target, value, flush=True)
        assert value
PY

journalctl -k --since "@${journal_start_epoch}" --no-pager \
  >"${out}/kernel-journal-preliminary.log"
! grep -Eqi 'xe 0000:(23|27|43|47):00\.0.*(reset|fault|timeout|timed out|fatal|wedged|failed)' \
  "${out}/kernel-journal-preliminary.log"
! grep -Eqi 'out of memory|killed process|I/O error|TTM.*(fail|error)' \
  "${out}/kernel-journal-preliminary.log"
write_atomic "${out}/gates-passed.txt" \
  'PASS post-A4 source storage per-card peer XCCL and journal gates'
printf 'PASS: post-A4 Stage A5 recovery gate\n'
