#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/supervise-tp4-mtp0-4352-ple-only-a29-moe-m1-warps8.sh"
expected_base=bfb70ca1cdb74f5c7ec4bf462755c250cebbf71a828fd42d18b09c36e7c13bb0
expected_wrapper=b6f9dc16d7b39c7c988f3ff828b37650b24781490348632daf8fb9f574989088
expected_client=7342b8ed2e8edb96cbd648e286e6ebeba9945553ac492915174ea17839e0552e
current_vllm=797769b34b6db5c934609b75dc04cc61ec66e5f9
rejected_boot=c36480de-9150-4182-9888-08c85d2d9de4
affinity_root=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/components/20260831-tp4-count2560-cpu-affinity-a1
component_state="/run/user/$(id -u)/q38-flash-next-component-chain.state"
expected_source=60d281b2f23d1233acc9b42f8ba41dc3f59b59e573ef101f1525820dd291b0c3

derive() {
  Q38_A29_SOURCE_ONLY=1 "$base" | awk \
    -v wrapper_hash="$expected_wrapper" \
    -v client_hash="$expected_client" \
    -v current_vllm="$current_vllm" '
{
  gsub(/ple-only-a29-moe-m1-warps8/, "ple-only-a31-moe-m1-current")
  gsub(/q38-mtp0-ple-only-a29/, "q38-mtp0-ple-only-a31")
  gsub(/q38-ple4k-a29/, "q38-ple4k-a31")
  gsub(/attempt29/, "attempt31")
  gsub(/19701/, "19703")
  gsub(/A29/, "A31")
  gsub(/d14396e27247c1b251da0ce24a0942772c4b002f/, current_vllm)
  if ($0 == "expected_wrapper=6a624362e1ae1d4c4522fbc6cd88c6ac9e7da0da7998390c28333927c3aec5b0") {
    print "expected_wrapper=" wrapper_hash
    next
  }
  if ($0 == "expected_client=28e89555634fe22a06cf87d8bc15fbb69fe6230981ddaef34d9a7fe1476b6981") {
    print "expected_client=" client_hash
    next
  }
  print
}
'
}

[[ $# == 0 ]] || { printf 'FAIL: A31 supervisor takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]] || {
  printf 'FAIL: A31 base supervisor drifted\n' >&2
  exit 1
}
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || {
  printf 'FAIL: A31 supervisor source %s is not frozen %s\n' "$actual_source" "$expected_source" >&2
  exit 1
}
if [[ "${Q38_A31_SOURCE_ONLY:-0}" == 1 ]]; then derive; exit 0; fi
[[ "$(tr -d '\n' </proc/sys/kernel/random/boot_id)" != "$rejected_boot" ]] || {
  printf 'FAIL: A31 supervisor rejects the event-chain failure boot; reboot only while attended\n' >&2
  exit 1
}
[[ -s "$affinity_root/comparison.json" && -s "$affinity_root/evidence.sha256" ]] || {
  printf 'FAIL: A31 supervisor requires the clean same-boot affinity closeout first\n' >&2
  exit 1
}
[[ "$(tr -d '\n' <"$affinity_root/boot-id.txt")" == "$(tr -d '\n' </proc/sys/kernel/random/boot_id)" ]] || {
  printf 'FAIL: A31 supervisor affinity prerequisite is from another boot\n' >&2
  exit 1
}
exec 10>"${component_state}.lock"
flock -n 10 || {
  printf 'FAIL: A31 supervisor component-chain state is busy\n' >&2
  exit 1
}
read -r component_status component_boot <"$component_state" || {
  printf 'FAIL: A31 supervisor component-chain state is absent or malformed\n' >&2
  exit 1
}
[[ "$component_status" == cpu-affinity-complete && "$component_boot" == "$(tr -d '\n' </proc/sys/kernel/random/boot_id)" ]] || {
  printf 'FAIL: A31 supervisor requires cpu-affinity-complete on this boot\n' >&2
  exit 1
}
flock -u 10
exec 10>&-
(cd "$affinity_root" && sha256sum -c evidence.sha256) >/dev/null || {
  printf 'FAIL: A31 supervisor affinity evidence does not verify\n' >&2
  exit 1
}
jq -e '.status == "passed" or .status == "closed"' "$affinity_root/comparison.json" >/dev/null || {
  printf 'FAIL: A31 supervisor affinity prerequisite did not complete cleanly\n' >&2
  exit 1
}
source <(derive)
