#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
classifier="${script_dir}/classify-q38-runtime-conflicts.py"
test_script=$(realpath "${BASH_SOURCE[0]}")
fixture_root=$(mktemp -d)
trap 'chmod -R u+rwX -- "$fixture_root"; rm -rf -- "$fixture_root"' EXIT

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
  printf 'Name:\t%s\nPPid:\t%s\n' "$comm" "$ppid" \
    >"${fixture_root}/${pid}/status"
  printf '%s\n' "$comm" >"${fixture_root}/${pid}/comm"
  printf '%s\0' "$@" >"${fixture_root}/${pid}/cmdline"
}

scan_fixture() {
  local output=$1
  shift
  "$classifier" --proc-root "$fixture_root" --scanner-pid 101 \
    --supervisor-pid 100 --supervisor-starttime 1000 \
    --supervisor-script "$test_script" "$@" >"$output"
}

reset_fixture() {
  find "$fixture_root" -mindepth 1 -delete
  add_process 50 1 500 parent bash /bin/bash /tmp/launch-vision-supervisor.sh
  add_process 100 50 1000 supervisor bash /bin/bash "$test_script"
  add_process 101 100 1001 scanner python3 python3 "$classifier"
}

# Self-match and empty-cmdline clear fixtures.
reset_fixture
add_process 200 50 2000 helper bash /bin/bash /tmp/qwen38-flash-next-diagnostic-helper.sh
add_process 201 50 2001 pgrep pgrep -af 'vllm|qwen38-flash-next|torch.distributed|xccl_probe'
add_process 202 50 2002 kworker kworker
: >"${fixture_root}/202/cmdline"
scan_fixture "${fixture_root}/self-match.json"
jq -e '.status == "clear" and (.conflicts | length) == 0 and
  (.errors | length) == 0 and .binding.supervisor.pid == 100 and
  .binding.supervisor.starttime == 1000 and
  .binding.direct_parent.pid == 50 and
  .binding.excluded_pids == [101, 100, 50]' \
  "${fixture_root}/self-match.json" >/dev/null

# Exact argv owners plus worker/API/engine names with empty cmdlines and
# 15-character Linux comm truncation variants must all be positive.
reset_fixture
add_process 300 50 3000 vllm vllm /home/steve/.venvs/vllm-xpu/bin/vllm serve /mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8
add_process 301 50 3001 distributed python python -m torch.distributed.run --nproc_per_node=4 /tmp/worker.py
add_process 302 50 3002 collective python python /home/steve/llm-optimizations/tools/xccl_probe.py allreduce
add_process 303 50 3003 'VLLM::Worker'
add_process 304 50 3004 APIServer
add_process 305 50 3005 EngineCore
add_process 306 50 3006 'VLLM::EngineCor'
add_process 307 50 3007 'VLLM::APIServ'
add_process 308 50 3008 api_script python python /tmp/vllm/entrypoints/openai/api_server.py
for pid in 303 304 305 306 307; do : >"${fixture_root}/${pid}/cmdline"; done
set +e
scan_fixture "${fixture_root}/runtime-positive.json"
rc=$?
set -e
(( rc == 1 ))
jq -e '.status == "conflict" and (.errors | length) == 0 and
  (.conflicts | length) == 9 and
  ([.conflicts[].reason] | sort) == [
    "torch-distributed-run", "vllm-api-server", "vllm-named-api-server",
    "vllm-named-api-server", "vllm-named-engine-core",
    "vllm-named-engine-core", "vllm-named-worker", "vllm-serve", "xccl-probe"
  ]' "${fixture_root}/runtime-positive.json" >/dev/null

# A structurally excluded supervisor remains a conflict when its comm is a
# runtime owner: exclusion cannot hide a positive process.
reset_fixture
printf '%s\n' 'VLLM::Worker' >"${fixture_root}/100/comm"
set +e
scan_fixture "${fixture_root}/fabricated-exclusion.json"
rc=$?
set -e
(( rc == 1 ))
jq -e '.status == "conflict" and (.conflicts | length) == 1 and
  .conflicts[0].pid == 100 and .conflicts[0].was_structurally_excluded == true and
  .conflicts[0].reason == "vllm-named-worker"' \
  "${fixture_root}/fabricated-exclusion.json" >/dev/null

# Missing/unreadable required files and identity changes are errors. The
# stat.after fixture deterministically represents PID reuse during a scan.
reset_fixture
add_process 400 50 4000 missing_status sleep /bin/sleep 1
rm "${fixture_root}/400/status"
add_process 401 50 4001 missing_cmdline sleep /bin/sleep 1
rm "${fixture_root}/401/cmdline"
add_process 402 50 4002 unreadable_cmdline sleep /bin/sleep 1
chmod 000 "${fixture_root}/402/cmdline"
add_process 403 50 4003 reused sleep /bin/sleep 1
write_stat "${fixture_root}/403/stat.after" 403 50 4999 reused
set +e
scan_fixture "${fixture_root}/read-errors.json"
rc=$?
set -e
(( rc == 2 ))
jq -e '.status == "error" and (.conflicts | length) == 0 and
  ([.errors[].pid] | sort) == [400, 401, 402, 403] and
  ([.errors[].field] | sort) == ["cmdline", "cmdline", "pid-reuse", "status"]' \
  "${fixture_root}/read-errors.json" >/dev/null

# Mixed positives and read failures retain both classes and still exit 2.
reset_fixture
add_process 500 50 5000 'VLLM::Worker'
: >"${fixture_root}/500/cmdline"
add_process 501 50 5001 broken sleep /bin/sleep 1
rm "${fixture_root}/501/status"
set +e
scan_fixture "${fixture_root}/mixed.json"
rc=$?
set -e
(( rc == 2 ))
jq -e '.status == "error-and-conflict" and (.conflicts | length) == 1 and
  (.errors | length) == 1 and .conflicts[0].pid == 500 and .errors[0].pid == 501' \
  "${fixture_root}/mixed.json" >/dev/null

# A wrong starttime cannot fabricate an exclusion for a reused supervisor PID.
reset_fixture
set +e
"$classifier" --proc-root "$fixture_root" --scanner-pid 101 \
  --supervisor-pid 100 --supervisor-starttime 9999 \
  --supervisor-script "$test_script" >"${fixture_root}/binding-pid-reuse.json"
rc=$?
set -e
(( rc == 2 ))
jq -e '.status == "error" and .errors[0].field == "binding" and
  (.errors[0].detail | contains("PID was reused"))' \
  "${fixture_root}/binding-pid-reuse.json" >/dev/null

# Exercise the same structural binding against live /proc without converting
# unrelated live processes into a fixture expectation.
live_starttime=$(python3 - "$$" <<'PY'
from pathlib import Path
import sys
text = Path(f"/proc/{sys.argv[1]}/stat").read_text()
print(text[text.rfind(")") + 1:].split()[19])
PY
)
set +e
"$classifier" --supervisor-pid "$$" --supervisor-starttime "$live_starttime" \
  --supervisor-script "$test_script" --binding-only \
  >"${fixture_root}/live-proc-binding.json"
rc=$?
set -e
if (( rc != 0 )); then
  jq . "${fixture_root}/live-proc-binding.json" >&2
  exit 1
fi
jq -e --argjson pid "$$" '.status == "clear" and .binding_only == true and
  .binding.supervisor.pid == $pid and (.errors | length) == 0' \
  "${fixture_root}/live-proc-binding.json" >/dev/null

printf 'PASS q38 runtime classifier binding, identity, read-error, and owner fixtures\n'
