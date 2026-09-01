#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/run-tp4-mtp0-4352-ple-only-a29-moe-m1-warps8-client.sh"
expected_base=28e89555634fe22a06cf87d8bc15fbb69fe6230981ddaef34d9a7fe1476b6981
current_vllm=797769b34b6db5c934609b75dc04cc61ec66e5f9
expected_source=9980496a1fdd0136373963dad890405e0c65c6a9e88817cc9ef76e0125abe601

derive() {
  Q38_A29_SOURCE_ONLY=1 "$base" | awk -v current_vllm="$current_vllm" '
BEGIN { skip_old_supervisor_binding = 0 }
{
  if ($0 == "supervisor_pid=$(cat \"${state}.pid\" 2>/dev/null || true)") {
    print "inner_supervisor_pid=$(cat \"${state}.pid\" 2>/dev/null || true)"
    print "[[ \"$inner_supervisor_pid\" =~ ^[1-9][0-9]*$ && -r \"/proc/${inner_supervisor_pid}/environ\" ]] || { printf '\''FAIL: inner supervisor is absent\\n'\'' >&2; exit 1; }"
    print "mapfile -d '\'''\'' -t outer_pid_rows < <(grep -z '^Q38_A32_SUPERVISOR_PID=' \"/proc/${inner_supervisor_pid}/environ\" || true)"
    print "mapfile -d '\'''\'' -t outer_starttime_rows < <(grep -z '^Q38_A32_SUPERVISOR_STARTTIME=' \"/proc/${inner_supervisor_pid}/environ\" || true)"
    print "[[ \"${#outer_pid_rows[@]}\" == 1 && \"${#outer_starttime_rows[@]}\" == 1 ]] || { printf '\''FAIL: outer supervisor binding is absent or ambiguous\\n'\'' >&2; exit 1; }"
    print "outer_supervisor_pid=${outer_pid_rows[0]#Q38_A32_SUPERVISOR_PID=}"
    print "outer_supervisor_starttime=${outer_starttime_rows[0]#Q38_A32_SUPERVISOR_STARTTIME=}"
    print "[[ \"$outer_supervisor_pid\" =~ ^[1-9][0-9]*$ && \"$outer_supervisor_starttime\" =~ ^[1-9][0-9]*$ && -r \"/proc/${outer_supervisor_pid}/stat\" ]] || { printf '\''FAIL: outer supervisor identity is malformed or absent\\n'\'' >&2; exit 1; }"
    print "actual_outer_starttime=$(awk '\''{ line=$0; sub(/^.*\\) /, \"\", line); split(line, fields, \" \" ); print fields[20] }'\'' \"/proc/${outer_supervisor_pid}/stat\")"
    print "[[ \"$actual_outer_starttime\" == \"$outer_supervisor_starttime\" ]] || { printf '\''FAIL: outer supervisor starttime mismatch\\n'\'' >&2; exit 1; }"
    print "outer_supervisor_command=$(tr '\''\\0'\'' '\'' '\'' <\"/proc/${outer_supervisor_pid}/cmdline\")"
    print "[[ \"$outer_supervisor_command\" == *\"supervise-tp4-mtp0-4352-ple-only-a32-moe-m1-current.sh\"* ]] || { printf '\''FAIL: outer supervisor script identity mismatch\\n'\'' >&2; exit 1; }"
    print "expected_outer_locks=(/tmp/b70-benchmark.lock /tmp/b70-gpu0.lock /tmp/b70-gpu1.lock /tmp/b70-gpu2.lock /tmp/b70-gpu3.lock)"
    print "for lock_index in 0 1 2 3 4; do"
    print "  [[ \"$(readlink -f \"/proc/${outer_supervisor_pid}/fd/$((7 + lock_index))\")\" == \"${expected_outer_locks[$lock_index]}\" ]] || { printf '\''FAIL: outer supervisor lock set mismatch\\n'\'' >&2; exit 1; }"
    print "done"
    skip_old_supervisor_binding = 1
    next
  }
  if (skip_old_supervisor_binding) {
    if ($0 == "}") skip_old_supervisor_binding = 0
    next
  }
  gsub(/ple-only-a29-moe-m1-warps8/, "ple-only-a32-moe-m1-current")
  gsub(/q38-mtp0-ple-only-a29/, "q38-mtp0-ple-only-a32")
  gsub(/q38-ple-only-a29/, "q38-ple-only-a32")
  gsub(/attempt29/, "attempt32")
  gsub(/19701/, "19704")
  gsub(/A29/, "A32")
  gsub(/d14396e27247c1b251da0ce24a0942772c4b002f/, current_vllm)
  print
}
'
}

[[ $# == 0 ]] || { printf 'FAIL: A32 client takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]] || {
  printf 'FAIL: A32 base client drifted\n' >&2
  exit 1
}
actual_source=$(derive | sha256sum | cut -d' ' -f1)
[[ "$actual_source" == "$expected_source" ]] || {
  printf 'FAIL: A32 client source %s is not frozen %s\n' "$actual_source" "$expected_source" >&2
  exit 1
}
if [[ "${Q38_A32_SOURCE_ONLY:-0}" == 1 ]]; then derive; exit 0; fi
source <(derive)
