#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
wrapper="${script_dir}/launch-tp4-ep4-eager-mtp4-1536-headroom29.sh"
state=/tmp/q38-mtp4-1536-supervisor
stop_file="${state}.stop"
expected=907eadac18cf17de65fd6cb09b93341a0e2d756b016cbbe80aafd418577dfd8c
[[ $# == 0 ]] || { printf 'FAIL: supervisor takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$wrapper" | cut -d' ' -f1)" == "$expected" ]] || {
  printf 'FAIL: frozen launcher hash mismatch\n' >&2
  exit 1
}
for path in "${state}.pid" "${state}.child.pid" "${state}.rc" "$stop_file"; do
  [[ ! -e "$path" ]] || { printf 'FAIL: refusing to overwrite %s\n' "$path" >&2; exit 1; }
done
printf '%s\n' "$$" > "${state}.pid"
set +e
timeout --signal=TERM --kill-after=30s 1800s \
  "$wrapper" --execute --ack 'RUN qwen38-flash-next-fp8-tp4-ep4-eager-mtp4-1536-r1' &
child=$!
printf '%s\n' "$child" > "${state}.child.pid"
while kill -0 "$child" 2>/dev/null; do
  if [[ -e "$stop_file" ]]; then
    if ! grep -Fxq 'STOP after completed preregistered requests' "$stop_file"; then
      printf 'FAIL: invalid stop sentinel\n' >&2
    fi
    kill -TERM "$child" 2>/dev/null || true
    break
  fi
  sleep 2
done
wait "$child"
rc=$?
set -e
tmp="${state}.rc.tmp.$$"
printf '%s\n' "$rc" > "$tmp"
mv "$tmp" "${state}.rc"
exit "$rc"
