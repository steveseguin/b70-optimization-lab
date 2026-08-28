#!/usr/bin/env bash
set -Eeuo pipefail

repo=/home/steve/llm-optimizations
state=/tmp/q38-mtp0-current-vision-a9
stop_file="${state}.stop"
failure_file="${state}.failed"
run_dir=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-eager-mtp0-vision-512-r1-attempt9
evidence_dir=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-eager-mtp0-vision-512-r1-attempt9-supervisor
base_url=http://127.0.0.1:19688
model=qwen38-flash-next-fp8-tp4-vision
tokenizer=/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8
python=/home/steve/.venvs/vllm-xpu/bin/python
quality="${repo}/scripts/qwen38-text-quality-suite.py"
vision_client="${repo}/experiments/qwen38-flash-next-fp8-b70/tools/run-fixed-vision-fixture-v1.py"
vision_manifest="${repo}/experiments/qwen38-flash-next-fp8-b70/fixtures/fixed-vision-fixture-v1.json"
vision_output="${run_dir}/fixed-vision-v1"
completed=0

write_atomic() {
  local path=$1 value=$2 tmp="${1}.tmp.$$"
  printf '%s\n' "$value" >"$tmp"
  mv "$tmp" "$path"
}

fail_sentinel() {
  local rc=$?
  if (( completed == 0 )); then
    write_atomic "$failure_file" "FAIL vision attempt-9 client rc=${rc}"
  fi
}
trap fail_sentinel EXIT

[[ $# == 0 ]] || { printf 'FAIL: vision client takes no arguments\n' >&2; exit 2; }
[[ -d "$run_dir" && -d "$evidence_dir" ]] || {
  printf 'FAIL: vision run or supervisor evidence directory is absent\n' >&2
  exit 1
}
[[ "$(sha256sum "$quality" | cut -d' ' -f1)" == 8e18afee22a0fda4b44583ca55e3a43aef5f86fe8387a1bd28c533d1534bd3de ]] || {
  printf 'FAIL: text quality helper hash changed\n' >&2
  exit 1
}
[[ "$(sha256sum "$vision_client" | cut -d' ' -f1)" == f84e7f02d98c611095b2bae9582fc1056c3e042969733d1ef4290910cd40e0a1 ]] || {
  printf 'FAIL: fixed vision client hash changed\n' >&2
  exit 1
}
[[ "$(sha256sum "$vision_manifest" | cut -d' ' -f1)" == 395158995f300e53d4360b844bcbb8dffb2dd551eb0106f4d91200b9c7402226 ]] || {
  printf 'FAIL: fixed vision manifest hash changed\n' >&2
  exit 1
}
for artifact in health-before-client.json models-before-client.json \
  metrics-before-client.prom journal-before-client.log text-recovery.json \
  text-semantic-7.json text-semantic-7.log text-semantic-7.rc \
  fixed-vision-static-validation.json health-after-vision.json \
  metrics-after-vision.prom journal-after-vision.log vision-attempt9-summary.json \
  client-gates-passed.txt; do
  [[ ! -e "${run_dir}/${artifact}" ]] || {
    printf 'FAIL: refusing to overwrite %s\n' "$artifact" >&2
    exit 1
  }
done
[[ ! -e "$vision_output" ]] || {
  printf 'FAIL: refusing to reuse %s\n' "$vision_output" >&2
  exit 1
}

supervisor_pid=$(cat "${state}.pid" 2>/dev/null || true)
[[ "$supervisor_pid" =~ ^[1-9][0-9]*$ && -e "/proc/${supervisor_pid}" ]] || {
  printf 'FAIL: exact vision supervisor is absent\n' >&2
  exit 1
}
supervisor_command=$(tr '\0' ' ' <"/proc/${supervisor_pid}/cmdline")
[[ "$supervisor_command" == *"supervise-tp4-mtp0-current-vision-a9.sh"* ]] || {
  printf 'FAIL: supervisor identity mismatch\n' >&2
  exit 1
}
deadline_epoch=$(cat "${state}.deadline-epoch" 2>/dev/null || true)
[[ "$deadline_epoch" =~ ^[1-9][0-9]*$ ]] || {
  printf 'FAIL: supervisor deadline is absent\n' >&2
  exit 1
}
(( deadline_epoch - $(date +%s) >= 10500 )) || {
  printf 'FAIL: less than 10500 seconds remain in lifecycle\n' >&2
  exit 1
}
server_pid=$(cat "${run_dir}/server.pid" 2>/dev/null || true)
[[ "$server_pid" =~ ^[1-9][0-9]*$ && -e "/proc/${server_pid}" ]] || {
  printf 'FAIL: exact vision server is absent\n' >&2
  exit 1
}
server_command=$(tr '\0' ' ' <"/proc/${server_pid}/cmdline")
[[ "$server_command" == *"vllm serve /mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8"* && \
   "$server_command" == *"--port 19688"* && \
   "$server_command" == *"--max-model-len 512"* && \
   "$server_command" == *"--limit-mm-per-prompt"* && \
   "$server_command" == *"--mm-processor-cache-gb 0"* && \
   "$server_command" == *"--mm-encoder-tp-mode weights"* ]] || {
  printf 'FAIL: server command does not own the frozen vision identity\n' >&2
  exit 1
}
[[ "$server_command" != *"--language-model-only"* && \
   "$server_command" != *"--speculative-config"* && \
   "$server_command" != *"--reasoning-parser"* ]] || {
  printf 'FAIL: text-only, MTP, or reasoning mode unexpectedly present\n' >&2
  exit 1
}
for receipt in \
  'vllm_head=1372c62d975c554f4b465c8299bc5f3295301ceb' \
  'kernels_head=ad25aa9f69a2171612b9c6b83dfa82c69559f9e4' \
  'runtime_stage_build_head=2f829747503c77d4814834dffd0840fb1dd9f75a' \
  'tp=4 ep=4 all2all=allgather_reducescatter' \
  'moe_backend=triton eager=1 mtp=0 max_model_len=512 max_num_batched_tokens=64' \
  'language_model_only=false modality=vision' \
  'limit_mm_per_prompt=image:1,video:0 mm_processor_cache_gb=0 mm_encoder_tp_mode=weights' \
  'kv_cache_memory_bytes=201326592' 'kv_cache_layout=BLHNC' \
  'reasoning_parser=absent' 'diagnostics=none'; do
  grep -Fxq "$receipt" "${run_dir}/identity.txt" || {
    printf 'FAIL: identity receipt missing: %s\n' "$receipt" >&2
    exit 1
  }
done

curl --connect-timeout 5 --max-time 20 -fsS "${base_url}/health" \
  >"${run_dir}/health-before-client.json"
curl --connect-timeout 5 --max-time 20 -fsS "${base_url}/v1/models" \
  >"${run_dir}/models-before-client.json"
curl --connect-timeout 5 --max-time 20 -fsS "${base_url}/metrics" \
  >"${run_dir}/metrics-before-client.prom"
jq -e --arg model "$model" '.data | any(.id == $model and .max_model_len == 512)' \
  "${run_dir}/models-before-client.json" >/dev/null
journal_start=$(cat "${evidence_dir}/journal-start-epoch.txt")
journalctl -k --since "@${journal_start}" --no-pager \
  >"${run_dir}/journal-before-client.log"
! grep -Eqi 'xe 0000:(23|27|43|47):00\.0.*(reset|fault|timeout|timed out|fatal|wedged|failed)' \
  "${run_dir}/journal-before-client.log" || {
  printf 'FAIL: B70 event before client work\n' >&2
  exit 1
}

"$python" - "$base_url" "$model" "${run_dir}/text-recovery.json" <<'PY'
import hashlib, json, pathlib, sys, urllib.request
base_url, model, output = sys.argv[1:]
payload = {
    "model": model,
    "messages": [{"role": "user", "content": "Reply with exactly: OK"}],
    "chat_template_kwargs": {"enable_thinking": False},
    "temperature": 0, "top_p": 1.0, "seed": 20260609,
    "max_tokens": 8, "stream": False,
}
request = urllib.request.Request(
    f"{base_url}/v1/chat/completions", data=json.dumps(payload).encode(),
    headers={"Content-Type": "application/json", "X-Request-Id": "q38-vision-a9-text-recovery"},
    method="POST")
with urllib.request.urlopen(request, timeout=300) as response:
    assert response.status == 200
    result = json.load(response)
choice = result["choices"][0]
content = choice["message"]["content"].strip()
usage = result["usage"]
details = usage["prompt_tokens_details"]
assert result["model"] == model
assert choice["finish_reason"] == "stop"
assert content == "OK"
assert hashlib.sha256(content.encode()).hexdigest() == "565339bc4d33d72817b583024112eb7f5cdf3e5eef0252d6ec1b9c9a94e12bb3"
assert (usage["prompt_tokens"], usage["completion_tokens"], usage["total_tokens"]) == (17, 2, 19)
assert details.get("cached_tokens") == 0 and details.get("created_cache_tokens") == 0
pathlib.Path(output).write_text(json.dumps({
    "status": "passed", "response": result, "speed_credit": False,
}, indent=2) + "\n")
PY

set +e
timeout --signal=TERM --kill-after=10s 1500s "$python" - \
  "$quality" "$base_url" "$model" "${run_dir}/text-semantic-7.json" \
  >"${run_dir}/text-semantic-7.log" 2>&1 <<'PY'
import importlib.util, json, pathlib, sys
source, base_url, model, output = sys.argv[1:]
spec = importlib.util.spec_from_file_location("q38_text_quality", source)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
cases = module.run_exact_cases(
    base_url, model, 900, 20260609, {"enable_thinking": False}, 0.0,
    "q38-vision-a9-semantic",
)
for case in cases:
    usage = case.get("usage") or {}
    details = usage.get("prompt_tokens_details") or {}
    assert usage.get("total_tokens") == usage.get("prompt_tokens") + usage.get("completion_tokens")
    assert details.get("cached_tokens") == 0
    assert details.get("created_cache_tokens") == 0
passed = sum(case["pass"] is True for case in cases)
known_miss = [case for case in cases if case["pass"] is False]
accepted = passed == 7 or (
    passed == 6 and len(known_miss) == 1 and
    known_miss[0]["name"] == "code_execution" and
    known_miss[0]["normalized"] == "30"
)
receipt = {
    "status": "passed" if accepted else "failed",
    "semantic": f"{passed}/7",
    "exact_cases": cases,
    "allowed_known_miss": "code_execution=30 only",
    "speed_credit": False,
}
pathlib.Path(output).write_text(json.dumps(receipt, indent=2) + "\n")
raise SystemExit(0 if accepted else 1)
PY
semantic_rc=$?
set -e
write_atomic "${run_dir}/text-semantic-7.rc" "$semantic_rc"
(( semantic_rc == 0 )) || {
  printf 'FAIL: seven-case text semantic gate failed\n' >&2
  exit 1
}

"$python" "$vision_client" --validate-only \
  --manifest "$vision_manifest" \
  >"${run_dir}/fixed-vision-static-validation.json"
timeout --signal=TERM --kill-after=10s 8400s "$python" "$vision_client" \
  --manifest "$vision_manifest" --base-url "$base_url" --model "$model" \
  --timeout 900 --output-dir "$vision_output"
jq -e '.status == "passed" and .expected_result_count == 9 and
  .observed_result_count == 9 and (.results | length) == 9 and
  ([.results[].passed] | all(. == true)) and
  ([.repeat_groups[].passed] | all(. == true))' \
  "${vision_output}/result.json" >/dev/null

curl --connect-timeout 5 --max-time 20 -fsS "${base_url}/health" \
  >"${run_dir}/health-after-vision.json"
curl --connect-timeout 5 --max-time 20 -fsS "${base_url}/metrics" \
  >"${run_dir}/metrics-after-vision.prom"
journalctl -k --since "@${journal_start}" --no-pager \
  >"${run_dir}/journal-after-vision.log"
! grep -Eqi 'xe 0000:(23|27|43|47):00\.0.*(reset|fault|timeout|timed out|fatal|wedged|failed)' \
  "${run_dir}/journal-after-vision.log" || {
  printf 'FAIL: B70 event during client work\n' >&2
  exit 1
}

"$python" - "$run_dir" <<'PY'
import hashlib, json, os, pathlib, sys
root = pathlib.Path(sys.argv[1])
semantic = json.loads((root / "text-semantic-7.json").read_text())
vision = json.loads((root / "fixed-vision-v1/result.json").read_text())
summary = {
    "schema": "neural.download.flash-next-vision-screen.v1",
    "status": "passed",
    "identity": {
        "model_revision": "bcd9f01ddc9cff2316eb84281bebcd5b058bddce",
        "vllm_head": "1372c62d975c554f4b465c8299bc5f3295301ceb",
        "kernel_head": "ad25aa9f69a2171612b9c6b83dfa82c69559f9e4",
        "stage_build_head": "2f829747503c77d4814834dffd0840fb1dd9f75a",
        "tp": 4, "ep": 4, "mtp": 0, "graph": "off",
        "max_model_len": 512, "max_num_batched_tokens": 64,
        "language_model_only": False,
        "limit_mm_per_prompt": {"image": 1, "video": 0},
        "mm_processor_cache_gb": 0, "mm_encoder_tp_mode": "weights",
        "kv_cache_memory_bytes": 201326592,
    },
    "same_boot_order": ["text_recovery", "seven_text_semantic_cases", "nine_fixed_vision_requests"],
    "text_recovery": "passed",
    "text_semantic": semantic["semantic"],
    "vision": {
        "fixture_id": vision["manifest"]["fixture"]["fixture_id"],
        "observed": vision["observed_result_count"], "expected": 9,
        "all_passed": all(item["passed"] for item in vision["results"]),
    },
    "health_after_final_request": "passed",
    "speed_claim": False,
    "speed_credit": False,
    "deployment_credit": False,
    "protected_results_changed": False,
    "maximum_interpretation_before_clean_teardown": "bounded capability and quality candidate only",
    "sha256": {},
}
for relative in ["text-recovery.json", "text-semantic-7.json", "fixed-vision-v1/result.json"]:
    summary["sha256"][relative] = hashlib.sha256((root / relative).read_bytes()).hexdigest()
destination = root / "vision-attempt9-summary.json"
temporary = destination.with_name(destination.name + f".tmp.{os.getpid()}")
temporary.write_text(json.dumps(summary, indent=2) + "\n")
os.replace(temporary, destination)
PY

write_atomic "${run_dir}/client-gates-passed.txt" \
  'PASS same-boot text recovery seven semantics nine fixed-vision requests health no-speed'
write_atomic "$stop_file" 'STOP after passed bounded vision attempt-9 client'
completed=1
