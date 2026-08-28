#!/usr/bin/env bash
set -Eeuo pipefail

repo=/home/steve/llm-optimizations
run_dir=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-eager-mtp4-3072-r1-attempt1
harness="${repo}/scripts/bench-openai-token-depth-suite.py"
fixture="${repo}/data/qwen27-exact-depth/qwen38-flash-next-bcd9f01-exact-depth-v1.json"
expected_harness=8f162c1ab9fde7e0daffed2c4f0d6ff061ad6076c5de716e36f3d883ab4a1067
expected_fixture=c44fccbaf600cc506d8ed0cc7357161057b86abc44469b611be71db97558061d
[[ $# == 1 && ( "$1" == 1 || "$1" == 2 ) ]] || { printf 'usage: %s 1|2\n' "$0" >&2; exit 2; }
request=$1
output="${run_dir}/exact-depth-2048-request${request}.json"
unexpected_partial="${output%.json}.unexpected-partial.json"
log="${run_dir}/client-request${request}.log"
pid_file="${run_dir}/client-request${request}.pid"
rc_file="${run_dir}/client-request${request}.rc"
[[ -d "$run_dir" ]] || { printf 'FAIL: run directory missing\n' >&2; exit 1; }
[[ "$(sha256sum "$harness" | cut -d' ' -f1)" == "$expected_harness" ]] || { printf 'FAIL: harness hash mismatch\n' >&2; exit 1; }
[[ "$(sha256sum "$fixture" | cut -d' ' -f1)" == "$expected_fixture" ]] || { printf 'FAIL: fixture hash mismatch\n' >&2; exit 1; }
for path in "$output" "$unexpected_partial" "$log" "$pid_file" "$rc_file"; do
  [[ ! -e "$path" ]] || { printf 'FAIL: refusing to overwrite %s\n' "$path" >&2; exit 1; }
done
[[ -s "${run_dir}/metrics-before-request${request}.prom" ]] || { printf 'FAIL: pre-request metrics missing\n' >&2; exit 1; }
if [[ "$request" == 2 ]]; then
  gate="${run_dir}/request1-gates-passed.txt"
  [[ "$(wc -l < "$gate" 2>/dev/null || true)" == 1 ]] || { printf 'FAIL: request-one gate sentinel missing\n' >&2; exit 1; }
  grep -Fxq 'PASS request1 exact usage length MTP0 token hash cache-zero 100-events 99-intervals and MTP4 positions 0 1 2 3' "$gate" || { printf 'FAIL: request-one gate sentinel invalid\n' >&2; exit 1; }
fi
printf '%s\n' "$$" >"$pid_file"
set +e
timeout --signal=TERM --kill-after=10s 370s \
  /home/steve/.venvs/vllm-xpu/bin/python "$harness" \
  --execute \
  --fixture "$fixture" \
  --depth 2048 \
  --context-capacity 3072 \
  --base-url http://127.0.0.1:19665 \
  --model qwen38-flash-next-fp8-tp4 \
  --response-adapter vllm \
  --timeout 360 \
  --out "$output" >"$log" 2>&1
rc=$?
set -e
if [[ "$rc" != 0 && -e "$output" ]]; then
  if ! /home/steve/.venvs/vllm-xpu/bin/python - "$output" <<'PY'
import json
import pathlib
import sys

payload = json.loads(pathlib.Path(sys.argv[1]).read_text())
assert payload.get("schema") == "openai-token-depth-benchmark-v1"
assert isinstance(payload.get("gate", {}).get("passed"), bool)
PY
  then
    mv "$output" "$unexpected_partial"
  fi
fi
tmp="${rc_file}.tmp.$$"
printf '%s\n' "$rc" >"$tmp"
mv "$tmp" "$rc_file"
exit "$rc"
