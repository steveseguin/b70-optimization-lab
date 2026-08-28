#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
wrapper="${script_dir}/launch-tp4-mtp0-current-vision-a11.sh"
client="${script_dir}/run-tp4-mtp0-current-vision-a11-client.sh"
inner="${script_dir}/supervise-tp4-mtp0-current-vision-a11-inner.sh"
outer="${script_dir}/supervise-tp4-mtp0-current-vision-a11-swap64.sh"
watchdog="${script_dir}/watch-tp4-mtp0-current-vision-a11-resources.sh"

for file in "$wrapper" "$client" "$inner" "$outer" "$watchdog"; do
  [[ -f "$file" && ! -L "$file" ]] || { printf 'FAIL missing regular file %s\n' "$file" >&2; exit 1; }
  bash -n "$file"
done

grep -Fxq 'export ATTEMPT=10' "$wrapper"
grep -Fxq 'export PORT=19690' "$wrapper"
grep -Fxq 'export COMPILE_CACHE_DIR=/tmp/q38v-a11-c' "$wrapper"
grep -Fxq 'export RPC_DIR=/tmp/q38v-a11-r' "$wrapper"
! grep -Eq 'ATTEMPT=10|PORT=19689|q38v-a10' "$wrapper"

grep -Fq '/var/tmp/q38-vision-a11-resource/derived-supervisor.sh' "$client"
grep -Fq 'http://127.0.0.1:19690' "$client"
grep -Fq 'vision-attempt11-summary.json' "$client"
! grep -Eq 'vision-a10|attempt10|19689|q38v-a10' "$client"

grep -Fq '20260828-tp4-mtp0-fixed-vision-attempt10-administrative-closeout.json' "$inner"
grep -Fq 'expected_attempt10_closeout=0862f156b15d3f72d295b9966f2fb5e9ce30d1d9494946981b718a22efc2732d' "$inner"
grep -Fq 'expected_attempt10_manifest=68470e550fcdbb667137bf5da8402647995dddc69bf06595a7b07193556b80bd' "$inner"
grep -Fq 'expected_attempt10_manifest_entries=47' "$inner"
grep -Fq 'compile_dir=/tmp/q38v-a11-c' "$inner"
grep -Fq 'rpc_dir=/tmp/q38v-a11-r' "$inner"
grep -Fq 'deadline_epoch=$((journal_start_epoch + 15000))' "$inner"
grep -Fq 'mem_available_kib < 10 * 1024 * 1024 || swap_free_kib < 5 * 1024 * 1024' "$inner"
grep -Fq 'root_available_bytes >= 40 * 1024 * 1024 * 1024' "$inner"
grep -Fq 'mem_available_kib >= 104 * 1024 * 1024' "$inner"
grep -Fq 'less than 104 GiB host memory is available' "$inner"
! grep -Eq 'attempt9_closeout|q38v-a10|port == 19689|less than 105 GiB' "$inner"

grep -Fxq 'swapfile=/var/tmp/q38-vision-a11-64g.swap' "$outer"
grep -Fxq 'swap_bytes=68719476736' "$outer"
grep -Fxq 'precreate_floor_bytes=111669149696' "$outer"
grep -Fxq 'root_floor_bytes=42949672960' "$outer"
grep -Fxq 'mem_floor_kib=10485760' "$outer"
grep -Fxq 'swapoff_mem_reserve_kib=16777216' "$outer"
grep -Fq 'outer_deadline_epoch=$((journal_start_epoch + 16200))' "$outer"
grep -Fq '/sbin/swapon -p -1 -- "$swapfile"' "$outer"
grep -Fq '900s /usr/bin/sudo -S -p' "$outer"
grep -Fq '/sbin/swapoff -- "$swapfile"' "$outer"
grep -Fq '/usr/bin/unlink -- "$swapfile"' "$outer"
grep -Fq 'cmp -s "${resource_dir}/swaps-before-layout.txt" "${resource_dir}/swaps-restored-layout.txt"' "$outer"
grep -Fq 'terminal_server_group_absent || resource_fault=1' "$outer"
grep -Fq 'expected_attempt10_closeout=0862f156b15d3f72d295b9966f2fb5e9ce30d1d9494946981b718a22efc2732d' "$outer"
grep -Fq 'expected_attempt10_manifest=68470e550fcdbb667137bf5da8402647995dddc69bf06595a7b07193556b80bd' "$outer"
grep -Fq 'expected_attempt10_manifest_entries=47' "$outer"
grep -Fq 'final_user_active_epoch" == "$user_active_epoch' "$outer"

grep -Fxq 'mem_floor_kib=10485760' "$watchdog"
grep -Fxq 'swap_free_floor_kib=5242880' "$watchdog"
grep -Fq 'MemAvailable below 10 GiB' "$watchdog"
grep -Fq 'SwapFree below 5 GiB' "$watchdog"
grep -Fq 'memory PSI full avg10 >=5.0' "$watchdog"
grep -Fq 'kernel journal event-block policy refused the attempt-11 window' "$watchdog"

printf 'PASS vision attempt-11 swap/resource policy static fixture\n'
