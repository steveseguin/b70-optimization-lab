#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/supervise-tp4-mtp0-4352-ple-only-a23-inner-trace.sh"
expected_base=8c4311a6dfe1fbd1f15d599119ae345ba6bdb7c2ee81cdecc41454fa74182ed3
expected_source=d4b8631f816f0105d358a58cb4124c5ae21dd948729255db0dfd81f1b9e0e568

derive() {
  Q38_A23_SOURCE_ONLY=1 "$base" | awk '
{
  gsub(/ple-only-a23/, "ple-only-a24")
  gsub(/ple-only-a24-inner-trace/, "ple-only-a24-local-inner-trace")
  gsub(/attempt23/, "attempt24")
  gsub(/19695/, "19696")
  gsub(/Q38_A23_VALIDATE_ONLY/, "Q38_A24_VALIDATE_ONLY")
  gsub(/q38-ple4k-a23-rpc/, "q38-ple4k-a24-rpc")
  gsub(/9194d3065d2c6ad1fd0e86e6054d0dd398f3d2510f098090c0c06562bfe04874/, "23afbb401bc0ad15403e20e734ce5b5d9f4095b95a29e641a85e292659bbcff6")
  gsub(/04cee0d187065cdbcbd3a24195163f93e448c465324b71488bf4720c06fd9f8d/, "b485d3c98a448f09c7a2d0e2c3a69e93ea52aedc1bbe3e27314a058184e6715f")
  gsub(/\/mnt\/usb-models\/llm-models\/Qwen3.8-Flash-Next-FP8/, "/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8")
  if ($0 == "expected_derived=0a08c20662b0e031e4a2c222219e4d8d4e5cf20ffa37a7a1163d2190648ddc49")
    print "expected_derived=8f34100d66f0d3f2b0f460a9f4cf857b56a43d6c2954b017c36b63eb644a6b65"
  else
    print
}
'
}

[[ $# == 0 ]] || { printf 'FAIL: A24 local inner-trace supervisor takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]]
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || { printf 'FAIL: A24 supervisor source %s\n' "$actual_source" >&2; exit 1; }
if [[ "${Q38_A24_SOURCE_ONLY:-0}" == 1 ]]; then derive; exit 0; fi
source <(derive)
