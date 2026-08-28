#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
wrapper="${script_dir}/launch-tp4-ep4-eager-mtp4-3072-headroom29.sh"
state=/tmp/q38-mtp4-3072-supervisor
stop_file="${state}.stop"
run_dir=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-eager-mtp4-3072-r1-attempt1
compile_dir=/tmp/qwen38-flash-next-fp8-tp4-ep4-eager-mtp4-3072-r1-attempt1-compile
rpc_dir=/tmp/qwen38-flash-next-fp8-tp4-ep4-eager-mtp4-3072-r1-attempt1-rpc
expected=7ff6398a7f880c85d57f4fec3d40ca789bdde6201f887d33615b878e500923d3
[[ $# == 0 ]] || { printf 'FAIL: supervisor takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$wrapper" | cut -d' ' -f1)" == "$expected" ]] || {
  printf 'FAIL: frozen launcher hash mismatch\n' >&2
  exit 1
}
for path in "${state}.pid" "${state}.child.pid" "${state}.launcher.pid" "${state}.rc" "$stop_file"; do
  [[ ! -e "$path" ]] || { printf 'FAIL: refusing to overwrite %s\n' "$path" >&2; exit 1; }
done
printf '%s\n' "$$" >"${state}.pid"
set +e
timeout --signal=TERM --kill-after=30s 2100s \
  "$wrapper" --execute --ack 'RUN qwen38-flash-next-fp8-tp4-ep4-eager-mtp4-3072-r1' &
child=$!
printf '%s\n' "$child" >"${state}.child.pid"
launcher=""
for _ in $(seq 1 50); do
  mapfile -t descendants < <(pgrep -P "$child" || true)
  if [[ "${#descendants[@]}" == 1 ]]; then
    launcher=${descendants[0]}
    break
  fi
  kill -0 "$child" 2>/dev/null || break
  sleep .2
done
if [[ -z "$launcher" ]]; then
  printf 'FAIL: bounded launcher descendant was not uniquely identified\n' >&2
  kill -TERM "$child" 2>/dev/null || true
  wait "$child" 2>/dev/null || true
  tmp="${state}.rc.tmp.$$"
  printf '70\n' >"$tmp"
  mv "$tmp" "${state}.rc"
  exit 70
fi
printf '%s\n' "$launcher" >"${state}.launcher.pid"
requested_stop=0
valid_stop=1
while kill -0 "$child" 2>/dev/null; do
  if [[ -e "$stop_file" ]]; then
    if [[ "$(wc -l < "$stop_file")" != 1 ]] || \
       ! grep -Fxq 'STOP after completed preregistered requests' "$stop_file"; then
      printf 'FAIL: invalid stop sentinel\n' >&2
      valid_stop=0
    fi
    kill -TERM "$launcher" 2>/dev/null || true
    requested_stop=1
    break
  fi
  sleep 2
done
wait "$child"
rc=$?
set -e
if (( requested_stop == 1 )); then
  for _ in $(seq 1 30); do
    server_pid=$(cat "${run_dir}/server.pid" 2>/dev/null || true)
    if [[ -z "$server_pid" || ! -e "/proc/${server_pid}" ]]; then
      break
    fi
    sleep 1
  done
  server_pid=$(cat "${run_dir}/server.pid" 2>/dev/null || true)
  if [[ -n "$server_pid" && -e "/proc/${server_pid}" ]] || \
     ss -ltn 2>/dev/null | grep -q ':19665 ' || \
     [[ -e "$compile_dir" || -e "$rpc_dir" ]]; then
    printf 'FAIL: descendant-aware shutdown did not clean all frozen state\n' >&2
    rc=70
  elif (( valid_stop == 0 )); then
    rc=65
  else
    rc=0
  fi
fi
tmp="${state}.rc.tmp.$$"
printf '%s\n' "$rc" >"$tmp"
mv "$tmp" "${state}.rc"
exit "$rc"
