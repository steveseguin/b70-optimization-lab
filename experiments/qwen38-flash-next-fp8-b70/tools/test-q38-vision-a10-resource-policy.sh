#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
wrapper="${script_dir}/launch-tp4-mtp0-current-vision-a10.sh"
client="${script_dir}/run-tp4-mtp0-current-vision-a10-client.sh"
inner="${script_dir}/supervise-tp4-mtp0-current-vision-a10-inner.sh"
outer="${script_dir}/supervise-tp4-mtp0-current-vision-a10-swap64.sh"
watchdog="${script_dir}/watch-tp4-mtp0-current-vision-a10-resources.sh"

for file in "$wrapper" "$client" "$inner" "$outer" "$watchdog"; do
  [[ -f "$file" && ! -L "$file" ]] || { printf 'FAIL missing regular file %s\n' "$file" >&2; exit 1; }
  bash -n "$file"
done

grep -Fxq 'export ATTEMPT=10' "$wrapper"
grep -Fxq 'export PORT=19689' "$wrapper"
grep -Fxq 'export COMPILE_CACHE_DIR=/tmp/q38v-a10-c' "$wrapper"
grep -Fxq 'export RPC_DIR=/tmp/q38v-a10-r' "$wrapper"
! grep -Eq 'ATTEMPT=9|PORT=19688|q38v-a9' "$wrapper"

grep -Fq '/var/tmp/q38-vision-a10-resource/derived-supervisor.sh' "$client"
grep -Fq 'http://127.0.0.1:19689' "$client"
grep -Fq 'vision-attempt10-summary.json' "$client"
! grep -Eq 'vision-a9|attempt9|19688|q38v-a9' "$client"

grep -Fq '20260828-tp4-mtp0-fixed-vision-attempt9-result.json' "$inner"
grep -Fq 'expected_attempt9_closeout=a23825dffb6edf7238744c60e7d28480bbc9e95b5c76fa62c01675e8743331d7' "$inner"
grep -Fq 'expected_attempt9_manifest=c7daeced21a50cdf7fae02531b845fec4dd17ccdb98b495a4e9b3faffd947b06' "$inner"
grep -Fq '.classification.checkpoint_shards_completed == 5' "$inner"
grep -Fq '.resource_evidence.trip_sample.swap_free_kib == 3414672' "$inner"
grep -Fq 'compile_dir=/tmp/q38v-a10-c' "$inner"
grep -Fq 'rpc_dir=/tmp/q38v-a10-r' "$inner"
grep -Fq 'deadline_epoch=$((journal_start_epoch + 15000))' "$inner"
grep -Fq 'mem_available_kib < 10 * 1024 * 1024 || swap_free_kib < 5 * 1024 * 1024' "$inner"
grep -Fq 'root_available_bytes >= 40 * 1024 * 1024 * 1024' "$inner"
! grep -Eq 'attempt8_closeout|q38v-a9|port == 19688' "$inner"

grep -Fxq 'swapfile=/var/tmp/q38-vision-a10-64g.swap' "$outer"
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
grep -Fq 'expected_attempt9_closeout=a23825dffb6edf7238744c60e7d28480bbc9e95b5c76fa62c01675e8743331d7' "$outer"
grep -Fq 'expected_attempt9_manifest=c7daeced21a50cdf7fae02531b845fec4dd17ccdb98b495a4e9b3faffd947b06' "$outer"
grep -Fq 'final_user_active_epoch" == "$user_active_epoch' "$outer"

grep -Fxq 'mem_floor_kib=10485760' "$watchdog"
grep -Fxq 'swap_free_floor_kib=5242880' "$watchdog"
grep -Fq 'MemAvailable below 10 GiB' "$watchdog"
grep -Fq 'SwapFree below 5 GiB' "$watchdog"
grep -Fq 'memory PSI full avg10 >=5.0' "$watchdog"
grep -Fq 'kernel journal event-block policy refused the attempt-10 window' "$watchdog"

printf 'PASS vision attempt-10 swap/resource policy static fixture\n'
