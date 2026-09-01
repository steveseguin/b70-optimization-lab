#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/launch-tp4-mtp0-4352-ple-only-a29-moe-m1-warps8.sh"
rewrite="${script_dir}/rewrite-a32-current-source-contract.py"
expected_base=6a624362e1ae1d4c4522fbc6cd88c6ac9e7da0da7998390c28333927c3aec5b0
expected_rewrite=8766a855ef13429bb4c8d6c6252a9ca3de82d7c59083436ee8e039e0a0581fb5
expected_source=8e4dc027709f45d3be941aa82b586410423b4406e493c81f897889a5ed2a4213
current_vllm=797769b34b6db5c934609b75dc04cc61ec66e5f9

derive() {
  Q38_A29_SOURCE_ONLY=1 "$base" | awk \
    -v rewrite="$rewrite" \
    -v current_vllm="$current_vllm" '
BEGIN {
  skip_forbidden_boot = 0
  skip_full_load_marker = 0
}
{
  if ($0 == "  boot_id=$(< /proc/sys/kernel/random/boot_id)") {
    skip_forbidden_boot = 1
    next
  }
  if (skip_forbidden_boot) {
    if ($0 ~ /^  mem_available_kib=/) {
      skip_forbidden_boot = 0
    } else {
      next
    }
  }
  if ($0 ~ /^  full_load_marker=/) {
    skip_full_load_marker = 1
    next
  }
  if (skip_full_load_marker) {
    if ($0 == "  exec 9>&-") {
      skip_full_load_marker = 0
    }
    next
  }
  gsub(/ple-only-a29-moe-m1-warps8/, "ple-only-a32-moe-m1-current")
  gsub(/q38-mtp0-ple-only-a29/, "q38-mtp0-ple-only-a32")
  gsub(/q38-ple-only-a29/, "q38-ple-only-a32")
  gsub(/q38-ple4k-a29/, "q38-ple4k-a32")
  gsub(/attempt29/, "attempt32")
  gsub(/ATTEMPT=29 PORT=19701/, "ATTEMPT=32 PORT=19704")
  gsub(/19701/, "19704")
  gsub(/Q38_A29_VALIDATE_ONLY/, "Q38_A32_VALIDATE_ONLY")
  gsub(/A29/, "A32")
  gsub(/d14396e27247c1b251da0ce24a0942772c4b002f/, current_vllm)
  gsub(/37791a9b20d0ce0d10e89f3930f9d0e8b7d7f743e1074691b39ed22a40e6adbb/, "73a880c3d2965bde6f02471fd9592862a89730142aa2ec31e40d45ea7c31da15")
  gsub(/rewrite-a29-kernel-workspace-contract.py/, "rewrite-a32-current-source-contract.py")
  if ($0 == "unset VLLM_XPU_PLE_UVA_PREFETCH") {
    print
    print "unset VLLM_XPU_QWEN4_EXP_HC_GROUPED_UP"
    next
  }
  if ($0 == "assert envs.VLLM_KV_CACHE_LAYOUT == '\''BLHNC'\''") {
    print
    print "assert envs.VLLM_XPU_QWEN4_EXP_HC_GROUPED_UP is False"
    next
  }
  print
}
'
}

[[ $# == 0 ]] || { printf 'FAIL: A32 launcher takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]] || {
  printf 'FAIL: A32 base launcher drifted\n' >&2
  exit 1
}
[[ "$(sha256sum "$rewrite" | cut -d' ' -f1)" == "$expected_rewrite" ]] || {
  printf 'FAIL: A32 rewrite helper drifted\n' >&2
  exit 1
}
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || {
  printf 'FAIL: A32 launcher source %s is not frozen %s\n' "$actual_source" "$expected_source" >&2
  exit 1
}
if [[ "${Q38_A32_SOURCE_ONLY:-0}" == 1 ]]; then derive; exit 0; fi
if [[ "${Q38_A32_VALIDATE_ONLY:-0}" != 1 ]]; then
  supervisor_pid=${Q38_A32_SUPERVISOR_PID:-}
  supervisor_starttime=${Q38_A32_SUPERVISOR_STARTTIME:-}
  [[ "$supervisor_pid" =~ ^[1-9][0-9]*$ && "$supervisor_starttime" =~ ^[1-9][0-9]*$ ]] || {
    printf 'FAIL: A32 runtime may be entered only by its frozen supervisor\n' >&2
    exit 1
  }
  [[ -r "/proc/${supervisor_pid}/stat" ]] || {
    printf 'FAIL: A32 supervisor process is absent\n' >&2
    exit 1
  }
  actual_starttime=$(awk '{ line=$0; sub(/^.*\) /, "", line); split(line, fields, " "); print fields[20] }' \
    "/proc/${supervisor_pid}/stat")
  [[ "$actual_starttime" == "$supervisor_starttime" ]] || {
    printf 'FAIL: A32 supervisor identity changed\n' >&2
    exit 1
  }
  supervisor_command=$(tr '\0' ' ' <"/proc/${supervisor_pid}/cmdline")
  [[ "$supervisor_command" == *"supervise-tp4-mtp0-4352-ple-only-a32-moe-m1-current.sh"* ]] || {
    printf 'FAIL: A32 runtime owner is not the frozen supervisor\n' >&2
    exit 1
  }
  expected_locks=(/tmp/b70-benchmark.lock /tmp/b70-gpu0.lock /tmp/b70-gpu1.lock /tmp/b70-gpu2.lock /tmp/b70-gpu3.lock)
  for index in 0 1 2 3 4; do
    [[ "$(readlink -f "/proc/${supervisor_pid}/fd/$((7 + index))")" == "${expected_locks[$index]}" ]] || {
      printf 'FAIL: A32 supervisor does not hold the complete host/GPU lock set\n' >&2
      exit 1
    }
  done
fi
source <(derive)
