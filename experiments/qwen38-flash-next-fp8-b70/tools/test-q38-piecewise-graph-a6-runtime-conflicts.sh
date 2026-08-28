#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
classifier="${script_dir}/classify-q38-runtime-conflicts.py"
shared_test="${script_dir}/test-q38-runtime-conflict-classifier.sh"
a6_supervisor="${script_dir}/supervise-tp4-mtp0-current-piecewise-graph-a6-swap64.sh"
fixture_root=$(mktemp -d)
trap 'chmod -R u+rwX -- "$fixture_root"; rm -rf -- "$fixture_root"' EXIT

[[ "$(sha256sum "$classifier" | cut -d' ' -f1)" == c6f9ee76fec1f3343c223ac8264312b6ec3ae6ad6c242e8154fb5d3e3d0ae390 ]]
[[ "$(sha256sum "$shared_test" | cut -d' ' -f1)" == fe146ba53bf0eb2f0c0ea60647fbdace353a39a564317e6375574815c2c2dd85 ]]
"$shared_test" >/dev/null

write_stat() {
  local path=$1 pid=$2 ppid=$3 starttime=$4 comm=$5 index
  printf '%s (%s) S %s' "$pid" "$comm" "$ppid" >"$path"
  for index in $(seq 1 17); do printf ' 0' >>"$path"; done
  printf ' %s\n' "$starttime" >>"$path"
}

add_process() {
  local pid=$1 ppid=$2 starttime=$3 comm=$4
  shift 4
  mkdir -p "${fixture_root}/${pid}"
  write_stat "${fixture_root}/${pid}/stat" "$pid" "$ppid" "$starttime" "$comm"
  printf 'Name:\t%s\nPPid:\t%s\n' "$comm" "$ppid" >"${fixture_root}/${pid}/status"
  printf '%s\n' "$comm" >"${fixture_root}/${pid}/comm"
  printf '%s\0' "$@" >"${fixture_root}/${pid}/cmdline"
}

reset_fixture() {
  find "$fixture_root" -mindepth 1 -delete
  add_process 50 1 500 parent bash /bin/bash /tmp/codex-orchestrator.sh
  add_process 100 50 1000 supervisor bash /bin/bash "$a6_supervisor"
  add_process 101 100 1001 scanner python3 python3 "$classifier"
}

scan_fixture() {
  local output=$1
  "$classifier" --proc-root "$fixture_root" --scanner-pid 101 \
    --supervisor-pid 100 --supervisor-starttime 1000 \
    --supervisor-script "$a6_supervisor" >"$output"
}

# Actual attempt-6 controller paths and the former broad-search command text
# are not runtime owners. The exact scanner/supervisor/parent binding is clear.
reset_fixture
add_process 200 50 2000 inner bash /bin/bash /var/tmp/q38-piecewise-graph-a6-resource/derived-supervisor.sh
add_process 201 200 2001 launcher bash /bin/bash /var/tmp/q38-piecewise-graph-a6-resource/derived-launcher-compile1.sh
add_process 202 50 2002 pgrep pgrep -af 'vllm serve /mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8|VLLM::Worker_TP'
scan_fixture "${fixture_root}/a6-controller-self-match.json"
jq -e '.status == "clear" and (.conflicts | length) == 0 and
  (.errors | length) == 0 and .binding.supervisor.pid == 100 and
  .binding.direct_parent.pid == 50 and (.scanned_processes | length) == 6' \
  "${fixture_root}/a6-controller-self-match.json" >/dev/null

# Real attempt-5 runtime forms remain positive: the exact vLLM server argv and
# the worker comm recorded by the OOM evidence cannot be hidden by empty argv.
reset_fixture
add_process 300 50 3000 vllm /home/steve/.venvs/vllm-xpu/bin/vllm serve \
  /mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8 --port 19679 \
  --max-model-len 4352 --compilation-config '{"cudagraph_mode":"PIECEWISE"}'
for pid in 301 302 303 304; do
  add_process "$pid" 300 "$((3000 + pid))" 'VLLM::Worker_TP'
  : >"${fixture_root}/${pid}/cmdline"
done
set +e
scan_fixture "${fixture_root}/a5-runtime-positive.json"
rc=$?
set -e
(( rc == 1 ))
jq -e '.status == "conflict" and (.errors | length) == 0 and
  (.conflicts | length) == 5 and
  ([.conflicts[].reason] | sort) ==
    ["vllm-named-worker","vllm-named-worker","vllm-named-worker","vllm-named-worker","vllm-serve"]' \
  "${fixture_root}/a5-runtime-positive.json" >/dev/null

printf 'PASS attempt-6 controller/self-match negatives and attempt-5 runtime positives\n'
