#!/usr/bin/env bash
set -Eeuo pipefail

self=$(readlink -f -- "$0")

if [[ "${1:-}" == "--fake-server" ]]; then
  [[ $# == 2 ]] || exit 2
  exec python3 -m http.server "$2" --bind 127.0.0.1
fi

if [[ "${1:-}" == "--fake-launcher" ]]; then
  [[ $# == 3 ]] || exit 2
  test_root=$2
  port=$3
  compile_dir="${test_root}/compile"
  rpc_dir="${test_root}/rpc"
  mkdir -p "$compile_dir" "$rpc_dir"
  server_pid=""
  cleanup() {
    set +e
    if [[ -n "$server_pid" ]] && kill -0 "$server_pid" 2>/dev/null; then
      kill -TERM -- "-${server_pid}" 2>/dev/null || true
      wait "$server_pid" 2>/dev/null || true
    fi
    rmdir "$compile_dir" "$rpc_dir" 2>/dev/null || true
  }
  trap cleanup EXIT
  setsid "$self" --fake-server "$port" >"${test_root}/server.log" 2>&1 &
  server_pid=$!
  printf '%s\n' "$server_pid" >"${test_root}/server.pid"
  wait "$server_pid"
  server_pid=""
  exit 0
fi

[[ $# == 0 ]] || { printf 'FAIL: unexpected arguments\n' >&2; exit 2; }

test_root=$(mktemp -d /tmp/q38-supervisor-control-test.XXXXXX)
port=29664
child=""
cleanup_test() {
  set +e
  if [[ -n "$child" ]] && kill -0 "$child" 2>/dev/null; then
    kill -TERM "$child" 2>/dev/null || true
    wait "$child" 2>/dev/null || true
  fi
  if [[ -s "${test_root}/server.pid" ]]; then
    server_pid=$(cat "${test_root}/server.pid")
    if kill -0 "$server_pid" 2>/dev/null; then
      kill -TERM -- "-${server_pid}" 2>/dev/null || true
      wait "$server_pid" 2>/dev/null || true
    fi
  fi
  find "$test_root" -mindepth 1 -delete 2>/dev/null || true
  rmdir "$test_root" 2>/dev/null || true
}
trap cleanup_test EXIT

ss -ltn 2>/dev/null | grep -q ":${port} " && {
  printf 'FAIL: test port %s is already open\n' "$port" >&2
  exit 1
}

timeout --signal=TERM --kill-after=5s 30s \
  "$self" --fake-launcher "$test_root" "$port" &
child=$!

launcher=""
for _ in $(seq 1 50); do
  mapfile -t descendants < <(pgrep -P "$child" || true)
  if [[ "${#descendants[@]}" == 1 ]]; then
    launcher=${descendants[0]}
    break
  fi
  kill -0 "$child" 2>/dev/null || break
  sleep .1
done
[[ -n "$launcher" ]] || { printf 'FAIL: launcher descendant not found\n' >&2; exit 1; }

for _ in $(seq 1 50); do
  ss -ltn 2>/dev/null | grep -q ":${port} " && break
  sleep .1
done
ss -ltn 2>/dev/null | grep -q ":${port} " || {
  printf 'FAIL: detached fake server did not open its listener\n' >&2
  exit 1
}

server_pid=$(cat "${test_root}/server.pid")
kill -TERM "$launcher"
set +e
wait "$child"
child_rc=$?
set -e
child=""

for _ in $(seq 1 50); do
  if ! kill -0 "$server_pid" 2>/dev/null && \
     ! ss -ltn 2>/dev/null | grep -q ":${port} "; then
    break
  fi
  sleep .1
done

[[ "$child_rc" == 143 ]] || {
  printf 'FAIL: bounded wrapper rc=%s, expected 143 after launcher TERM\n' "$child_rc" >&2
  exit 1
}
[[ ! -e "/proc/${server_pid}" ]] || { printf 'FAIL: detached server remains\n' >&2; exit 1; }
! ss -ltn 2>/dev/null | grep -q ":${port} " || { printf 'FAIL: listener remains\n' >&2; exit 1; }
[[ ! -e "${test_root}/compile" && ! -e "${test_root}/rpc" ]] || {
  printf 'FAIL: launcher cleanup paths remain\n' >&2
  exit 1
}

printf 'PASS: signalling the timeout descendant reached launcher cleanup; detached server, listener, and temporary paths are absent\n'
