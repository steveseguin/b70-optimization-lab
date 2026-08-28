#!/usr/bin/env bash
set -Eeuo pipefail

repo=/home/steve/llm-optimizations
source_client="${repo}/experiments/qwen38-flash-next-fp8-b70/tools/run-tp4-mtp0-current-piecewise-graph-a1-client.sh"
expected_source=5886f5ba6127826f1122bc8ac26d4c1b328d9ab34674051e50cb5d985dbdaaaf
resource_dir=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-piecewise-mtp0-4352-r1-attempt3-resource
derived="${resource_dir}/derived-client.sh"
expected_derived=2fde4a7875168c0df0e217dc454190654ba70c81184d0f7d3f169561fd0bd9ef

[[ $# == 0 ]] || { printf 'FAIL: attempt-3 client takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$source_client" | cut -d' ' -f1)" == "$expected_source" ]] || {
  printf 'FAIL: frozen attempt-1 client source changed\n' >&2
  exit 1
}
[[ -d "$resource_dir" && ! -e "$derived" ]] || {
  printf 'FAIL: fresh resource evidence directory/derived client required\n' >&2
  exit 1
}

stage1="${derived}.stage1"
sed \
  -e 's|supervisor="${repo}/experiments/qwen38-flash-next-fp8-b70/tools/supervise-tp4-mtp0-current-piecewise-graph-a1.sh"|supervisor=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-piecewise-mtp0-4352-r1-attempt3-resource/derived-supervisor.sh|' \
  -e 's/q38-mtp0-current-piecewise-graph-a1/q38-mtp0-current-piecewise-graph-a3/g' \
  -e 's/attempt1/attempt3/g' \
  -e 's/19674/19677/g' \
  -e 's/q38-piecewise-a1/q38-piecewise-a3/g' \
  "$source_client" >"$stage1"
awk '
  $0 == "for row in 1 2 3; do" {
    print
    print "  read -r row_pswpin_before row_pswpout_before < <(awk '\''$1 == \"pswpin\" {a=$2} $1 == \"pswpout\" {b=$2} END {print a, b}'\'' /proc/vmstat)"
    print "  row_temp_used_before=$(awk '\''$1 == \"/var/tmp/q38-piecewise-graph-a3-64g.swap\" {print $4}'\'' /proc/swaps)"
    print "  [[ \"$row_pswpin_before\" =~ ^[0-9]+$ && \"$row_pswpout_before\" =~ ^[0-9]+$ && \"$row_temp_used_before\" =~ ^[0-9]+$ ]] || { printf '\''FAIL: measured-row swap baseline unavailable\\n'\'' >&2; exit 1; }"
    next
  }
  { print }
  index($0, "write_atomic \"${run_dir}/bench-short-r${row}.rc\"") {
    print "  read -r row_pswpin_after row_pswpout_after < <(awk '\''$1 == \"pswpin\" {a=$2} $1 == \"pswpout\" {b=$2} END {print a, b}'\'' /proc/vmstat)"
    print "  row_temp_used_after=$(awk '\''$1 == \"/var/tmp/q38-piecewise-graph-a3-64g.swap\" {print $4}'\'' /proc/swaps)"
    print "  [[ \"$row_pswpin_after\" =~ ^[0-9]+$ && \"$row_pswpout_after\" =~ ^[0-9]+$ && \"$row_temp_used_after\" =~ ^[0-9]+$ ]] || { printf '\''FAIL: measured-row swap endpoint unavailable\\n'\'' >&2; exit 1; }"
    print "  {"
    print "    printf '\''pswpin_before=%s\\npswpin_after=%s\\npswpout_before=%s\\npswpout_after=%s\\ntemp_swap_used_before_kib=%s\\ntemp_swap_used_after_kib=%s\\n'\'' \"$row_pswpin_before\" \"$row_pswpin_after\" \"$row_pswpout_before\" \"$row_pswpout_after\" \"$row_temp_used_before\" \"$row_temp_used_after\""
    print "    cat /proc/pressure/memory"
    print "  } >\"${run_dir}/bench-short-r${row}-swap-boundary.txt\""
    print "  [[ \"$row_pswpin_after\" == \"$row_pswpin_before\" && \"$row_pswpout_after\" == \"$row_pswpout_before\" && \"$row_temp_used_after\" == \"$row_temp_used_before\" ]] || { printf '\''FAIL: measured row %s had swap traffic; speed is paging-contaminated\\n'\'' \"$row\" >&2; exit 1; }"
  }
' "$stage1" >"$derived"
rm -- "$stage1"
chmod 0500 "$derived"
[[ "$(sha256sum "$derived" | cut -d' ' -f1)" == "$expected_derived" ]] || {
  printf 'FAIL: mechanically derived attempt-3 client hash mismatch\n' >&2
  exit 1
}
exec /bin/bash "$derived"
