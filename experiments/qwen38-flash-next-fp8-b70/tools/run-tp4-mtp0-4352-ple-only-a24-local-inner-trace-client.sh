#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/run-tp4-mtp0-4352-ple-only-a23-inner-trace-client.sh"
expected_base=04cee0d187065cdbcbd3a24195163f93e448c465324b71488bf4720c06fd9f8d
expected_source=a3136f909282e59c1457a22637f8d283ab81f48ed80e3b611a82cf093a397824

derive() {
  Q38_A23_SOURCE_ONLY=1 "$base" | awk '
{
  gsub(/ple-only-a23/, "ple-only-a24")
  gsub(/attempt23/, "attempt24")
  gsub(/19695/, "19696")
  gsub(/Q38_A23_VALIDATE_ONLY/, "Q38_A24_VALIDATE_ONLY")
  gsub(/\/mnt\/usb-models\/llm-models\/Qwen3.8-Flash-Next-FP8/, "/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8")
  if ($0 == "expected_derived=aa24172f7f22f46524f29bfcbd6a2dec94a0dfc0299df666bd13c31d3b9f1c7c")
    print "expected_derived=12bf005261e1893986d3e2856a32d42ea83112f1468ef7af099ffc8e8ccca40d"
  else
    print
}
'
}

[[ $# == 0 ]] || { printf 'FAIL: A24 local inner-trace client takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]]
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || { printf 'FAIL: A24 client source %s\n' "$actual_source" >&2; exit 1; }
if [[ "${Q38_A24_SOURCE_ONLY:-0}" == 1 ]]; then derive; exit 0; fi
source <(derive)
