#!/usr/bin/env bash
set -Eeuo pipefail

repo=/home/steve/llm-optimizations
supervisor="${repo}/experiments/qwen38-flash-next-fp8-b70/tools/supervise-tp4-mtp1-4352-ple-only-a200-fullgraphdet-w13n32.sh"
state=/tmp/q38-mtp1-ple-only-a200
stop_file="${state}.stop"
failure_file="${state}.failed"
run_dir=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-fullgraphdet-mtp1-4352-ple-only-r1-attempt200
base_url=http://127.0.0.1:19871
model=qwen38-flash-next-fp8-tp4
tokenizer=/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8
python=/home/steve/.venvs/vllm-xpu/bin/python
quality="${repo}/scripts/qwen38-text-quality-suite.py"
short_harness="${repo}/scripts/bench-openai-concurrency.py"
depth_harness="${repo}/scripts/bench-openai-token-depth-suite.py"
fixture="${repo}/data/qwen27-exact-depth/qwen38-flash-next-bcd9f01-exact-depth-v1.json"
runtime_verifier=${repo}/experiments/qwen38-flash-next-fp8-b70/tools/verify-q38-a118-fullgraph-runtime.py
expected_runtime_verifier=6c5c3ca9a3b93d0e6da6f2e6f93d66172920384e709f812e98cb34103fe52bf1
torchinductor_cache=/tmp/qwen38-flash-next-fp8-tp4-ep4-fullgraphdet-mtp1-4352-ple-only-r1-attempt200-compile/torchinductor
torch_trace=${run_dir}/torch-trace
compilation_json='{"mode":0,"cudagraph_mode":"FULL_DECODE_ONLY","cudagraph_capture_sizes":[1,2],"max_cudagraph_capture_size":2,"compile_sizes":[],"cudagraph_num_of_warmups":1}'
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
    write_atomic "$failure_file" "FAIL PLE-only 2K MTP1 QSA-stable treatment client rc=${rc}"
  fi
}
trap fail_sentinel EXIT

[[ $# == 0 ]] || { printf 'FAIL: client takes no arguments\n' >&2; exit 2; }
[[ -d "$run_dir" ]] || { printf 'FAIL: run directory is absent\n' >&2; exit 1; }
[[ "$(sha256sum "$quality" | cut -d' ' -f1)" == 268f6de4a3e4353191d4f75c48b6b0f243ca30196fcb4c582e1db2e2935db656 ]] || exit 1
[[ "$(sha256sum "$short_harness" | cut -d' ' -f1)" == d590c63c87b1e664417b4198dbbb873cbe4f252509fa8f9fc50830efca2b4cf4 ]] || exit 1
[[ "$(sha256sum "$depth_harness" | cut -d' ' -f1)" == 8f162c1ab9fde7e0daffed2c4f0d6ff061ad6076c5de716e36f3d883ab4a1067 ]] || exit 1
[[ "$(sha256sum "$fixture" | cut -d' ' -f1)" == c44fccbaf600cc506d8ed0cc7357161057b86abc44469b611be71db97558061d ]] || exit 1
[[ "$(sha256sum "$runtime_verifier" | cut -d' ' -f1)" == "$expected_runtime_verifier" ]] || exit 1
for artifact in recovery-canary.json quality-current.json quality-current.log quality-current.rc \
  bench-short-r1.json bench-short-r2.json bench-short-r3.json \
  exact-depth-2k-r1.json exact-depth-2k-r2.json exact-depth-4k-r1.json exact-depth-4k-r2.json \
  ple-only-qsa-stable-summary.json \
  health-before-client.json models-before-client.json metrics-before-client.prom \
  fullgraphdet-runtime-before.json fullgraphdet-runtime-after.json \
  journal-before-client.log client-gates-passed.txt \
  bench-short-r1.log bench-short-r1.rc bench-short-r2.log bench-short-r2.rc \
  bench-short-r3.log bench-short-r3.rc exact-depth-2k-r1.log exact-depth-2k-r1.rc \
  exact-depth-2k-r2.log exact-depth-2k-r2.rc exact-depth-4k-r1.log exact-depth-4k-r1.rc \
  exact-depth-4k-r2.log exact-depth-4k-r2.rc; do
  [[ ! -e "${run_dir}/${artifact}" ]] || { printf 'FAIL: refusing to overwrite %s\n' "$artifact" >&2; exit 1; }
done

supervisor_pid=$(cat "${state}.pid" 2>/dev/null || true)
[[ "$supervisor_pid" =~ ^[1-9][0-9]*$ && -e "/proc/${supervisor_pid}" ]] || { printf 'FAIL: supervisor is absent\n' >&2; exit 1; }
supervisor_command=$(tr '\0' ' ' <"/proc/${supervisor_pid}/cmdline")
[[ "$supervisor_command" == *"supervise-tp4-mtp1-4352-ple-only-a200-fullgraphdet-w13n32.sh"* ]] || {
  printf 'FAIL: supervisor identity mismatch\n' >&2
  exit 1
}
deadline_epoch=$(cat "${state}.deadline-epoch" 2>/dev/null || true)
[[ "$deadline_epoch" =~ ^[1-9][0-9]*$ ]] || { printf 'FAIL: supervisor deadline is absent\n' >&2; exit 1; }
(( deadline_epoch - $(date +%s) >= 4800 )) || { printf 'FAIL: less than 4800 seconds remain in lifecycle\n' >&2; exit 1; }
server_pid=$(cat "${run_dir}/server.pid" 2>/dev/null || true)
[[ "$server_pid" =~ ^[1-9][0-9]*$ && -e "/proc/${server_pid}" ]] || { printf 'FAIL: owned server is absent\n' >&2; exit 1; }
server_command=$(tr '\0' ' ' <"/proc/${server_pid}/cmdline")
if grep -zFq 'VLLM_XPU_PLE_UVA_PREFETCH=' "/proc/${server_pid}/environ"; then
  printf 'FAIL: async UVA PLE selector unexpectedly present in server environment\n' >&2
  exit 1
fi
grep -zFxq 'VLLM_TUNED_CONFIG_FOLDER=/home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/configs/moe-m1-w13-n32' "/proc/${server_pid}/environ" || {
  printf 'FAIL: live server lacks the exact A200 tuned M1 map folder\n' >&2
  exit 1
}
[[ "$(grep -zc 'VLLM_TUNED_CONFIG_FOLDER=' "/proc/${server_pid}/environ" | tr -d '\n')" == 1 ]] || {
  printf 'FAIL: more than one tuned folder selector in server environment\n' >&2
  exit 1
}
[[ "$(sha256sum '/home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/configs/moe-m1-w13-n32/E=128,N=640,device_name=Intel(R)_Arc(TM)_Pro_B70_Graphics,dtype=fp8_w8a8,block_shape=[128,128].json' | cut -d' ' -f1)" == a8f1f8982e3e1af80ff31b9e0a00afaacf1af1b3c401585109b4d60d3c8267be ]] || {
  printf 'FAIL: A200 tuned M1 map drifted before client work\n' >&2
  exit 1
}
[[ "$(sha256sum "${repo}/experiments/qwen38-flash-next-fp8-b70/tools/verify-moe-m1-w13-n32-selection.py" | cut -d' ' -f1)" == 0bd36f13056d79924e7598bf8d844db3a5b8b35639737c0ef0b5af68cad14753 ]] || {
  printf 'FAIL: W13-N32 selection verifier drifted\n' >&2
  exit 1
}
# The official resolver needs the server's XPU runtime identity to resolve
# the platform and device name; mirror the frozen server exports exactly.
env PYTHONPATH=/mnt/usb-models/qwen38-build/runtime-core-moe-negidguard-b70:/home/steve/src/vllm-current-main \
  LD_LIBRARY_PATH=/mnt/usb-models/qwen38-build/runtime-core-moe-negidguard-b70/vllm_xpu_kernels:/home/steve/.venvs/vllm-xpu/lib:/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/lib:/opt/intel/oneapi/compiler/2025.3/lib:/opt/intel/oneapi/compiler/2025.3/opt/compiler/lib \
  ZE_AFFINITY_MASK=0 VLLM_TARGET_DEVICE=xpu \
  VLLM_TUNED_CONFIG_FOLDER=/home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/configs/moe-m1-w13-n32 \
  "$python" "${repo}/experiments/qwen38-flash-next-fp8-b70/tools/verify-moe-m1-w13-n32-selection.py" \
  --base-config-file '/home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/configs/moe-warps8-m1/E=128,N=640,device_name=Intel(R)_Arc(TM)_Pro_B70_Graphics,dtype=fp8_w8a8,block_shape=[128,128].json' \
  --candidate-config-file '/home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/configs/moe-m1-w13-n32/E=128,N=640,device_name=Intel(R)_Arc(TM)_Pro_B70_Graphics,dtype=fp8_w8a8,block_shape=[128,128].json' \
  --vllm-source /home/steve/src/vllm-current-main \
  --phase-config-patch /home/steve/llm-optimizations/patches/qwen38-flash-next-fp8-b70/vllm/0021-Add-opt-in-per-phase-Triton-MoE-configs.patch \
  --output "${run_dir}/moe-m1-w13-n32-selection-receipt.json" || {
  printf 'FAIL: official W13-N32 resolver receipt failed\n' >&2
  exit 1
}
jq -e '.status == "pass" and .selected_batch_key == 1 and
  .m1.w13.BLOCK_SIZE_N == 32 and .m1.w13.num_warps == 8 and
  .m1.w2.BLOCK_SIZE_N == 64 and .m1.w2.num_warps == 8 and
  .config.candidate_sha256 == "a8f1f8982e3e1af80ff31b9e0a00afaacf1af1b3c401585109b4d60d3c8267be" and
  .preservation.all_integer_m_2_through_512_match_retained_map == true' \
  "${run_dir}/moe-m1-w13-n32-selection-receipt.json" >/dev/null || {
  printf 'FAIL: W13-N32 resolver receipt did not prove key 1 W13-N32 / W2-N64\n' >&2
  exit 1
}
grep -zFxq 'CCL_SYCL_ALLREDUCE_LL=twoshots' "/proc/${server_pid}/environ" || {
  printf 'FAIL: live server lacks exact twoshots selector\n' >&2
  exit 1
}
grep -zFxq 'VLLM_XPU_GDN_SERIAL_SPEC_DECODE=1' "/proc/${server_pid}/environ" || {
  printf 'FAIL: live server lacks the serial GDN verifier-row selector
' >&2
  exit 1
}
grep -zFxq 'VLLM_XPU_ROWWISE_ALLREDUCE_MAX_ROWS=2' "/proc/${server_pid}/environ" || {
  printf 'FAIL: live server lacks the row-wise all-reduce selector
' >&2
  exit 1
}
grep -zFxq 'VLLM_XPU_ROWWISE_HC_NORM_MAX_ROWS=2' "/proc/${server_pid}/environ" || {
  printf 'FAIL: live server lacks the row-wise hyperconnection norm selector
' >&2
  exit 1
}
grep -zFxq 'PYTHONPATH=/mnt/usb-models/qwen38-build/runtime-core-moe-negidguard-b70:/home/steve/src/vllm-current-main' "/proc/${server_pid}/environ" || {
  printf 'FAIL: live server PYTHONPATH identity mismatch\n' >&2
  exit 1
}
if grep -zEq '^(Q38_REPEATABILITY_TRACE_FILE|VLLM_XPU_QWEN4_EXP_REPEATABILITY_TRACE_FILE|VLLM_XPU_QWEN4_EXP_REPEATABILITY_TRACE_RANK)=' "/proc/${server_pid}/environ"; then
  printf 'FAIL: trace selector unexpectedly present in live server environment\n' >&2
  exit 1
fi
[[ "$(git -C /home/steve/src/vllm-current-main rev-parse HEAD)" == 813fadd465c9247a7e70dc86951febd1f3f711b7 ]] || {
  printf 'FAIL: live vLLM checkout head changed\n' >&2
  exit 1
}
[[ -z "$(git -C /home/steve/src/vllm-current-main status --porcelain)" ]] || {
  printf 'FAIL: live vLLM checkout is dirty\n' >&2
  exit 1
}
[[ "$server_command" == *"vllm serve /mnt/usb-models/llm-models/Qwen3.8-Flash-Next-FP8"* && \
   "$server_command" == *"--port 19871"* && "$server_command" == *"--max-model-len 4352"* ]] || {
  printf 'FAIL: server command identity mismatch\n' >&2
  exit 1
}

[[ "$server_command" == *"--speculative-config"* && "$server_command" != *"--reasoning-parser"* ]] || {
  printf 'FAIL: MTP absent or reasoning parser present\n' >&2
  exit 1
}
[[ "$server_command" != *"--enforce-eager"* && "$server_command" == *"--cudagraph-metrics"* && \
   "$server_command" == *"--compilation-config ${compilation_json}"* ]] || {
  printf 'FAIL: frozen A200 graph command identity mismatch\n' >&2
  exit 1
}
for receipt in \
  'vllm_head=813fadd465c9247a7e70dc86951febd1f3f711b7' \
  'kernels_head=e421889999bc1e5a5f11044d14548b9afdba644d' \
  'runtime_stage_build_head=2f829747503c77d4814834dffd0840fb1dd9f75a' \
  'cpu_offload_gb=12.0' 'cpu_offload_params=ple_embedding.ngram_embedding.weight' \
  'tp=4 ep=4 all2all=allgather_reducescatter' \
  'moe_backend=triton eager=0 graph=FULL_DECODE_ONLY mtp=1 max_model_len=4352 max_num_batched_tokens=64' \
  'mtp_exact_recurrent=0' \
  'kv_cache_memory_bytes=376569856' 'kv_cache_layout=BLHNC' \
  'reasoning_parser=absent' 'diagnostics=full-decode-graph-public-oneccl-torch-trace' \
  'graph_enable_env=VLLM_XPU_ENABLE_XPU_GRAPH=1' \
  'compilation_config={"mode":0,"cudagraph_mode":"FULL_DECODE_ONLY","cudagraph_capture_sizes":[1,2],"max_cudagraph_capture_size":2,"compile_sizes":[],"cudagraph_num_of_warmups":1}' \
  'libccl_sha256=43d94d43506e30096dd099b9d53b54f932be964751e92ff0cbb8d3a37fad6700' 'ccl_kernel_sha256=0d549c35a558f1b216cb7d1efeaa9f86d7596ffc47b383644e075290d314f0c9' \
  'ccl_sycl_allreduce_ll=twoshots' \
  'tuned_config_folder=moe-m1-w13-n32' 'tuned_config_map_sha256=a8f1f8982e3e1af80ff31b9e0a00afaacf1af1b3c401585109b4d60d3c8267be' \
  'mkldnn_deterministic=1'; do
  grep -Fxq "$receipt" "${run_dir}/identity.txt" || { printf 'FAIL: identity receipt missing: %s\n' "$receipt" >&2; exit 1; }
done

curl --connect-timeout 5 --max-time 20 -fsS "${base_url}/health" >"${run_dir}/health-before-client.json"
curl --connect-timeout 5 --max-time 20 -fsS "${base_url}/v1/models" >"${run_dir}/models-before-client.json"
curl --connect-timeout 5 --max-time 20 -fsS "${base_url}/metrics" >"${run_dir}/metrics-before-client.prom"
"$python" "$runtime_verifier" \
  --server-pid "$server_pid" --server-log "${run_dir}/server.log" \
  --torchinductor-cache "$torchinductor_cache" --torch-trace "$torch_trace" --phase before \
  --output "${run_dir}/fullgraphdet-runtime-before.json"
jq -e --arg model "$model" '.data | any(.id == $model and .max_model_len == 4352)' \
  "${run_dir}/models-before-client.json" >/dev/null
"$python" - "${run_dir}/metrics-before-client.prom" <<'PY'
import pathlib, re, sys
line = next((line for line in pathlib.Path(sys.argv[1]).read_text().splitlines()
             if line.startswith("vllm:cache_config_info{")), None)
assert line is not None
labels = dict(re.findall(r'(\w+)="([^"]*)"', line))
assert labels.get("kv_cache_memory_bytes") == "376569856", labels
assert labels.get("enable_prefix_caching") == "False", labels
assert int(labels.get("kv_cache_size_tokens", "0")) >= 4224, labels
PY
journal_start=$(cat "/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-fullgraphdet-mtp1-4352-ple-only-r1-attempt200-supervisor/journal-start-epoch.txt")
journalctl -k --since "@${journal_start}" --no-pager >"${run_dir}/journal-before-client.log"
! grep -Eqi 'xe 0000:(23|27|43|47):00\.0.*(reset|fault|timeout|timed out|fatal|wedged|failed)' \
  "${run_dir}/journal-before-client.log" || { printf 'FAIL: B70 event before client work\n' >&2; exit 1; }

"$python" - "$base_url" "$model" "${run_dir}/recovery-canary.json" <<'PY'
import hashlib, json, pathlib, sys, urllib.request
base_url, model, output = sys.argv[1:]
payload = {
    "model": model,
    "messages": [{"role": "user", "content": "Reply with exactly: OK"}],
    "chat_template_kwargs": {"enable_thinking": False},
    "temperature": 0,
    "top_p": 1.0,
    "seed": 20260609,
    "max_tokens": 8,
    "stream": False,
}
request = urllib.request.Request(
    f"{base_url}/v1/chat/completions", data=json.dumps(payload).encode(),
    headers={"Content-Type": "application/json", "X-Request-Id": "q38-ple-only-a200-recovery-canary"},
    method="POST")
destination = pathlib.Path(output)
try:
    with urllib.request.urlopen(request, timeout=180) as response:
        assert response.status == 200
        result = json.load(response)
    content = result["choices"][0]["message"]["content"].strip()
    usage = result["usage"]
    details = usage["prompt_tokens_details"]
    assert result["model"] == model
    assert result["choices"][0]["finish_reason"] == "stop"
    assert content == "OK"
    assert hashlib.sha256(content.encode()).hexdigest() == "565339bc4d33d72817b583024112eb7f5cdf3e5eef0252d6ec1b9c9a94e12bb3"
    assert (usage["prompt_tokens"], usage["completion_tokens"], usage["total_tokens"]) == (17, 2, 19)
    assert details.get("cached_tokens") == 0 and details.get("created_cache_tokens") == 0
    receipt = {"status": "passed", "response": result}
except Exception as error:
    receipt = {"status": "failed", "error_type": type(error).__name__, "error": str(error)}
    destination.write_text(json.dumps(receipt, indent=2) + "\n")
    raise
destination.write_text(json.dumps(receipt, indent=2) + "\n")
PY


set +e
timeout --signal=TERM --kill-after=10s 1200s "$python" "$quality" \
  --base-url "$base_url" --model "$model" --tokenizer "$tokenizer" --timeout 900 \
  --seed 20260609 --repeat-runs 16 --request-id-prefix q38-ple-only-a200 \
  --long-context-tokens 2157 --chat-template-kwargs-json '{"enable_thinking":false}' \
  --output-json "${run_dir}/quality-current.json" >"${run_dir}/quality-current.log" 2>&1
quality_rc=$?
set -e
write_atomic "${run_dir}/quality-current.rc" "$quality_rc"
[[ "$quality_rc" == 0 || "$quality_rc" == 1 ]] || {
  printf 'FAIL: quality helper transport/runtime rc=%s\n' "$quality_rc" >&2
  exit 1
}
jq -e '
  .baseline_status == "not_run" and .baseline_match_all == null and
  (.exact_cases | length) == 7 and
  (([.exact_cases[] | select(.pass == true)] | length) == 7 or
   (([.exact_cases[] | select(.pass == true)] | length) == 6 and
    ([.exact_cases[] | select(.pass == false)] | length) == 1 and
    ([.exact_cases[] | select(.pass == false)][0] |
      .name == "code_execution" and .normalized == "30"))) and
  .repeat_case.pass == true and .repeat_case.repeats == 16 and
  .repeat_case.unique_hashes == ["3b0b3192cd70de9c19caf7a6f6f69a4dda63cc4e66049c2cf9c15633103896b7"] and
  .long_context_case.pass == true and .long_context_case.usage.prompt_tokens == 2048 and
  .long_context_case.usage.prompt_tokens_details.cached_tokens == 0 and
  .long_context_case.usage.prompt_tokens_details.created_cache_tokens == 0 and
  ([.exact_cases[].usage, .repeat_case.runs[].usage, .long_context_case.usage] |
    all(.total_tokens == (.prompt_tokens + .completion_tokens) and
        .prompt_tokens_details.cached_tokens == 0 and
        .prompt_tokens_details.created_cache_tokens == 0))
' "${run_dir}/quality-current.json" >/dev/null
quality_passed=$(jq '[.exact_cases[] | select(.pass == true)] | length' "${run_dir}/quality-current.json")
if [[ "$quality_passed" == 7 ]]; then
  [[ "$quality_rc" == 0 ]] || { printf 'FAIL: 7/7 quality did not return rc=0\n' >&2; exit 1; }
else
  [[ "$quality_passed" == 6 && "$quality_rc" == 1 ]] || { printf 'FAIL: quality rc/semantic mismatch\n' >&2; exit 1; }
fi

for row in 1 2 3; do
  warmups=0
  [[ "$row" == 1 ]] && warmups=1
  set +e
  timeout 360s "$python" "$short_harness" --base-url "$base_url" --tokenizer "$tokenizer" \
    --prompt-tokens 128 --output-tokens 256 \
    --concurrency 1 --warmups "$warmups" --timeout 300 --seed 20260828 \
    --output-json "${run_dir}/bench-short-r${row}.json" \
    >"${run_dir}/bench-short-r${row}.log" 2>&1
  rc=$?
  set -e
  write_atomic "${run_dir}/bench-short-r${row}.rc" "$rc"
  (( rc == 0 )) || exit "$rc"
done

for row in 1 2; do
  set +e
  timeout --signal=TERM --kill-after=10s 910s "$python" "$depth_harness" --execute \
    --fixture "$fixture" --depth 2048 --context-capacity 4352 \
    --base-url "$base_url" --model "$model" --response-adapter vllm --timeout 900 \
    --out "${run_dir}/exact-depth-2k-r${row}.json" \
    >"${run_dir}/exact-depth-2k-r${row}.log" 2>&1
  rc=$?
  set -e
  write_atomic "${run_dir}/exact-depth-2k-r${row}.rc" "$rc"
  (( rc == 0 )) || exit "$rc"
done

for row in 1 2; do
  set +e
  timeout --signal=TERM --kill-after=10s 1500s "$python" "$depth_harness" --execute \
    --fixture "$fixture" --depth 4096 --context-capacity 4352 \
    --base-url "$base_url" --model "$model" --response-adapter vllm --timeout 1400 \
    --out "${run_dir}/exact-depth-4k-r${row}.json" \
    >"${run_dir}/exact-depth-4k-r${row}.log" 2>&1
  rc=$?
  set -e
  write_atomic "${run_dir}/exact-depth-4k-r${row}.rc" "$rc"
  (( rc == 0 )) || exit "$rc"
done

"$python" - "$run_dir" <<'PY'
import hashlib, json, os, pathlib, statistics, sys
root = pathlib.Path(sys.argv[1])
quality = json.loads((root / "quality-current.json").read_text())
quality_passed = sum(case["pass"] is True for case in quality["exact_cases"])
quality_semantic = f"{quality_passed}/7"
if quality_passed == 6:
    quality_semantic += "; sole known miss code_execution=30"
short = [json.loads((root / f"bench-short-r{i}.json").read_text()) for i in range(1, 4)]
short_records = [item["scenarios"]["c1"]["records"][0] for item in short]
for record in short_records:
    assert (record["prompt_tokens"], record["completion_tokens"], record["total_tokens"]) == (146, 256, 402)
    assert record["sha256"] == "5f40744644b98ddd58a0c202fe855af324c0b1c33e1a6275afd74c12488f89f0"
depth = [json.loads((root / f"exact-depth-2k-r{i}.json").read_text()) for i in range(1, 3)]
for item in depth:
    assert item["status"] == "passed" and item["gate"]["passed"] is True
    assert item["request"]["prompt_token_ids_sha256"] == "a173e60e5047c0f080e0ea45680eecbb533d30946cfc2ae0e028c684bf18d1ba"
    assert item["request"]["request_payload_sha256"] == "3aa1bba4d0ade3c07e7cad10bb5ee01245dc194d28dc17359311ece3b4ab6f36"
    usage = item["response"]["usage"]
    assert (usage["prompt_tokens"], usage["completion_tokens"], usage["total_tokens"]) == (2048, 128, 2176)
    assert usage["prompt_tokens_details"]["cached_tokens"] == 0
    assert item["response"]["finish_reasons"] == ["length"] and len(item["response"]["token_ids"]) == 128
depth_hashes = [item["response"]["output_token_ids_sha256"] for item in depth]
assert len(set(depth_hashes)) == 1
assert depth_hashes == ['afffd2110812762164862b6388f054bb56696ee57b07eadce411a702c40bc714'] * 2
depth4k = [json.loads((root / f"exact-depth-4k-r{i}.json").read_text()) for i in range(1, 3)]
for item in depth4k:
    assert item["status"] == "passed" and item["gate"]["passed"] is True
    assert item["request"]["prompt_token_ids_sha256"] == "aedf2eb779bfa4aad8f533c644ca94646977deae1c10221bff592f06785c76d0"
    assert item["request"]["request_payload_sha256"] == "2d92a2857d5cf45c3dcbc9d856cba714e2a36003295159fb5fcf1a8effb930be"
    usage = item["response"]["usage"]
    assert (usage["prompt_tokens"], usage["completion_tokens"], usage["total_tokens"]) == (4096, 128, 4224)
    assert usage["prompt_tokens_details"]["cached_tokens"] == 0
    assert item["response"]["finish_reasons"] == ["length"] and len(item["response"]["token_ids"]) == 128
depth4k_hashes = [item["response"]["output_token_ids_sha256"] for item in depth4k]
assert len(set(depth4k_hashes)) == 1
assert depth4k_hashes == ['c6193cc6c9a1553f56d7ce78faea9c8bfa628a67fcea229b1c99279a149f6639'] * 2
summary = {
    "schema_version": 1,
    "status": "passed",
    "identity": {
        "model_revision": "bcd9f01ddc9cff2316eb84281bebcd5b058bddce",
        "vllm_head": "813fadd465c9247a7e70dc86951febd1f3f711b7",
        "kernel_head": "e421889999bc1e5a5f11044d14548b9afdba644d",
        "stage_build_head": "2f829747503c77d4814834dffd0840fb1dd9f75a",
        "tp": 4, "ep": 4, "mtp": 1, "graph": "FULL_DECODE_ONLY",
        "compilation_mode": "NONE", "cudagraph_capture_sizes": [1, 2],
        "exact_verify_selectors": ["VLLM_XPU_GDN_SERIAL_SPEC_DECODE=1", "VLLM_XPU_ROWWISE_ALLREDUCE_MAX_ROWS=2", "VLLM_XPU_ROWWISE_HC_NORM_MAX_ROWS=2"],
        "max_model_len": 4352,
        "placement": "ple_only_uva", "ple_host_bytes_per_rank": 12800061440,
        "async_uva_ple_prefetch": False,
        "libccl_sha256": "43d94d43506e30096dd099b9d53b54f932be964751e92ff0cbb8d3a37fad6700",
        "ccl_kernel_sha256": "0d549c35a558f1b216cb7d1efeaa9f86d7596ffc47b383644e075290d314f0c9",
        "ccl_sycl_allreduce_ll": "twoshots",
        "tuned_config_folder": "moe-m1-w13-n32",
        "tuned_config_map_sha256": "a8f1f8982e3e1af80ff31b9e0a00afaacf1af1b3c401585109b4d60d3c8267be",
        "diagnostics": "full-decode-graph-public-oneccl-torch-trace",
        "torch_trace_policy": "dynamo-exact-target-allowlist-v1",
        "input_embedding": "device", "kv_cache_memory_bytes": 376569856,
    },
    "recovery_canary": "passed",
    "quality": {
        "semantic": quality_semantic,
        "repeat": "16/16 one hash",
        "long_context": "2048 prompt tokens, exact needle, cache zero",
    },
    "short": {
        "protocol": "row 1 follows one conditioning request in its invocation; rows 2-3 have no warmup; all three use the established identical p146/o256/c1 prompt",
        "rates_tok_s_after_ttft": [r["tok_s_out_after_ttft"] for r in short_records],
        "median_tok_s_after_ttft": statistics.median(r["tok_s_out_after_ttft"] for r in short_records),
        "output_sha256": short_records[0]["sha256"],
        "cache_finish_boundary": "The established harness does not retain cache-detail or finish-reason fields; do not claim those per-row receipts.",
    },
    "exact_2k": {
        "repeats": 2,
        "rates_tok_s_conventional_99_interval": [d["metric_window"]["conventional_99_interval_tok_s"] for d in depth],
        "median_tok_s_conventional_99_interval": statistics.median(d["metric_window"]["conventional_99_interval_tok_s"] for d in depth),
        "ttft_s": [d["metric_window"]["time_to_first_token_s"] for d in depth],
        "output_token_ids_sha256": depth_hashes[0],
        "same_boot_output_repeat": True,
        "cached_tokens": [0, 0],
    },
    "exact_4k": {
        "repeats": 2,
        "protocol": "p4096/o128; conventional 99 inter-token intervals; served capacity 4352",
        "rates_tok_s_conventional_99_interval": [d["metric_window"]["conventional_99_interval_tok_s"] for d in depth4k],
        "median_tok_s_conventional_99_interval": statistics.median(d["metric_window"]["conventional_99_interval_tok_s"] for d in depth4k),
        "ttft_s": [d["metric_window"]["time_to_first_token_s"] for d in depth4k],
        "output_token_ids_sha256": depth4k_hashes[0],
        "same_boot_output_repeat": True,
        "cached_tokens": [0, 0],
    },
    "protected_results_changed": False,
    "interpretation": "Additive PLE-only TP4 compilation-free FULL_DECODE_ONLY deterministic-line quality, short, exact-2K and exact-4K screen at 4352 served tokens; both depth hashes are the deterministic line's own two-server authorities; it does not replace or lower any prior row or native-line record.",
}
for name in ["recovery-canary.json", "quality-current.json",
             "bench-short-r1.json", "bench-short-r2.json", "bench-short-r3.json",
             "exact-depth-2k-r1.json", "exact-depth-2k-r2.json",
             "exact-depth-4k-r1.json", "exact-depth-4k-r2.json"]:
    summary.setdefault("sha256", {})[name] = hashlib.sha256((root / name).read_bytes()).hexdigest()
destination = root / "ple-only-qsa-stable-summary.json"
temporary = destination.with_name(destination.name + f".tmp.{os.getpid()}")
temporary.write_text(json.dumps(summary, indent=2) + "\n")
os.replace(temporary, destination)
PY

"$python" "$runtime_verifier" \
  --server-pid "$server_pid" --server-log "${run_dir}/server.log" \
  --torchinductor-cache "$torchinductor_cache" --torch-trace "$torch_trace" --phase after \
  --output "${run_dir}/fullgraphdet-runtime-after.json"
jq -e '.status == "passed" and .phase == "after" and
  .size_2_full_dispatch_count > 0 and .size_1_full_dispatch_count >= 0 and (.collective_processes | length) >= 4 and
  .libccl.sha256 == "43d94d43506e30096dd099b9d53b54f932be964751e92ff0cbb8d3a37fad6700" and
  .ccl_kernel.sha256 == "0d549c35a558f1b216cb7d1efeaa9f86d7596ffc47b383644e075290d314f0c9" and
  .ccl_sycl_allreduce_ll == "twoshots" and
  .schema_version == 3 and .compilation_mode == "NONE" and
  .inductor_disabled_receipts > 0 and
  .torchinductor_cache.interpretation == "trace_attributed_nested_operator_cache" and
  .torchinductor_cache.file_count > 0 and
  .torch_trace.compile_event_count > 0' "${run_dir}/fullgraphdet-runtime-after.json" >/dev/null

write_atomic "${run_dir}/client-gates-passed.txt" 'PASS recovery quality short-repeat exact-2K-repeat exact-4K-repeat PLE-only 4352 MTP1 QSA-stable treatment'
write_atomic "$stop_file" 'STOP after passed PLE-only 2K MTP1 QSA-stable treatment'
completed=1
