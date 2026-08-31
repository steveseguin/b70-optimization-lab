#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/run-tp4-mtp0-4352-ple-only-a27-moe-warps8-client.sh"
selection_helper="${script_dir}/verify-moe-m1-selection.py"
expected_base=d3cb538d71f11423b8cc5f13a2ca9873fb9ad1cf1a654eaaa6ddac7f480cf68a
expected_helper=cafe4b1998dabbe60b4877615d0f9342ec479245713f6fe964786e246d7f9c1a
expected_source=c630d9591b75744d2d468f024177ea6533016da00f047df78507e0abd35ac52b

derive() {
  Q38_A27_SOURCE_ONLY=1 "$base" | awk -v helper_sha="$expected_helper" '
{
  gsub(/ple-only-a27-moe-warps8/, "ple-only-a29-moe-m1-warps8")
  gsub(/q38-mtp0-ple-only-a27/, "q38-mtp0-ple-only-a29")
  gsub(/q38-ple-only-a27/, "q38-ple-only-a29")
  gsub(/attempt27/, "attempt29")
  gsub(/19699/, "19701")
  gsub(/moe-warps8-m4-trace-off/, "moe-m1-warps8-selected-trace-off")
  gsub(/configs\/moe-warps8-m4/, "configs/moe-warps8-m1")
  gsub(/f93b5e1d5863e04268eb96877ab2ef6ba0990c42c62f1dff27bc36676c30bf7f/, "91e5d8b692da3febbba7cb07ee4fdab319909da0c82c1fda95b92dc42d680464")
  gsub(/M4 MoE/, "M1 MoE")
  gsub(/\."4"\.num_warps/, ".\"1\".num_warps")
  gsub(/moe_m4_num_warps/, "moe_m1_num_warps")
  if ($0 == "server_command=$(tr '\''\\0'\'' '\'' '\'' <\"/proc/${server_pid}/cmdline\")") {
    print
    print "selection_receipt=\"${run_dir}/moe-m1-selection-receipt.json\""
    print "[[ -s \"${selection_receipt}\" ]] || { printf '\''FAIL: live M1 selection receipt is absent\\n'\'' >&2; exit 1; }"
    print "jq -e '\''.status == \"passed\" and .requested_m == 1 and .selected_batch_key == 1 and .effective_config.num_warps == 8 and .official_resolver_match == true and .candidate_scope == \"key_1_only\" and .config_sha256 == \"91e5d8b692da3febbba7cb07ee4fdab319909da0c82c1fda95b92dc42d680464\" and .source_contract.fused_moe_sha256 == \"7072eb06237be9d33dcb0ef7101410f886a6363c98cbee70a014c68b70f639cb\" and .source_contract.triton_moe_sha256 == \"312d4da6f6869b22ed8c179f39f839cfbac2f77f5b01060c001f353d2310a6e5\"'\'' \"${selection_receipt}\" >/dev/null || { printf '\''FAIL: official M1 selection receipt did not prove key 1 / warps 8\\n'\'' >&2; exit 1; }"
    print "[[ \"$(sha256sum /home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/tools/verify-moe-m1-selection.py | cut -d'\'' '\'' -f1)\" == " helper_sha " ]] || exit 1"
    next
  }
  if ($0 == "[[ \"$(jq -r '\''.\"1\".num_warps'\'' \"$config_file\")\" == 8 ]] || exit 1") {
    print
    print "[[ \"$(jq -r '\''.\"4\".num_warps'\'' \"$config_file\")\" == 4 ]] || exit 1"
    print "! grep -zFq '\''configs/moe-warps8-m4'\'' \"/proc/${server_pid}/environ\" || { printf '\''FAIL: old M4 tuned folder leaked into server environment\\n'\'' >&2; exit 1; }"
    next
  }
  if ($0 == "quality = json.loads((root / \"quality-current.json\").read_text())") {
    print "selection = json.loads((root / \"moe-m1-selection-receipt.json\").read_text())"
    print
    next
  }
  if ($0 == "        \"moe_m1_num_warps\": 8,") {
    print "        \"moe_selected_batch_key\": selection[\"selected_batch_key\"],"
    print
    next
  }
  if (index($0, "for name in [\"recovery-canary.json\"") == 1) {
    sub(/\[\"recovery-canary.json\"/, "[\"moe-m1-selection-receipt.json\", \"recovery-canary.json\"")
    print
    next
  }
  print
}
'
}

[[ $# == 0 ]] || { printf 'FAIL: A29 client takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]]
[[ "$(sha256sum "$selection_helper" | cut -d' ' -f1)" == "$expected_helper" ]]
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || {
  printf 'FAIL: A29 client source %s is not frozen %s\n' "$actual_source" "$expected_source" >&2
  exit 1
}
if [[ "${Q38_A29_SOURCE_ONLY:-0}" == 1 ]]; then derive; exit 0; fi
source <(derive)
