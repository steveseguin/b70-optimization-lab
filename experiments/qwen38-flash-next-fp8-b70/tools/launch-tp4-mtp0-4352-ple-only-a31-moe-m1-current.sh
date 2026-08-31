#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/launch-tp4-mtp0-4352-ple-only-a29-moe-m1-warps8.sh"
rewrite="${script_dir}/rewrite-a31-current-source-contract.py"
expected_base=6a624362e1ae1d4c4522fbc6cd88c6ac9e7da0da7998390c28333927c3aec5b0
expected_rewrite=daa902d850632f33f07451b72a3f7b4c68df0eb07183b6dc3904de35d02f4d72
expected_source=b0bc8aea505dc02f24956fe7d7316a29131671cd4db7af922b43d473f11485ec
current_vllm=797769b34b6db5c934609b75dc04cc61ec66e5f9
rejected_boot=c36480de-9150-4182-9888-08c85d2d9de4
affinity_root=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/components/20260831-tp4-count2560-cpu-affinity-a1

derive() {
  Q38_A29_SOURCE_ONLY=1 "$base" | awk \
    -v rewrite="$rewrite" \
    -v current_vllm="$current_vllm" \
    -v rejected_boot="$rejected_boot" '
{
  gsub(/ple-only-a29-moe-m1-warps8/, "ple-only-a31-moe-m1-current")
  gsub(/q38-mtp0-ple-only-a29/, "q38-mtp0-ple-only-a31")
  gsub(/q38-ple-only-a29/, "q38-ple-only-a31")
  gsub(/q38-ple4k-a29/, "q38-ple4k-a31")
  gsub(/attempt29/, "attempt31")
  gsub(/ATTEMPT=29 PORT=19701/, "ATTEMPT=31 PORT=19703")
  gsub(/19701/, "19703")
  gsub(/Q38_A29_VALIDATE_ONLY/, "Q38_A31_VALIDATE_ONLY")
  gsub(/A29/, "A31")
  gsub(/d14396e27247c1b251da0ce24a0942772c4b002f/, current_vllm)
  gsub(/37791a9b20d0ce0d10e89f3930f9d0e8b7d7f743e1074691b39ed22a40e6adbb/, "6fe2ffb28e60706bd7ad814fe0cb57752b8b4f0df27ad50d033880f77a424e0c")
  gsub(/rewrite-a29-kernel-workspace-contract.py/, "rewrite-a31-current-source-contract.py")
  gsub(/c9c86120-4735-4f7a-9500-d7e49f0d2f63/, rejected_boot)
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

[[ $# == 0 ]] || { printf 'FAIL: A31 launcher takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]] || {
  printf 'FAIL: A31 base launcher drifted\n' >&2
  exit 1
}
[[ "$(sha256sum "$rewrite" | cut -d' ' -f1)" == "$expected_rewrite" ]] || {
  printf 'FAIL: A31 rewrite helper drifted\n' >&2
  exit 1
}
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || {
  printf 'FAIL: A31 launcher source %s is not frozen %s\n' "$actual_source" "$expected_source" >&2
  exit 1
}
if [[ "${Q38_A31_SOURCE_ONLY:-0}" == 1 ]]; then derive; exit 0; fi
[[ "$(tr -d '\n' </proc/sys/kernel/random/boot_id)" != "$rejected_boot" ]] || {
  printf 'FAIL: A31 rejects the event-chain failure boot; reboot only while attended\n' >&2
  exit 1
}
[[ -s "$affinity_root/comparison.json" && -s "$affinity_root/evidence.sha256" ]] || {
  printf 'FAIL: A31 requires the clean same-boot affinity component closeout first\n' >&2
  exit 1
}
[[ "$(tr -d '\n' <"$affinity_root/boot-id.txt")" == "$(tr -d '\n' </proc/sys/kernel/random/boot_id)" ]] || {
  printf 'FAIL: A31 affinity prerequisite is from another boot\n' >&2
  exit 1
}
(cd "$affinity_root" && sha256sum -c evidence.sha256) >/dev/null || {
  printf 'FAIL: A31 affinity prerequisite evidence does not verify\n' >&2
  exit 1
}
jq -e '.status == "passed" or .status == "closed"' "$affinity_root/comparison.json" >/dev/null || {
  printf 'FAIL: A31 affinity prerequisite did not complete cleanly\n' >&2
  exit 1
}
source <(derive)
