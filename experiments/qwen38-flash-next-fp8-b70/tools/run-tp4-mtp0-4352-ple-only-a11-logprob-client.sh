#!/usr/bin/env bash
set -Eeuo pipefail

repo=/home/steve/llm-optimizations
script_dir=${repo}/experiments/qwen38-flash-next-fp8-b70/tools
supervisor=${script_dir}/supervise-tp4-mtp0-4352-ple-only-a11-logprob.sh
launcher=${script_dir}/launch-tp4-mtp0-4352-ple-only-a11-logprob.sh
probe=${script_dir}/run-exact-depth-logprob-repeat.py
depth_module=${repo}/scripts/bench-openai-token-depth-suite.py
fixture=${repo}/data/qwen27-exact-depth/qwen38-flash-next-bcd9f01-exact-depth-v1.json
state=/tmp/q38-mtp0-ple-only-a11-logprob
stop_file=${state}.stop
failure_file=${state}.failed
run_dir=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-eager-mtp0-4352-ple-only-r1-attempt11
supervisor_dir=${run_dir}-supervisor
base_url=http://127.0.0.1:19683
model=qwen38-flash-next-fp8-tp4
python=/home/steve/.venvs/vllm-xpu/bin/python
completed=0

write_atomic() {
  local path=$1 value=$2 tmp
  tmp="${path}.tmp.$$"
  printf '%s\n' "$value" >"$tmp"
  mv "$tmp" "$path"
}

fail_sentinel() {
  local rc=$?
  if (( completed == 0 )); then
    write_atomic "$failure_file" "FAIL PLE-only exact-4K API-logprob diagnostic client rc=${rc}"
  fi
}
trap fail_sentinel EXIT

[[ $# == 0 ]] || { printf 'FAIL: A11 client takes no arguments\n' >&2; exit 2; }
[[ "$(sha256sum "$launcher" | cut -d' ' -f1)" == 955505783af6ec3fbfe884c3a0134561d52d0597bc7dc65a94436013a9cbd225 ]]
[[ "$(sha256sum "$probe" | cut -d' ' -f1)" == 95a03d9c134168a2468957d7775bcb4e14df8fccb4d14ea9f596e99196edba4f ]]
[[ "$(sha256sum "$depth_module" | cut -d' ' -f1)" == 8f162c1ab9fde7e0daffed2c4f0d6ff061ad6076c5de716e36f3d883ab4a1067 ]]
[[ "$(sha256sum "$fixture" | cut -d' ' -f1)" == c44fccbaf600cc506d8ed0cc7357161057b86abc44469b611be71db97558061d ]]
[[ -d "$run_dir" && -d "$supervisor_dir" ]]
for artifact in health-before-client.json models-before-client.json metrics-before-client.prom \
  journal-before-client.log exact-4k-logprob-repeat.json exact-4k-logprob-repeat.log \
  exact-4k-logprob-repeat.rc client-gates-passed.txt; do
  [[ ! -e "${run_dir}/${artifact}" ]] || {
    printf 'FAIL: refusing to overwrite %s\n' "$artifact" >&2
    exit 1
  }
done

supervisor_pid=$(cat "${state}.pid" 2>/dev/null || true)
[[ "$supervisor_pid" =~ ^[1-9][0-9]*$ && -e "/proc/${supervisor_pid}" ]]
supervisor_command=$(tr '\0' ' ' <"/proc/${supervisor_pid}/cmdline")
[[ "$supervisor_command" == *"supervise-tp4-mtp0-4352-ple-only-a11-logprob.sh"* ]]
deadline_epoch=$(cat "${state}.deadline-epoch" 2>/dev/null || true)
[[ "$deadline_epoch" =~ ^[1-9][0-9]*$ ]]
(( deadline_epoch - $(date +%s) >= 2400 )) || {
  printf 'FAIL: less than 2400 seconds remain in supervised lifecycle\n' >&2
  exit 1
}
server_pid=$(cat "${run_dir}/server.pid" 2>/dev/null || true)
[[ "$server_pid" =~ ^[1-9][0-9]*$ && -e "/proc/${server_pid}" ]]
server_command=$(tr '\0' ' ' <"/proc/${server_pid}/cmdline")
[[ "$server_command" == *"vllm serve /mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8"* && \
   "$server_command" == *"--port 19683"* && \
   "$server_command" == *"--max-model-len 4352"* && \
   "$server_command" == *"--cpu-offload-gb 12.0"* && \
   "$server_command" == *"--cpu-offload-params ple_embedding.ngram_embedding.weight"* && \
   "$server_command" == *"--kv-cache-memory-bytes 134217728"* ]]
[[ "$server_command" != *"--speculative-config"* && \
   "$server_command" != *"--reasoning-parser"* ]]
for receipt in \
  'vllm_head=e5137bfd8ca2ca718c4fd93d86d54bb843e2999b' \
  'kernels_head=ad25aa9f69a2171612b9c6b83dfa82c69559f9e4' \
  'runtime_stage_build_head=2f829747503c77d4814834dffd0840fb1dd9f75a' \
  'tp=4 ep=4 all2all=allgather_reducescatter' \
  'moe_backend=triton eager=1 mtp=0 max_model_len=4352 max_num_batched_tokens=64' \
  'cpu_offload_gb=12.0' \
  'cpu_offload_params=ple_embedding.ngram_embedding.weight' \
  'kv_cache_memory_bytes=134217728' \
  'kv_cache_layout=BLHNC' \
  'reasoning_parser=absent' \
  'diagnostics=none'; do
  grep -Fxq "$receipt" "${run_dir}/identity.txt" || {
    printf 'FAIL: identity receipt missing: %s\n' "$receipt" >&2
    exit 1
  }
done

curl --connect-timeout 5 --max-time 20 -fsS "${base_url}/health" >"${run_dir}/health-before-client.json"
curl --connect-timeout 5 --max-time 20 -fsS "${base_url}/v1/models" >"${run_dir}/models-before-client.json"
curl --connect-timeout 5 --max-time 20 -fsS "${base_url}/metrics" >"${run_dir}/metrics-before-client.prom"
jq -e --arg model "$model" '.data | any(.id == $model and .max_model_len == 4352)' \
  "${run_dir}/models-before-client.json" >/dev/null
"$python" - "${run_dir}/metrics-before-client.prom" <<'PY'
import pathlib, re, sys
line = next((line for line in pathlib.Path(sys.argv[1]).read_text().splitlines()
             if line.startswith("vllm:cache_config_info{")), None)
assert line is not None
labels = dict(re.findall(r'(\w+)="([^"]*)"', line))
assert labels.get("kv_cache_memory_bytes") == "134217728", labels
assert labels.get("enable_prefix_caching") == "False", labels
assert int(labels.get("kv_cache_size_tokens", "0")) >= 4224, labels
PY
journal_start=$(cat "${supervisor_dir}/journal-start-epoch.txt")
journalctl -k --since "@${journal_start}" --no-pager >"${run_dir}/journal-before-client.log"
! grep -Eqi 'xe 0000:(23|27|43|47):00\.0.*(reset|fault|timeout|timed out|fatal|wedged|failed)' \
  "${run_dir}/journal-before-client.log"

set +e
timeout --signal=TERM --kill-after=10s 3800s "$python" "$probe" --execute \
  --depth-module "$depth_module" --fixture "$fixture" --base-url "$base_url" \
  --model "$model" --repeats 4 --top-logprobs 8 --timeout 900 \
  --request-id-prefix q38-ple-only-a11-logprob \
  --out "${run_dir}/exact-4k-logprob-repeat.json" \
  >"${run_dir}/exact-4k-logprob-repeat.log" 2>&1
probe_rc=$?
set -e
write_atomic "${run_dir}/exact-4k-logprob-repeat.rc" "$probe_rc"
(( probe_rc == 0 )) || exit "$probe_rc"
jq -e '
  .schema == "qwen38-exact-depth-logprob-repeat-v1" and
  .status == "passed" and .performance_credit == false and
  .identity.repeats == 4 and .identity.top_logprobs == 8 and
  .request.prompt_tokens == 4096 and
  .request.prompt_token_ids_sha256 == "aedf2eb779bfa4aad8f533c644ca94646977deae1c10221bff592f06785c76d0" and
  .request.diagnostic_request_payload_sha256 == "3fb48f788ccee7337e7fbc9924ced628c419afd31dfa281846af747b287d44c1" and
  (.rows | length) == 4 and
  ([.rows[] | .passed] | all) and
  ([.rows[] | .checks.cached_tokens_zero] | all) and
  ([.rows[] | .checks.selected_is_top1_all] | all) and
  .analysis.selected_is_top1_all == true
' "${run_dir}/exact-4k-logprob-repeat.json" >/dev/null

write_atomic "${run_dir}/client-gates-passed.txt" \
  'PASS exact-4K API-logprob diagnostic transport and greedy-decision integrity'
write_atomic "$stop_file" \
  'STOP after completed PLE-only exact-4K API-logprob diagnostic'
completed=1
trap - EXIT
