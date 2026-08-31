#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/supervise-tp4-mtp0-4352-ple-only-a29-moe-m1-warps8.sh"
wrapper="${script_dir}/launch-tp4-mtp0-4352-ple-only-a30-hc-grouped-m1.sh"
client="${script_dir}/run-tp4-mtp0-4352-ple-only-a30-hc-grouped-m1-client.sh"
expected_base=bfb70ca1cdb74f5c7ec4bf462755c250cebbf71a828fd42d18b09c36e7c13bb0
expected_wrapper=19ea4096d8de475ea40738b8d0c2bde006c6e660a653e93d010a56717aff094e
expected_client=71387d4df1f9c5fa2527cd301a8a8992a8ef370cae418eb83e5a44ca56814b07
expected_source=4a498eceb1d6797598dd28b2a01efe554a45fd691553556f015f6370ff7666db

derive() {
  Q38_A29_SOURCE_ONLY=1 "$base" | awk -v wrapper_hash="$expected_wrapper" -v client_hash="$expected_client" '
{
  gsub(/ple-only-a29-moe-m1-warps8/, "ple-only-a30-hc-grouped-m1")
  gsub(/q38-mtp0-ple-only-a29/, "q38-mtp0-ple-only-a30")
  gsub(/q38-ple4k-a29/, "q38-ple4k-a30")
  gsub(/attempt29/, "attempt30")
  gsub(/19701/, "19702")
  gsub(/moe-m1-warps8-selected-trace-off/, "moe-m1-warps8-hc-grouped-up-trace-off")
  gsub(/d14396e27247c1b251da0ce24a0942772c4b002f/, "797769b34b6db5c934609b75dc04cc61ec66e5f9")
  gsub(/ad25aa9f69a2171612b9c6b83dfa82c69559f9e4/, "eeee7d671abfa964626baa18da2174bb92cac80a")
  gsub(/2f829747503c77d4814834dffd0840fb1dd9f75a/, "eeee7d671abfa964626baa18da2174bb92cac80a")
  if ($0 == "expected_wrapper=6a624362e1ae1d4c4522fbc6cd88c6ac9e7da0da7998390c28333927c3aec5b0") {
    print "expected_wrapper=" wrapper_hash
    next
  }
  if ($0 == "expected_client=28e89555634fe22a06cf87d8bc15fbb69fe6230981ddaef34d9a7fe1476b6981") {
    print "expected_client=" client_hash
    next
  }
  if ($0 == "         .identity.stage_build_head == \"eeee7d671abfa964626baa18da2174bb92cac80a\" and") {
    print "         .identity.stage_native_head == \"eeee7d671abfa964626baa18da2174bb92cac80a\" and"
    print "         .identity.stage_retained_base_head == \"2f829747503c77d4814834dffd0840fb1dd9f75a\" and"
    print "         .identity.stage_manifest_sha256 == \"a4e83ec34d91b70a666dc170fcc3bda75562592c58fce198f29cfa4d25755d0d\" and"
    print "         .identity.stage_qualification_sha256 == \"ca218488129510e0bc29175f96fd17f0572ecbc2e0f7913ce3c576d25b5b3591\" and"
    print "         .identity.hc_grouped_up == true and"
    next
  }
  if ($0 == "    \"${evidence_dir}/kernel-journal.log\" || return 1") {
    print
    print "  ! grep -Fq '\''nvme 0000:01:00.0:'\'' \"${evidence_dir}/kernel-journal.log\" || return 1"
    next
  }
  print
}
'
}

[[ $# == 0 ]] || { printf 'FAIL: A30 supervisor takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]] || exit 1
[[ "$(sha256sum "$wrapper" | cut -d' ' -f1)" == "$expected_wrapper" ]] || exit 1
[[ "$(sha256sum "$client" | cut -d' ' -f1)" == "$expected_client" ]] || exit 1
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || {
  printf 'FAIL: A30 supervisor source %s is not frozen %s\n' "$actual_source" "$expected_source" >&2
  exit 1
}
if [[ "${Q38_A30_SOURCE_ONLY:-0}" == 1 ]]; then
  derive
  exit 0
fi
source <(derive)
