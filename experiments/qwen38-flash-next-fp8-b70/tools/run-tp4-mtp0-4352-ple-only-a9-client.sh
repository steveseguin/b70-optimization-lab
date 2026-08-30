#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/run-tp4-mtp0-current-anchor-a4-client.sh"
expected_base=28957596b743e068c50c65ceaa716bb79a47908167ab7ac3ec4fb629346135e0
expected_derived=66378542f789ff81d90dd4535156f04663ea72179c28d60442b9a35412858c33

derive() {
  awk '
$0 == "supervisor=\"${repo}/experiments/qwen38-flash-next-fp8-b70/tools/supervise-tp4-mtp0-current-anchor-a4.sh\"" {
  print "supervisor=\"${repo}/experiments/qwen38-flash-next-fp8-b70/tools/supervise-tp4-mtp0-4352-ple-only-a9.sh\""; next
}
$0 == "state=/tmp/q38-mtp0-current-anchor-a4" { print "state=/tmp/q38-mtp0-ple-only-a9"; next }
$0 == "run_dir=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-eager-mtp0-4352-r1-attempt4" {
  print "run_dir=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-eager-mtp0-4352-ple-only-r1-attempt9"; next
}
$0 == "base_url=http://127.0.0.1:19673" { print "base_url=http://127.0.0.1:19681"; next }
index($0, "supervise-tp4-mtp0-current-anchor-a4.sh") { gsub(/supervise-tp4-mtp0-current-anchor-a4\.sh/, "supervise-tp4-mtp0-4352-ple-only-a9.sh"); print; next }
index($0, "--port 19673") { gsub(/--port 19673/, "--port 19681"); print; next }
$0 == "  '\''vllm_head=1372c62d975c554f4b465c8299bc5f3295301ceb'\'' \\" {
  print "  '\''vllm_head=e5137bfd8ca2ca718c4fd93d86d54bb843e2999b'\'' \\"; next
}
$0 == "  '\''tp=4 ep=4 all2all=allgather_reducescatter'\'' \\" {
  print "  '\''cpu_offload_gb=12.0'\'' '\''cpu_offload_params=ple_embedding.ngram_embedding.weight'\'' \\"
  print; next
}
index($0, "'\''kv_cache_memory_bytes=201326592'\''") { gsub(/201326592/, "134217728"); print; next }
index($0, "kv_cache_memory_bytes\") == \"201326592\"") { gsub(/201326592/, "134217728"); print; next }
index($0, "qwen38-flash-next-fp8-tp4-ep4-eager-mtp0-4352-r1-attempt4-supervisor") {
  gsub(/qwen38-flash-next-fp8-tp4-ep4-eager-mtp0-4352-r1-attempt4-supervisor/, "qwen38-flash-next-fp8-tp4-ep4-eager-mtp0-4352-ple-only-r1-attempt9-supervisor"); print; next
}
index($0, "q38-current-anchor") {
  gsub(/q38-current-anchor-a4/, "q38-ple-only-a9")
  gsub(/q38-current-anchor/, "q38-ple-only-a9")
  print; next
}
$0 == "assert len(set(depth_hashes)) == 1" {
  print
  print "assert depth_hashes == ['\''1d833e5f463366223a669aa15495840d1337b173e675a9ea04f00a5ae339d5cc'\''] * 2"
  next
}
index($0, "\"vllm_head\": \"1372c62d975c554f4b465c8299bc5f3295301ceb\"") {
  gsub(/1372c62d975c554f4b465c8299bc5f3295301ceb/, "e5137bfd8ca2ca718c4fd93d86d54bb843e2999b"); print; next
}
$0 == "        \"tp\": 4, \"ep\": 4, \"mtp\": 0, \"graph\": \"off\", \"max_model_len\": 4352," {
  print
  print "        \"placement\": \"ple_only_uva\", \"ple_host_bytes_per_rank\": 12800061440,"
  print "        \"input_embedding\": \"device\", \"kv_cache_memory_bytes\": 134217728,"
  next
}
index($0, "current-anchor-summary.json") { gsub(/current-anchor-summary\.json/, "ple-only-summary.json"); print; next }
index($0, "current-runtime MTP0 anchor") { gsub(/current-runtime MTP0 anchor/, "PLE-only 4K MTP0 candidate"); print; next }
index($0, "current-runtime TP4 eager MTP0") { gsub(/current-runtime TP4 eager MTP0/, "PLE-only TP4 eager MTP0"); print; next }
{ print }
' "$base"
}

[[ $# == 0 ]] || { printf 'FAIL: PLE-only client takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]]
actual_derived=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_derived" == "$expected_derived" ]] || {
  printf 'FAIL: derived PLE-only client hash %s is not frozen %s\n' "$actual_derived" "$expected_derived" >&2
  exit 1
}
if [[ "${Q38_A9_VALIDATE_ONLY:-0}" == 1 ]]; then
  derive
  exit 0
fi
source <(derive)
