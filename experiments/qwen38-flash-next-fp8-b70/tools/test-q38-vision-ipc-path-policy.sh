#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/launch-tp4-ep4-eager-mtp0-vision-512-base.sh"
uuid_fixture=ffffffff-ffff-4fff-bfff-ffffffffffff
limit=107
short_root=/tmp/q38v-a4-r
old_root=/tmp/qwen38-flash-next-fp8-tp4-ep4-eager-mtp0-vision-512-r1-attempt3-rpc
short_path="${short_root}/${uuid_fixture}"
old_path="${old_root}/${uuid_fixture}"
short_bytes=$(LC_ALL=C printf '%s' "$short_path" | wc -c)
old_bytes=$(LC_ALL=C printf '%s' "$old_path" | wc -c)

[[ "${#uuid_fixture}" == 36 ]]
[[ "$short_bytes" == 51 && "$short_bytes" -le "$limit" ]]
[[ "$old_bytes" == 109 && "$old_bytes" -gt "$limit" ]]

ipc_line=$(grep -nF "grep -Fq 'zmq.error.ZMQError: ipc path'" "$base" | cut -d: -f1)
worker_line=$(grep -nF "if ! grep -Fq 'Worker_TP'" "$base" | cut -d: -f1)
offload_line=$(grep -nF 'verify_offload_receipt || fail' "$base" | head -1 | cut -d: -f1)
[[ "$ipc_line" =~ ^[1-9][0-9]*$ && "$worker_line" =~ ^[1-9][0-9]*$ &&
   "$offload_line" =~ ^[1-9][0-9]*$ ]]
(( ipc_line < worker_line && worker_line < offload_line ))

classify_fixture() {
  local log=$1
  if grep -Fq 'zmq.error.ZMQError: ipc path' "$log" &&
     grep -Fq 'is longer than 107 characters' "$log"; then
    printf 'ipc-limit\n'
  elif ! grep -Fq 'Worker_TP' "$log"; then
    printf 'pre-worker-other\n'
  else
    printf 'worker-or-later\n'
  fi
}

fixture_root=$(mktemp -d)
trap 'rm -rf -- "$fixture_root"' EXIT
printf 'zmq.error.ZMQError: ipc path x is longer than 107 characters\n' \
  >"${fixture_root}/ipc.log"
printf 'APIServer stopped before worker construction\n' >"${fixture_root}/pre-worker.log"
printf 'Worker_TP0 started\n' >"${fixture_root}/worker.log"
[[ "$(classify_fixture "${fixture_root}/ipc.log")" == ipc-limit ]]
[[ "$(classify_fixture "${fixture_root}/pre-worker.log")" == pre-worker-other ]]
[[ "$(classify_fixture "${fixture_root}/worker.log")" == worker-or-later ]]

printf 'PASS short_uuid_path_bytes=%s old_uuid_path_bytes=%s limit=%s failure_order=ipc,pre-worker,offload\n' \
  "$short_bytes" "$old_bytes" "$limit"
