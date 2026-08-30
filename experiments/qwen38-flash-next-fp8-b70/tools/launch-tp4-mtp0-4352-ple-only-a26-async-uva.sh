#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/launch-tp4-mtp0-4352-ple-only-a25-local-inner-trace.sh"
expected_base=170f5d282c52188f803e7112c9d9ca77595a1bb29963a3457b7fe8d03d32e77f
expected_source=8f7832212dc1f900180e2e20df678859bba79611bf1ca0e6d386394be2bb2f77

derive() {
  awk '
{
  if ($0 == "$0 == \"assert offload_budget - offload_bytes_per_rank < 64 * 1024**2\" {")
    inject_after_budget = 1
  if (inject_after_budget && $0 == "}") {
    print
    print "$0 == \"unset VLLM_PLE_CPU_OFFLOAD\" {"
    print "  print"
    print "  print \"export VLLM_XPU_PLE_UVA_PREFETCH=1\""
    print "  next"
    print "}"
    print "$0 == \"setsid \\\"${vllm_bin}\\\" serve \\\"${args[@]}\\\" >\\\"${server_log}\\\" 2>&1 &\" {"
    print "  print \"[[ \\\"$(git -C \\\"${vllm_src}\\\" rev-parse HEAD)\\\" == \\\"${expected_vllm_head}\\\" ]] || fail \\\"vLLM overlay changed immediately before launch\\\"\""
    print "  print \"[[ -z \\\"$(git -C \\\"${vllm_src}\\\" status --porcelain)\\\" ]] || fail \\\"vLLM overlay became dirty immediately before launch\\\"\""
    print "  print"
    print "  next"
    print "}"
    inject_after_budget = 0
    next
  }
  gsub(/ple-only-a25-local-inner-trace/, "ple-only-a26-async-uva")
  gsub(/q38-ple4k-a25/, "q38-ple4k-a26")
  gsub(/attempt25/, "attempt26")
  gsub(/ATTEMPT=25 PORT=19697/, "ATTEMPT=26 PORT=19698")
  gsub(/19697/, "19698")
  gsub(/Q38_A25_VALIDATE_ONLY/, "Q38_A26_VALIDATE_ONLY")
  gsub(/A25/, "A26")
  gsub(/ca20c4465ca34fc733aac70416b75d7cb8a1c46f/, "d14396e27247c1b251da0ce24a0942772c4b002f")
  gsub(/diagnostics=qwen4exp-ple-inner-trace-rank-all/, "diagnostics=async-uva-ple-trace-off")
  if ($0 == "expected_derived=b1048e3204d67d13944226f2714afb44f06a68f0c4d92477fbe0f49e1951b150")
    print "expected_derived=1a3de0d9207843bcb451abfae0d6eadc03debfc87d916bab801db5efae938870"
  else if (index($0, "export Q38_REPEATABILITY_TRACE_FILE=") == 1)
    print "unset Q38_REPEATABILITY_TRACE_FILE"
  else if ($0 == "export VLLM_XPU_QWEN4_EXP_REPEATABILITY_TRACE_RANK=all") {
    print "unset VLLM_XPU_QWEN4_EXP_REPEATABILITY_TRACE_RANK"
    print "export VLLM_XPU_PLE_UVA_PREFETCH=1"
  } else
    print
}
' "$base"
}

[[ $# == 0 ]] || { printf 'FAIL: A26 launcher takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]]
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || {
  printf 'FAIL: A26 launcher source %s is not frozen %s\n' "$actual_source" "$expected_source" >&2
  exit 1
}
if [[ "${Q38_A26_SOURCE_ONLY:-0}" == 1 ]]; then derive; exit 0; fi
source <(derive)
