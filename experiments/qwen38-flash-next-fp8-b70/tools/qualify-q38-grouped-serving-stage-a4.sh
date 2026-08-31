#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
base="${script_dir}/qualify-q38-grouped-serving-stage-a2.sh"
expected_base=870529a3e9c37599f77f38460795a2651e9a3ff4701c1a46d7dac73f8b8152a2
expected_inspector=60f0264f9971d699b8cac39afe9c55dba0d4b3566cc9b793e5465c3e3ebeefc2
expected_source=92863f116e809effdfdf769703e80959b96990b65d85c4d66d9ea09958482d41
expected_derived=894cc6b276647051d6dd34057d3a8158f97a0600a9261e990901c4e01845a3ae

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

derive() {
  awk -v inspector_hash="$expected_inspector" '
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
      print "result=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/grouped-serving-stage-eeee7d6-a2-qualification-a4"
      next
    }
    $0 == "inspector=\"${repo}/experiments/qwen38-flash-next-fp8-b70/tools/inspect-q38-grouped-serving-stage-a2.py\"" {
      print "inspector=\"${repo}/experiments/qwen38-flash-next-fp8-b70/tools/inspect-q38-grouped-serving-stage-a4.py\""
      next
    }
    $0 == "expected_inspector=b37a2e15d61826d1deca3b3dab03028e18b6e7f1a77776bd52b09a6d6d6d40d4" {
      print "expected_inspector=" inspector_hash
      next
    }
    { print }
  ' "$base"
}

[[ $# == 0 ]] || fail "this frozen qualification takes no arguments"
[[ -f "$base" && ! -L "$base" ]] || fail "A2 qualification source is absent or not regular"
[[ "$(sha256sum "$base" | cut -d' ' -f1)" == "$expected_base" ]] || fail "A2 qualification source drifted"
[[ "$(sha256sum "${script_dir}/inspect-q38-grouped-serving-stage-a4.py" | cut -d' ' -f1)" == "$expected_inspector" ]] || fail "A4 inspector drifted"
source_hash=$(sed 's/^expected_source=.*/expected_source=SOURCE_HASH/' "${BASH_SOURCE[0]}" | sha256sum | cut -d' ' -f1)
[[ "$source_hash" == "$expected_source" ]] || fail "A4 wrapper source drifted"

derived_hash=$(derive | sha256sum | cut -d' ' -f1)
[[ "$derived_hash" == "$expected_derived" ]] || fail "derived A4 qualification drifted"

qualification_tmp=$(mktemp /tmp/q38-grouped-stage-a4.XXXXXX.sh)
trap 'rm -f -- "$qualification_tmp"' EXIT
derive >"$qualification_tmp"
chmod 700 "$qualification_tmp"
bash "$qualification_tmp"
