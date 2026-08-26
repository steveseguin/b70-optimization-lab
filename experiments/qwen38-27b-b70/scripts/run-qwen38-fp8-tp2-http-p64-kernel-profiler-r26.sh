#!/usr/bin/env bash
set -euo pipefail

# Reuse the audited R11 profiler runner with only the candidate identity,
# campaign paths, and corrected shape-variant qualifier changed. Keeping the
# derivation explicit avoids maintaining a second near-identical long runner.
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/../../.." && pwd)
base_runner="${repo_root}/experiments/qwen38-27b-b70/scripts/run-qwen38-fp8-tp2-http-p64-p2p1-profiler-r11.sh"
candidate_image='neural-download/vllm-openai-xpu:f01e-kernel-1e90-r13'
expected_image_id='sha256:9403883cdbec3df988f486815f9dd528eb98baf0cc73d04ef3631ff0ac6a35b0'
expected_kernel_head='1e90ffa672ba02f17a909da11838a4c55b199783'

fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
[[ -f "${base_runner}" ]] || fail "base profiler runner is missing"
docker image inspect "${candidate_image}" >/dev/null 2>&1 \
  || fail "candidate image is not local"
[[ "$(docker image inspect "${candidate_image}" --format '{{.Id}}')" == "${expected_image_id}" ]] \
  || fail "candidate image ID changed"
[[ "$(docker image inspect "${candidate_image}" --format '{{index .Config.Labels "neural.download.kernel.head"}}')" == "${expected_kernel_head}" ]] \
  || fail "candidate kernel head changed"

derived_dir=$(mktemp -d)
cleanup_derived() {
  rm -f "${derived_dir}/runner.sh"
  rmdir "${derived_dir}" 2>/dev/null || true
}
trap cleanup_derived EXIT
derived_runner="${derived_dir}/runner.sh"
sed \
  -e 's|repo_root=$(cd -- "${script_dir}/../../.." && pwd)|repo_root="${REPO_ROOT:?REPO_ROOT is required}"|' \
  -e 's|qwen38-fp8-tp2-http-p64-p2p1-profiler-20260826-r11|qwen38-fp8-tp2-http-p64-kernel-profiler-20260826-r26|g' \
  -e 's|2026-08-26-qwen38-fp8-tp2-http-p64-p2p1-profiler-r11-prereg.json|2026-08-26-qwen38-fp8-tp2-http-p64-kernel-profiler-r26-prereg.json|' \
  -e 's|q38-official-fp8-f01e/vllm-p64-p2p1-profiler-r11|q38-official-fp8-f01e-kernel-1e90/vllm-p64-profiler-r26|' \
  -e 's|PORT:-18089|PORT:-18112|' \
  -e 's|qwen38-fp8-tp2-p64-p2p1-profiler-r11|qwen38-fp8-tp2-p64-kernel-profiler-r26|' \
  -e "s|image='vllm/vllm-openai-xpu@sha256:f01e24f6c7ff01f1e0662234255a1372297d1dbd89d003cf13c8fad3eab1ba4f'|image='${candidate_image}'|" \
  "${base_runner}" >"${derived_runner}"

# R11 incorrectly required sequential-oracle identity for this accepted
# output-isolated batch-shape lane. Preserve every batch gate while removing
# only that incompatible pilot/exact-oracle requirement.
sed -i 's/ --active-slots 64 --pilot \\/ --active-slots 64/' "${derived_runner}"
sed -i '/--pilot-require-batch-gates --expected-oracle-rows 64/d' "${derived_runner}"
chmod 0755 "${derived_runner}"

REPO_ROOT="${repo_root}" exec "${derived_runner}"
