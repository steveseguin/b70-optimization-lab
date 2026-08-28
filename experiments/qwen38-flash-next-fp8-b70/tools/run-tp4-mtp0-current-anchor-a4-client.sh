#!/usr/bin/env bash
set -Eeuo pipefail

repo=/home/steve/llm-optimizations
supervisor="${repo}/experiments/qwen38-flash-next-fp8-b70/tools/supervise-tp4-mtp0-current-anchor-a4.sh"
state=/tmp/q38-mtp0-current-anchor-a4
stop_file="${state}.stop"
failure_file="${state}.failed"
run_dir=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-eager-mtp0-4352-r1-attempt4
base_url=http://127.0.0.1:19673
model=qwen38-flash-next-fp8-tp4
tokenizer=/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8
python=/home/steve/.venvs/vllm-xpu/bin/python
quality="${repo}/scripts/qwen38-text-quality-suite.py"
short_harness="${repo}/scripts/bench-openai-concurrency.py"
depth_harness="${repo}/scripts/bench-openai-token-depth-suite.py"
fixture="${repo}/data/qwen27-exact-depth/qwen38-flash-next-bcd9f01-exact-depth-v1.json"
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
    write_atomic "$failure_file" "FAIL current-runtime MTP0 anchor client rc=${rc}"
  fi
}
trap fail_sentinel EXIT

[[ $# == 0 ]] || { printf 'FAIL: client takes no arguments\n' >&2; exit 2; }
[[ -d "$run_dir" ]] || { printf 'FAIL: run directory is absent\n' >&2; exit 1; }
[[ "$(sha256sum "$quality" | cut -d' ' -f1)" == 8e18afee22a0fda4b44583ca55e3a43aef5f86fe8387a1bd28c533d1534bd3de ]] || exit 1
[[ "$(sha256sum "$short_harness" | cut -d' ' -f1)" == d590c63c87b1e664417b4198dbbb873cbe4f252509fa8f9fc50830efca2b4cf4 ]] || exit 1
[[ "$(sha256sum "$depth_harness" | cut -d' ' -f1)" == 8f162c1ab9fde7e0daffed2c4f0d6ff061ad6076c5de716e36f3d883ab4a1067 ]] || exit 1
[[ "$(sha256sum "$fixture" | cut -d' ' -f1)" == c44fccbaf600cc506d8ed0cc7357161057b86abc44469b611be71db97558061d ]] || exit 1
for artifact in recovery-canary.json quality-current.json quality-current.log quality-current.rc \
  bench-short-r1.json bench-short-r2.json bench-short-r3.json \
  exact-depth-4k-r1.json exact-depth-4k-r2.json current-anchor-summary.json \
  health-before-client.json models-before-client.json metrics-before-client.prom \
  journal-before-client.log client-gates-passed.txt \
  bench-short-r1.log bench-short-r1.rc bench-short-r2.log bench-short-r2.rc \
  bench-short-r3.log bench-short-r3.rc exact-depth-4k-r1.log exact-depth-4k-r1.rc \
  exact-depth-4k-r2.log exact-depth-4k-r2.rc; do
  [[ ! -e "${run_dir}/${artifact}" ]] || { printf 'FAIL: refusing to overwrite %s\n' "$artifact" >&2; exit 1; }
done

supervisor_pid=$(cat "${state}.pid" 2>/dev/null || true)
[[ "$supervisor_pid" =~ ^[1-9][0-9]*$ && -e "/proc/${supervisor_pid}" ]] || { printf 'FAIL: supervisor is absent\n' >&2; exit 1; }
supervisor_command=$(tr '\0' ' ' <"/proc/${supervisor_pid}/cmdline")
[[ "$supervisor_command" == *"supervise-tp4-mtp0-current-anchor-a4.sh"* ]] || {
  printf 'FAIL: supervisor identity mismatch\n' >&2
  exit 1
}
deadline_epoch=$(cat "${state}.deadline-epoch" 2>/dev/null || true)
[[ "$deadline_epoch" =~ ^[1-9][0-9]*$ ]] || { printf 'FAIL: supervisor deadline is absent\n' >&2; exit 1; }
(( deadline_epoch - $(date +%s) >= 4800 )) || { printf 'FAIL: less than 4800 seconds remain in lifecycle\n' >&2; exit 1; }
server_pid=$(cat "${run_dir}/server.pid" 2>/dev/null || true)
[[ "$server_pid" =~ ^[1-9][0-9]*$ && -e "/proc/${server_pid}" ]] || { printf 'FAIL: owned server is absent\n' >&2; exit 1; }
server_command=$(tr '\0' ' ' <"/proc/${server_pid}/cmdline")
[[ "$server_command" == *"vllm serve /mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8"* && \
   "$server_command" == *"--port 19673"* && "$server_command" == *"--max-model-len 4352"* ]] || {
  printf 'FAIL: server command identity mismatch\n' >&2
  exit 1
}
[[ "$server_command" != *"--speculative-config"* && "$server_command" != *"--reasoning-parser"* ]] || {
  printf 'FAIL: MTP or reasoning parser unexpectedly present\n' >&2
  exit 1
}
for receipt in \
  'vllm_head=1372c62d975c554f4b465c8299bc5f3295301ceb' \
  'kernels_head=ad25aa9f69a2171612b9c6b83dfa82c69559f9e4' \
  'runtime_stage_build_head=2f829747503c77d4814834dffd0840fb1dd9f75a' \
  'tp=4 ep=4 all2all=allgather_reducescatter' \
  'moe_backend=triton eager=1 mtp=0 max_model_len=4352 max_num_batched_tokens=64' \
  'kv_cache_memory_bytes=201326592' 'kv_cache_layout=BLHNC' \
  'reasoning_parser=absent' 'diagnostics=none'; do
  grep -Fxq "$receipt" "${run_dir}/identity.txt" || { printf 'FAIL: identity receipt missing: %s\n' "$receipt" >&2; exit 1; }
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
assert labels.get("kv_cache_memory_bytes") == "201326592", labels
assert labels.get("enable_prefix_caching") == "False", labels
assert int(labels.get("kv_cache_size_tokens", "0")) >= 4224, labels
PY
journal_start=$(cat "/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-eager-mtp0-4352-r1-attempt4-supervisor/journal-start-epoch.txt")
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
    headers={"Content-Type": "application/json", "X-Request-Id": "q38-current-anchor-recovery-canary"},
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
  --seed 20260609 --repeat-runs 16 --request-id-prefix q38-current-anchor-a4 \
  --long-context-tokens 4372 --chat-template-kwargs-json '{"enable_thinking":false}' \
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
  .long_context_case.pass == true and .long_context_case.usage.prompt_tokens == 4096 and
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
    --fixture "$fixture" --depth 4096 --context-capacity 4352 \
    --base-url "$base_url" --model "$model" --response-adapter vllm --timeout 900 \
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
depth = [json.loads((root / f"exact-depth-4k-r{i}.json").read_text()) for i in range(1, 3)]
for item in depth:
    assert item["status"] == "passed" and item["gate"]["passed"] is True
    assert item["request"]["prompt_token_ids_sha256"] == "aedf2eb779bfa4aad8f533c644ca94646977deae1c10221bff592f06785c76d0"
    assert item["request"]["request_payload_sha256"] == "2d92a2857d5cf45c3dcbc9d856cba714e2a46003295159fb5fcf1a8effb930be"
    usage = item["response"]["usage"]
    assert (usage["prompt_tokens"], usage["completion_tokens"], usage["total_tokens"]) == (4096, 128, 4224)
    assert usage["prompt_tokens_details"]["cached_tokens"] == 0
    assert item["response"]["finish_reasons"] == ["length"] and len(item["response"]["token_ids"]) == 128
depth_hashes = [item["response"]["output_token_ids_sha256"] for item in depth]
assert len(set(depth_hashes)) == 1
summary = {
    "schema_version": 1,
    "status": "passed",
    "identity": {
        "model_revision": "bcd9f01ddc9cff2316eb84281bebcd5b058bddce",
        "vllm_head": "1372c62d975c554f4b465c8299bc5f3295301ceb",
        "kernel_head": "ad25aa9f69a2171612b9c6b83dfa82c69559f9e4",
        "stage_build_head": "2f829747503c77d4814834dffd0840fb1dd9f75a",
        "tp": 4, "ep": 4, "mtp": 0, "graph": "off", "max_model_len": 4352,
    },
    "recovery_canary": "passed",
    "quality": {
        "semantic": quality_semantic,
        "repeat": "16/16 one hash",
        "long_context": "4096 prompt tokens, exact needle, cache zero",
    },
    "short": {
        "protocol": "row 1 follows one conditioning request in its invocation; rows 2-3 have no warmup; all three use the established identical p146/o256/c1 prompt",
        "rates_tok_s_after_ttft": [r["tok_s_out_after_ttft"] for r in short_records],
        "median_tok_s_after_ttft": statistics.median(r["tok_s_out_after_ttft"] for r in short_records),
        "output_sha256": short_records[0]["sha256"],
        "cache_finish_boundary": "The established harness does not retain cache-detail or finish-reason fields; do not claim those per-row receipts.",
    },
    "exact_4k": {
        "repeats": 2,
        "rates_tok_s_conventional_99_interval": [d["metric_window"]["conventional_99_interval_tok_s"] for d in depth],
        "median_tok_s_conventional_99_interval": statistics.median(d["metric_window"]["conventional_99_interval_tok_s"] for d in depth),
        "ttft_s": [d["metric_window"]["time_to_first_token_s"] for d in depth],
        "output_token_ids_sha256": depth_hashes[0],
        "same_boot_output_repeat": True,
        "cached_tokens": [0, 0],
    },
    "protected_results_changed": False,
    "interpretation": "Additive current-runtime TP4 eager MTP0 quality, short, and exact-4K screen; it does not replace or lower any prior row.",
}
for name in ["recovery-canary.json", "quality-current.json",
             "bench-short-r1.json", "bench-short-r2.json", "bench-short-r3.json",
             "exact-depth-4k-r1.json", "exact-depth-4k-r2.json"]:
    summary.setdefault("sha256", {})[name] = hashlib.sha256((root / name).read_bytes()).hexdigest()
destination = root / "current-anchor-summary.json"
temporary = destination.with_name(destination.name + f".tmp.{os.getpid()}")
temporary.write_text(json.dumps(summary, indent=2) + "\n")
os.replace(temporary, destination)
PY

write_atomic "${run_dir}/client-gates-passed.txt" 'PASS recovery quality short-repeat exact-4K-repeat current-runtime MTP0 anchor'
write_atomic "$stop_file" 'STOP after passed current-runtime MTP0 anchor'
completed=1
