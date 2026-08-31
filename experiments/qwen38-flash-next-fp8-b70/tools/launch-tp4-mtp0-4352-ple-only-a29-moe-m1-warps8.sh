#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/launch-tp4-mtp0-4352-ple-only-a27-moe-warps8.sh"
selection_helper="${script_dir}/verify-moe-m1-selection.py"
expected_base=caf12747ccd194ce784c7f64f3bbd327ed63fbfc3d2a7b92d702e5162ec58e0f
expected_helper=cafe4b1998dabbe60b4877615d0f9342ec479245713f6fe964786e246d7f9c1a
expected_source=c5c57ffd8377d4c367617c0811830d39b3dbbb8ed3b3ba25742bc4eb20857283
config_dir=/home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/configs/moe-warps8-m1
config_name='E=128,N=640,device_name=Intel(R)_Arc(TM)_Pro_B70_Graphics,dtype=fp8_w8a8,block_shape=[128,128].json'
config_sha=91e5d8b692da3febbba7cb07ee4fdab319909da0c82c1fda95b92dc42d680464

derive() {
  Q38_A27_SOURCE_ONLY=1 "$base" | awk -v helper="$selection_helper" -v helper_sha="$expected_helper" '
{
  gsub(/ple-only-a27-moe-warps8/, "ple-only-a29-moe-m1-warps8")
  gsub(/q38-mtp0-ple-only-a27/, "q38-mtp0-ple-only-a29")
  gsub(/q38-ple-only-a27/, "q38-ple-only-a29")
  gsub(/q38-ple4k-a27/, "q38-ple4k-a29")
  gsub(/attempt27/, "attempt29")
  gsub(/ATTEMPT=27 PORT=19699/, "ATTEMPT=29 PORT=19701")
  gsub(/19699/, "19701")
  gsub(/Q38_A27_VALIDATE_ONLY/, "Q38_A29_VALIDATE_ONLY")
  gsub(/A27/, "A29")
  gsub(/moe-warps8-m4-trace-off/, "moe-m1-warps8-selected-trace-off")
  gsub(/configs\/moe-warps8-m4/, "configs/moe-warps8-m1")
  gsub(/f93b5e1d5863e04268eb96877ab2ef6ba0990c42c62f1dff27bc36676c30bf7f/, "91e5d8b692da3febbba7cb07ee4fdab319909da0c82c1fda95b92dc42d680464")
  gsub(/M4 MoE/, "M1 MoE")
  if ($0 == "expected_derived=54e0f0e2531b95d99c289818da12bda3276cb87de4cb27dc47d69a9e9f0bbd3c") {
    print "expected_derived=8909a33733ceb9196527abc698cee73e5b1441ca5c59bb44964e71143b329b06"
    next
  }
  if (index($0, "print \"[[ \\\"$(sha256sum \\\"${config_file}") > 0) {
    print
    print "    print \"selection_helper=\\\"" helper "\\\"\""
    print "    print \"[[ \\\"$(sha256sum \\\"${selection_helper}\\\" | cut -c1-64)\\\" == " helper_sha " ]] || fail \\\"M1 selection helper changed immediately before launch\\\"\""
    print "    print \"\\\"${python}\\\" \\\"${selection_helper}\\\" --config-file \\\"${config_file}\\\" --vllm-source \\\"${vllm_src}\\\" --output \\\"${run_dir}/moe-m1-selection-receipt.json\\\"\""
    next
  }
  print
}
'
}

[[ $# == 0 ]] || { printf 'FAIL: A29 launcher takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]]
[[ "$(sha256sum "$selection_helper" | cut -d' ' -f1)" == "$expected_helper" ]]
config_file="${config_dir}/${config_name}"
[[ "$(sha256sum "$config_file" | cut -d' ' -f1)" == "$config_sha" ]]
[[ "$(jq -r '."1".num_warps' "$config_file")" == 8 ]]
[[ "$(jq -cer '[to_entries[] | select(.key != "1") | .value.num_warps] | unique' "$config_file")" == '[4]' ]]
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || {
  printf 'FAIL: A29 launcher source %s is not frozen %s\n' "$actual_source" "$expected_source" >&2
  exit 1
}
if [[ "${Q38_A29_SOURCE_ONLY:-0}" == 1 ]]; then derive; exit 0; fi
source <(derive)
