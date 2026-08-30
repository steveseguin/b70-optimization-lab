#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/supervise-tp4-mtp0-current-anchor-a4.sh"
expected_base=4397290c337fa88c8131904b55f045d9b781a9d91213b84a637cb32f8ca25bad
expected_derived=7c3adf6a9b0c551e61d1489d78102af1208b2084d18c1522cb2fd667131c3726

derive() {
  awk '
index($0, "script_dir=$(cd --") == 1 { print "script_dir=/home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/tools"; next }
$0 == "wrapper=\"${script_dir}/launch-tp4-mtp0-current-anchor-a4.sh\"" {
  print "wrapper=\"${script_dir}/launch-tp4-mtp0-4352-ple-only-a9.sh\""; next
}
$0 == "expected_wrapper=adb0b7dc7a0f2aa21a4d2dd217a3107a579c42a921e1139bc1eda8801d46219d" {
  print "expected_wrapper=9fb4751df8641fdac67a7836becd025bf314c8e8a79c30c876b73c09c859cfa4"; next
}
$0 == "client=\"${script_dir}/run-tp4-mtp0-current-anchor-a4-client.sh\"" {
  print "client=\"${script_dir}/run-tp4-mtp0-4352-ple-only-a9-client.sh\""; next
}
$0 == "expected_client=28957596b743e068c50c65ceaa716bb79a47908167ab7ac3ec4fb629346135e0" {
  print "expected_client=71595fc912078203087fc04ab3a1a944589af91dd3855c2f5b8c086de7cb4b9c"; next
}
$0 == "state=/tmp/q38-mtp0-current-anchor-a4" { print "state=/tmp/q38-mtp0-ple-only-a9"; next }
$0 == "run_dir=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-eager-mtp0-4352-r1-attempt4" {
  print "run_dir=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-eager-mtp0-4352-ple-only-r1-attempt9"; next
}
$0 == "cache_dir=/mnt/usb-models/llm-runtime/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-eager-mtp0-4352-r1-attempt4" {
  print "cache_dir=/mnt/usb-models/llm-runtime/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-eager-mtp0-4352-ple-only-r1-attempt9"; next
}
$0 == "compile_dir=/tmp/qwen38-flash-next-fp8-tp4-ep4-eager-mtp0-4352-r1-attempt4-compile" {
  print "compile_dir=/tmp/qwen38-flash-next-fp8-tp4-ep4-eager-mtp0-4352-ple-only-r1-attempt9-compile"; next
}
$0 == "rpc_dir=/tmp/qwen38-flash-next-fp8-tp4-ep4-eager-mtp0-4352-r1-attempt4-rpc" {
  print "rpc_dir=/tmp/q38-ple4k-a9-rpc"; next
}
$0 == "evidence_dir=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-eager-mtp0-4352-r1-attempt4-supervisor" {
  print "evidence_dir=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-eager-mtp0-4352-ple-only-r1-attempt9-supervisor"; next
}
$0 == "port=19673" { print "port=19681"; next }
index($0, "frozen current-anchor wrapper") { gsub(/current-anchor/, "PLE-only"); print; next }
index($0, "frozen current-anchor client") { gsub(/current-anchor/, "PLE-only"); print; next }
$0 == "  \"$wrapper\" --execute --ack '\''RUN qwen38-flash-next-fp8-tp4-ep4-eager-mtp0-4352-r1'\'' &" {
  print "  \"$wrapper\" &"; next
}
index($0, "STOP after passed current-runtime MTP0 anchor") {
  gsub(/STOP after passed current-runtime MTP0 anchor/, "STOP after passed PLE-only 4K MTP0 candidate"); print; next
}
index($0, "PASS recovery quality short-repeat exact-4K-repeat current-runtime MTP0 anchor") {
  gsub(/PASS recovery quality short-repeat exact-4K-repeat current-runtime MTP0 anchor/, "PASS recovery quality short-repeat exact-4K-repeat PLE-only 4K MTP0 candidate"); print; next
}
index($0, ".identity.vllm_head == \"1372c62d975c554f4b465c8299bc5f3295301ceb\"") {
  gsub(/1372c62d975c554f4b465c8299bc5f3295301ceb/, "e5137bfd8ca2ca718c4fd93d86d54bb843e2999b"); print; next
}
$0 == "         .identity.graph == \"off\" and .identity.max_model_len == 4352 and" {
  print
  print "         .identity.placement == \"ple_only_uva\" and"
  print "         .identity.ple_host_bytes_per_rank == 12800061440 and"
  print "         .identity.input_embedding == \"device\" and"
  print "         .identity.kv_cache_memory_bytes == 134217728 and"
  next
}
index($0, ".exact_4k.cached_tokens == [0, 0] and .protected_results_changed == false") {
  print "         .exact_4k.cached_tokens == [0, 0] and"
  print "         .exact_4k.output_token_ids_sha256 == \"1d833e5f463366223a669aa15495840d1337b173e675a9ea04f00a5ae339d5cc\" and"
  print "         .short.output_sha256 == \"5f40744644b98ddd58a0c202fe855af324c0b1c33e1a6275afd74c12488f89f0\" and"
  print "         .protected_results_changed == false'\'' \\"
  next
}
index($0, "current-anchor-summary.json") { gsub(/current-anchor-summary\.json/, "ple-only-summary.json"); print; next }
index($0, "current-anchor postflight") { gsub(/current-anchor/, "PLE-only"); print; next }
{ print }
' "$base"
}

[[ $# == 0 ]] || { printf 'FAIL: PLE-only supervisor takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]]
actual_derived=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_derived" == "$expected_derived" ]] || {
  printf 'FAIL: derived PLE-only supervisor hash %s is not frozen %s\n' "$actual_derived" "$expected_derived" >&2
  exit 1
}
if [[ "${Q38_A9_VALIDATE_ONLY:-0}" == 1 ]]; then
  derive
  exit 0
fi
source <(derive)
