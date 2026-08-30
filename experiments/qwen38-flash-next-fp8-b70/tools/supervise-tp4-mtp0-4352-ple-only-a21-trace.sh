#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/supervise-tp4-mtp0-4352-ple-only-a20-trace.sh"
expected_base=f12be3ddbc88d9d623f23ac54f73e528691b79ccd1eb33753ad7a70ab0e52009
expected_source=51d2cefb2fbfb6bcb4be2228832c72b181492ceefe56e90beedde09d4145e4c7

derive() {
  Q38_A20_SOURCE_ONLY=1 "$base" | awk '
{
  gsub(/launch-tp4-mtp0-4352-ple-only-a20-external-trace\.sh/, "launch-tp4-mtp0-4352-ple-only-a21-external-trace.sh")
  gsub(/run-tp4-mtp0-4352-ple-only-a20-external-trace-client\.sh/, "run-tp4-mtp0-4352-ple-only-a21-external-trace-client.sh")
  gsub(/ple-only-a20/, "ple-only-a21")
  gsub(/attempt20/, "attempt21")
  gsub(/19692/, "19693")
  gsub(/efff9bf04d9b45afda80d0a80be8908c07901a51cc5e088f265cc54aebf5bffb/, "e60da9b46f31f43224d0564d519b801ee99ee133c042cacb4af1442da9bc18c5")
  gsub(/399546be606a48170f6b00dc6968cf7dabe75f2b0a4233f1d96accf8840f066f/, "6f90e0b35496e61f808ed67b068ee84809bca39ab3644c333dfc5a46cf1a933a")
  gsub(/Q38_A20_VALIDATE_ONLY/, "Q38_A21_VALIDATE_ONLY")
  gsub(/41ad18dd59d79c85ec1838c9a47522e9c9eeb31ca12a801d58754ea7f02c6c06/, "b274d5a77d5323f3c5c2c854fa742c0010a4363312a4c01483b7a5bb0695b1f6")
  if ($0 == "{ print }") {
    print "{"
    print "  gsub(/\\/mnt\\/fast-ai\\/llm-models\\/Qwen3.8-Flash-Next-FP8/, \"/mnt/usb-models/llm-models/Qwen3.8-Flash-Next-FP8\")"
    print "  print"
    print "}"
  } else
    print
}
'
}

[[ $# == 0 ]] || { printf 'FAIL: A21 external trace supervisor takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]]
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || exit 1
if [[ "${Q38_A21_SOURCE_ONLY:-0}" == 1 ]]; then derive; exit 0; fi
source <(derive)
