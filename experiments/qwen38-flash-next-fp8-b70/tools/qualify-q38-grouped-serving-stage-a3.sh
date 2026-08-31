#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/qualify-q38-grouped-serving-stage-a2.sh"
expected_base=870529a3e9c37599f77f38460795a2651e9a3ff4701c1a46d7dac73f8b8152a2
expected_source=2e9415c3c79c9dc27b5e257bde755c4e8257a6f98f871eaf49629adff3566314
expected_derived=c24f66abe2c3b5fb997119d295ea6455bc531d1ce5a63a068001179358f8ae15

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

derive() {
  awk '
    $0 == "refuse_render_owners() {" {
      in_render_guard = 1
    }
    in_render_guard == 1 && $0 == "  done" {
      print
      print "  return 0"
      in_render_guard = 0
      next
    }
    $0 == "result=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/grouped-serving-stage-eeee7d6-a2-qualification" {
      print "result=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/grouped-serving-stage-eeee7d6-a2-qualification-a3"
      next
    }
    { print }
  ' "$base"
}

[[ $# == 0 ]] || fail "this frozen qualification takes no arguments"
[[ -f "$base" && ! -L "$base" ]] || fail "A2 qualification source is absent or not regular"
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]] || fail "A2 qualification source drifted"
source_hash=$(sed 's/^expected_source=.*/expected_source=SOURCE_HASH/' "${BASH_SOURCE[0]}" | sha256sum | cut -d' ' -f1)
[[ "$source_hash" == "$expected_source" ]] || fail "A3 wrapper source drifted"

derived_hash=$(derive | sha256sum | cut -d' ' -f1)
[[ "$derived_hash" == "$expected_derived" ]] || fail "derived A3 qualification drifted"

qualification_tmp=$(mktemp /tmp/q38-grouped-stage-a3.XXXXXX.sh)
trap 'rm -f -- "$qualification_tmp"' EXIT
derive >"$qualification_tmp"
chmod 700 "$qualification_tmp"
bash "$qualification_tmp"
