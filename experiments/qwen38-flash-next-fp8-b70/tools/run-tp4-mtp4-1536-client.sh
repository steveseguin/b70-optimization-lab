#!/usr/bin/env bash
set -Eeuo pipefail

repo=/home/steve/llm-optimizations
run_dir=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-eager-mtp4-1536-r1-attempt1
harness="${repo}/scripts/bench-openai-concurrency.py"
expected_harness=d590c63c87b1e664417b4198dbbb873cbe4f252509fa8f9fc50830efca2b4cf4
[[ $# == 1 && ( "$1" == 1 || "$1" == 2 ) ]] || { printf 'usage: %s 1|2\n' "$0" >&2; exit 2; }
request=$1
output="${run_dir}/bench-context1k-o256-c1-r${request}.json"
log="${run_dir}/client-request${request}.log"
pid_file="${run_dir}/client-request${request}.pid"
rc_file="${run_dir}/client-request${request}.rc"
[[ -d "$run_dir" ]] || { printf 'FAIL: run directory missing\n' >&2; exit 1; }
[[ "$(sha256sum "$harness" | cut -d' ' -f1)" == "$expected_harness" ]] || { printf 'FAIL: harness hash mismatch\n' >&2; exit 1; }
for path in "$output" "$log" "$pid_file" "$rc_file"; do
  [[ ! -e "$path" ]] || { printf 'FAIL: refusing to overwrite %s\n' "$path" >&2; exit 1; }
done
[[ -s "${run_dir}/metrics-before-request${request}.prom" ]] || { printf 'FAIL: pre-request metrics missing\n' >&2; exit 1; }
if [[ "$request" == 2 ]]; then
  gate="${run_dir}/request1-gates-passed.txt"
  [[ "$(wc -l < "$gate" 2>/dev/null || true)" == 1 ]] || { printf 'FAIL: request-one gate sentinel missing\n' >&2; exit 1; }
  grep -Fxq 'PASS request1 exact usage hash cache and MTP4 positions 0 1 2 3' "$gate" || { printf 'FAIL: request-one gate sentinel invalid\n' >&2; exit 1; }
fi
printf '%s\n' "$$" > "$pid_file"
set +e
timeout --signal=TERM --kill-after=10s 370s \
  /home/steve/.venvs/vllm-xpu/bin/python "$harness" \
  --base-url http://127.0.0.1:19664 \
  --tokenizer /mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8 \
  --prompt-tokens 1038 --shared-prefix-tokens 0 --prompt-salt context-r1 \
  --output-tokens 256 --concurrency 1 --warmups 0 --timeout 360 \
  --seed 20260606 --output-json "$output" > "$log" 2>&1
rc=$?
set -e
if [[ "$rc" != 0 && -e "$output" ]]; then
  mv "$output" "${output%.json}.unexpected-partial.json"
fi
tmp="${rc_file}.tmp.$$"
printf '%s\n' "$rc" > "$tmp"
mv "$tmp" "$rc_file"
exit "$rc"
