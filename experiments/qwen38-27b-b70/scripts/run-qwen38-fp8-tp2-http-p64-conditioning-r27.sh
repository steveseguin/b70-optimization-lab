#!/usr/bin/env bash
set -euo pipefail

# Derive the audited promoted-image R9 server runner, replacing only campaign
# paths and the concurrency harness with the fixed-order factorial orchestrator.
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/../../.." && pwd)
base_runner="${repo_root}/experiments/qwen38-27b-b70/scripts/run-qwen38-fp8-tp2-http-p64-p2p1-screen-r9.sh"
factorial="${repo_root}/experiments/qwen38-27b-b70/scripts/qwen38-concurrency-conditioning-factorial.py"

fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
[[ -f "${base_runner}" && -f "${factorial}" ]] || fail "derived-runner input missing"

derived_dir=$(mktemp -d)
cleanup_derived() {
  rm -f "${derived_dir}/runner.sh"
  rmdir "${derived_dir}" 2>/dev/null || true
}
trap cleanup_derived EXIT
derived_runner="${derived_dir}/runner.sh"
sed \
  -e 's|repo_root=$(cd -- "${script_dir}/../../.." && pwd)|repo_root="${REPO_ROOT:?REPO_ROOT is required}"|' \
  -e 's|qwen38-fp8-tp2-http-p64-p2p1-screen-20260826-r9|qwen38-fp8-tp2-http-p64-conditioning-20260826-r27|g' \
  -e 's|2026-08-26-qwen38-fp8-tp2-http-p64-p2p1-screen-r9-prereg.json|2026-08-26-qwen38-fp8-tp2-http-p64-conditioning-r27-prereg.json|' \
  -e 's|q38-official-fp8-f01e/vllm-p64-p2p1-r9|q38-official-fp8-f01e/vllm-p64-conditioning-r27|' \
  -e 's|PORT:-18089|PORT:-18113|' \
  -e 's|qwen38-fp8-tp2-p64-p2p1-screen-r9|qwen38-fp8-tp2-p64-conditioning-r27|' \
  -e 's|harness="${repo_root}/scripts/bench-openai-concurrency-oracle.py"|harness="${repo_root}/experiments/qwen38-27b-b70/scripts/qwen38-concurrency-conditioning-factorial.py"|' \
  "${base_runner}" >"${derived_runner}"
chmod 0755 "${derived_runner}"

REPO_ROOT="${repo_root}" "${derived_runner}"
