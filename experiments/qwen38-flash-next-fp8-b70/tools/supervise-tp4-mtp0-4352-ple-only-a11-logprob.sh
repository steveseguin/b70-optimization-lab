#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/supervise-tp4-mtp0-4352-ple-only-a10.sh"
expected_base=5cd9afd92c394ace579c8837c560b37f0dcedbb0e44c9fe5a268b89fdd870ac0
expected_source=c17f18c9f24e0a2ae3425434925e9540e4c40e5bf9a8748c23041cbdcb7d3135

derive() {
  Q38_A10_VALIDATE_ONLY=1 "$base" | awk '
BEGIN { skip_summary = 0 }
$0 == "wrapper=\"${script_dir}/launch-tp4-mtp0-4352-ple-only-a10.sh\"" {
  print "wrapper=\"${script_dir}/launch-tp4-mtp0-4352-ple-only-a11-logprob.sh\""; next
}
$0 == "expected_wrapper=8a693f850bb43e71f41258b9cd80915c6275c0f590ef12b6e3ed7c5d9e09a910" {
  print "expected_wrapper=955505783af6ec3fbfe884c3a0134561d52d0597bc7dc65a94436013a9cbd225"; next
}
$0 == "client=\"${script_dir}/run-tp4-mtp0-4352-ple-only-a10-client.sh\"" {
  print "client=\"${script_dir}/run-tp4-mtp0-4352-ple-only-a11-logprob-client.sh\""; next
}
$0 == "expected_client=b11ce44155577d78b63451733218e48181c8c24155a8d72f0ca0a6267df5b707" {
  print "expected_client=56740bfb3662ce2674a367c9b43c2474379cc664b9d80da353117e99355eea07"; next
}
index($0, "jq -e '\''.status == \"passed\" and .recovery_canary") {
  print "       jq -e '\''.schema == \"qwen38-exact-depth-logprob-repeat-v1\" and"
  print "         .status == \"passed\" and .performance_credit == false and"
  print "         .identity.repeats == 4 and .identity.top_logprobs == 8 and"
  print "         .request.prompt_token_ids_sha256 == \"aedf2eb779bfa4aad8f533c644ca94646977deae1c10221bff592f06785c76d0\" and"
  print "         (.rows | length) == 4 and ([.rows[] | .passed] | all) and"
  print "         .analysis.selected_is_top1_all == true'\'' \"${run_dir}/exact-4k-logprob-repeat.json\" >/dev/null 2>&1; then"
  skip_summary = 1
  next
}
skip_summary == 1 {
  if (index($0, "${run_dir}/ple-only-fresh-summary.json")) skip_summary = 0
  next
}
{
  gsub(/ple-only-a10/, "ple-only-a11-logprob")
  gsub(/attempt10/, "attempt11")
  gsub(/19682/, "19683")
  gsub(/q38-ple4k-a10-rpc/, "q38-ple4k-a11-logprob-rpc")
  gsub(/STOP after passed PLE-only 4K MTP0 fresh-server repeat/, "STOP after completed PLE-only exact-4K API-logprob diagnostic")
  gsub(/PASS recovery quality short-repeat exact-4K-repeat PLE-only 4K MTP0 fresh-server repeat/, "PASS exact-4K API-logprob diagnostic transport and greedy-decision integrity")
  gsub(/frozen PLE-only wrapper/, "frozen PLE-only API-logprob wrapper")
  gsub(/frozen PLE-only client/, "frozen PLE-only API-logprob client")
  gsub(/PLE-only postflight/, "PLE-only API-logprob postflight")
  print
}
'
}

[[ $# == 0 ]] || { printf 'FAIL: A11 supervisor takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]]
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || {
  printf 'FAIL: derived A11 supervisor source hash %s is not frozen %s\n' "$actual_source" "$expected_source" >&2
  exit 1
}
if [[ "${Q38_A11_SOURCE_ONLY:-0}" == 1 ]]; then
  derive
  exit 0
fi
source <(derive)
