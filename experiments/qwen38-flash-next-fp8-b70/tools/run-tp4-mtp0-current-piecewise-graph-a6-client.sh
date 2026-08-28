#!/usr/bin/env bash
set -Eeuo pipefail

repo=/home/steve/llm-optimizations
source_client="${repo}/experiments/qwen38-flash-next-fp8-b70/tools/run-tp4-mtp0-current-piecewise-graph-a1-client.sh"
expected_source=5886f5ba6127826f1122bc8ac26d4c1b328d9ab34674051e50cb5d985dbdaaaf
resource_dir=/var/tmp/q38-piecewise-graph-a6-resource
derived="${resource_dir}/derived-client.sh"
expected_derived=6124378a02578b95948ccd04cad92aab806a9a25cf23e1f7d0d24a949b7d2ce6

[[ $# == 0 ]] || { printf 'FAIL: attempt-6 client takes no arguments\n' >&2; exit 2; }
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
  -e 's|supervisor="${repo}/experiments/qwen38-flash-next-fp8-b70/tools/supervise-tp4-mtp0-current-piecewise-graph-a1.sh"|supervisor=/var/tmp/q38-piecewise-graph-a6-resource/derived-supervisor.sh|' \
  -e 's/q38-mtp0-current-piecewise-graph-a1/q38-mtp0-current-piecewise-graph-a6/g' \
  -e 's/attempt1/attempt6/g' \
  -e 's/19674/19680/g' \
  -e 's/q38-piecewise-a1/q38-piecewise-a6/g' \
  -e 's|^journalctl -k |timeout --signal=TERM --kill-after=5s 30s journalctl -k |' \
  "$source_client" >"$stage1"
awk '
  index($0, "grep -aFq \"enforce_eager=False\"") {
    print "for receipt in torchinductor_compile_threads_env=1 torchinductor_compile_threads_effective=1; do"
    print "  grep -Fxq \"$receipt\" \"${run_dir}/identity.txt\" || { printf \047FAIL: compile-thread identity receipt missing: %s\\n\047 \"$receipt\" >&2; exit 1; }"
    print "  grep -Fxq \"$receipt\" \"${run_dir}/torchinductor-compile-threads.txt\" || { printf \047FAIL: effective compile-thread receipt missing: %s\\n\047 \"$receipt\" >&2; exit 1; }"
    print "done"
    print "tr \047\\0\047 \047\\n\047 <\"/proc/${server_pid}/environ\" | grep -Fxq \047TORCHINDUCTOR_COMPILE_THREADS=1\047 || { printf \047FAIL: live server compile-thread environment missing\\n\047 >&2; exit 1; }"
  }
  $0 == "for row in 1 2 3; do" {
    print
    print "  read -r row_pswpin_before row_pswpout_before < <(awk '\''$1 == \"pswpin\" {a=$2} $1 == \"pswpout\" {b=$2} END {print a, b}'\'' /proc/vmstat)"
    print "  row_temp_used_before=$(awk '\''$1 == \"/var/tmp/q38-piecewise-graph-a6-64g.swap\" {print $4}'\'' /proc/swaps)"
    print "  [[ \"$row_pswpin_before\" =~ ^[0-9]+$ && \"$row_pswpout_before\" =~ ^[0-9]+$ && \"$row_temp_used_before\" =~ ^[0-9]+$ ]] || { printf '\''FAIL: measured-row swap baseline unavailable\\n'\'' >&2; exit 1; }"
    next
  }
  index($0, "\047tp\047:4,\047ep\047:4,\047mtp\047:0") {
    sub(/\047kv_cache_memory_bytes\047:201326592}/, "\047kv_cache_memory_bytes\047:201326592,\047torchinductor_compile_threads\047:1}")
  }
  { print }
  index($0, "write_atomic \"${run_dir}/bench-short-r${row}.rc\"") {
    print "  read -r row_pswpin_after row_pswpout_after < <(awk '\''$1 == \"pswpin\" {a=$2} $1 == \"pswpout\" {b=$2} END {print a, b}'\'' /proc/vmstat)"
    print "  row_temp_used_after=$(awk '\''$1 == \"/var/tmp/q38-piecewise-graph-a6-64g.swap\" {print $4}'\'' /proc/swaps)"
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
  printf 'FAIL: mechanically derived attempt-6 client hash mismatch\n' >&2
  exit 1
}
exec /bin/bash "$derived"
