#!/usr/bin/env bash
set -Eeuo pipefail

repo=/home/steve/llm-optimizations
lane="${repo}/experiments/qwen38-flash-next-fp8-b70"
run_dir=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-eager-mtp0-16512-sampler-native-r1-attempt6
base_url=http://127.0.0.1:19678
model=qwen38-flash-next-fp8-tp4
tokenizer=/mnt/usb-models/llm-models/Qwen3.8-Flash-Next-FP8
python=/home/steve/.venvs/vllm-xpu/bin/python
quality="${repo}/scripts/qwen38-text-quality-suite.py"
depth_harness="${repo}/scripts/bench-openai-token-depth-suite.py"
long_harness="${repo}/scripts/bench-openai-long-context-suite.py"
depth_fixture="${repo}/data/qwen27-exact-depth/qwen38-flash-next-bcd9f01-exact-depth-v1.json"
semantic_fixture="${lane}/fixtures/long-context-semantic-16k-v1.json"
a3_reference="${lane}/data/20260828-tp4-mtp0-16k-semantic-a3-same-server-corruption.json"

write_atomic() {
  local path=$1 value=$2 temporary
  temporary="${path}.tmp.$$"
  printf '%s\n' "$value" >"$temporary"
  mv "$temporary" "$path"
}

[[ $# == 0 ]] || { printf 'FAIL: client takes no arguments\n' >&2; exit 2; }
[[ -d "$run_dir" ]] || { printf 'FAIL: run directory is absent\n' >&2; exit 1; }
[[ "$(sha256sum "$quality" | cut -d' ' -f1)" == 8e18afee22a0fda4b44583ca55e3a43aef5f86fe8387a1bd28c533d1534bd3de ]]
[[ "$(sha256sum "$depth_harness" | cut -d' ' -f1)" == 8f162c1ab9fde7e0daffed2c4f0d6ff061ad6076c5de716e36f3d883ab4a1067 ]]
[[ "$(sha256sum "$long_harness" | cut -d' ' -f1)" == f3bbf3369152a55aa0c9acc8bbad7ff15db2d4d694f03cb5ed275efde7f99459 ]]
[[ "$(sha256sum "$depth_fixture" | cut -d' ' -f1)" == c44fccbaf600cc506d8ed0cc7357161057b86abc44469b611be71db97558061d ]]
[[ "$(sha256sum "$semantic_fixture" | cut -d' ' -f1)" == 61d94377bcb5a8252d4796d27ab0a16714c4c603bb20e8f5533641cb9e982e6a ]]
[[ "$(sha256sum "$a3_reference" | cut -d' ' -f1)" == 60898a11ab90238e11bc90b73038de5d00c2e72b1b185cc3851989371c429ef0 ]]
for artifact in quality-sampler-native.json quality-sampler-native.log \
  exact-depth-4k-r1.json exact-depth-4k-r2.json phase1-4k-summary.json \
  semantic-16k-r1.json semantic-16k-r2.json sampler-native-summary.json \
  client-gates-passed.txt; do
  [[ ! -e "${run_dir}/${artifact}" ]] || {
    printf 'FAIL: refusing to overwrite %s\n' "$artifact" >&2
    exit 1
  }
done

server_pid=$(cat "${run_dir}/server.pid" 2>/dev/null || true)
[[ "$server_pid" =~ ^[1-9][0-9]*$ && -e "/proc/${server_pid}" ]]
server_command=$(tr '\0' ' ' <"/proc/${server_pid}/cmdline")
[[ "$server_command" == *"vllm serve /mnt/usb-models/llm-models/Qwen3.8-Flash-Next-FP8"* && \
   "$server_command" == *"--port 19678"* && "$server_command" == *"--max-model-len 16512"* ]]
for receipt in \
  'vllm_head=1372c62d975c554f4b465c8299bc5f3295301ceb' \
  'kernels_head=ad25aa9f69a2171612b9c6b83dfa82c69559f9e4' \
  'runtime_stage_build_head=2f829747503c77d4814834dffd0840fb1dd9f75a' \
  'tp=4 ep=4 all2all=allgather_reducescatter' \
  'moe_backend=triton eager=1 mtp=0 max_model_len=16512 max_num_batched_tokens=64' \
  'kv_cache_memory_bytes=358465536' 'kv_cache_layout=BLHNC' \
  'xpu_sampler_kernel=0' 'reasoning_parser=absent' 'diagnostics=none'; do
  grep -Fxq "$receipt" "${run_dir}/identity.txt"
done
curl --connect-timeout 5 --max-time 20 -fsS "${base_url}/health" \
  >"${run_dir}/health-before-client.json"
curl --connect-timeout 5 --max-time 20 -fsS "${base_url}/v1/models" \
  >"${run_dir}/models-before-client.json"
jq -e --arg model "$model" '.data | any(.id == $model and .max_model_len == 16512)' \
  "${run_dir}/models-before-client.json" >/dev/null

set +e
timeout --signal=TERM --kill-after=10s 1500s "$python" "$quality" \
  --base-url "$base_url" --model "$model" --tokenizer "$tokenizer" --timeout 900 \
  --seed 20260609 --repeat-runs 16 --request-id-prefix q38-sampler-native-a6 \
  --long-context-tokens 4372 --chat-template-kwargs-json '{"enable_thinking":false}' \
  --output-json "${run_dir}/quality-sampler-native.json" \
  >"${run_dir}/quality-sampler-native.log" 2>&1
quality_rc=$?
set -e
write_atomic "${run_dir}/quality-sampler-native.rc" "$quality_rc"
[[ "$quality_rc" == 0 || "$quality_rc" == 1 ]]
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
  .long_context_case.usage.prompt_tokens_details.created_cache_tokens == 0
' "${run_dir}/quality-sampler-native.json" >/dev/null

for row in 1 2; do
  timeout --signal=TERM --kill-after=10s 910s "$python" "$depth_harness" --execute \
    --fixture "$depth_fixture" --depth 4096 --context-capacity 16512 \
    --base-url "$base_url" --model "$model" --response-adapter vllm --timeout 900 \
    --out "${run_dir}/exact-depth-4k-r${row}.json" \
    >"${run_dir}/exact-depth-4k-r${row}.log" 2>&1
done

"$python" - "$run_dir" <<'PY'
import json, os, pathlib, statistics, sys

root = pathlib.Path(sys.argv[1])
rows = [json.loads((root / f"exact-depth-4k-r{i}.json").read_text()) for i in (1, 2)]
for row in rows:
    assert row["status"] == "passed" and row["gate"]["passed"] is True
    usage = row["response"]["usage"]
    assert (usage["prompt_tokens"], usage["completion_tokens"], usage["total_tokens"]) == (4096, 128, 4224)
    assert usage["prompt_tokens_details"]["cached_tokens"] == 0
    assert row["response"]["finish_reasons"] == ["length"]
    assert len(row["response"]["token_ids"]) == 128
    assert row["response"]["output_token_ids_sha256"] == "1d833e5f463366223a669aa15495840d1337b173e675a9ea04f00a5ae339d5cc"
rates = [row["metric_window"]["conventional_99_interval_tok_s"] for row in rows]
median = statistics.median(rates)
assert median >= 4.519927197031117, median
summary = {
    "status": "passed",
    "treatment": {"VLLM_XPU_USE_SAMPLER_KERNEL": 0},
    "quality": "accepted 6/7 or 7/7; 16/16 repeat; exact cache-zero 4K needle",
    "exact_4k_rates_tok_s": rates,
    "exact_4k_median_tok_s": median,
    "protected_median_tok_s": 4.7578181021380175,
    "required_floor_tok_s": 4.519927197031117,
    "protected_results_changed": False,
}
destination = root / "phase1-4k-summary.json"
temporary = destination.with_name(destination.name + f".tmp.{os.getpid()}")
temporary.write_text(json.dumps(summary, indent=2) + "\n")
os.replace(temporary, destination)
PY

for row in 1 2; do
  timeout --signal=TERM --kill-after=10s 1810s "$python" "$long_harness" \
    --base-url "$base_url" --model "$model" --suite "$semantic_fixture" \
    --case-id q38-fn-16k-middle-v1 --max-tokens 128 --seed 1 \
    --timeout 1800 --return-token-ids \
    --request-extra-json '{"chat_template_kwargs":{"enable_thinking":false}}' \
    --out "${run_dir}/semantic-16k-r${row}.json" \
    >"${run_dir}/semantic-16k-r${row}.log" 2>&1
done

"$python" - "$run_dir" "$a3_reference" <<'PY'
import json, os, pathlib, sys

root = pathlib.Path(sys.argv[1])
reference = json.loads(pathlib.Path(sys.argv[2]).read_text())["request_1"]
rows = [json.loads((root / f"semantic-16k-r{i}.json").read_text())["rows"][0] for i in (1, 2)]
for row in rows:
    assert row["validation"]["pass"] is True
    assert row["prompt_tokens"] == reference["prompt_tokens"] == 16213
    assert row["cached_tokens"] == 0
    assert row["token_ids_complete"] is True
    assert row["sha256"] == reference["text_sha256"]
    assert row["token_ids_sha256"] == reference["token_ids_sha256"]
summary = {
    "status": "passed",
    "treatment": {"VLLM_XPU_USE_SAMPLER_KERNEL": 0},
    "semantic_16k_requests": 2,
    "semantic_16k_passes": 2,
    "cached_tokens": [row["cached_tokens"] for row in rows],
    "text_sha256": rows[0]["sha256"],
    "token_ids_sha256": rows[0]["token_ids_sha256"],
    "diagnostic_tok_s_after_ttft": [row["tok_s_after_ttft"] for row in rows],
    "ttft_s": [row["ttft_s"] for row in rows],
    "protected_results_changed": False,
    "next_gate": "clean bounded teardown, then broader deployment quality replay",
}
destination = root / "sampler-native-summary.json"
temporary = destination.with_name(destination.name + f".tmp.{os.getpid()}")
temporary.write_text(json.dumps(summary, indent=2) + "\n")
os.replace(temporary, destination)
PY

write_atomic "${run_dir}/client-gates-passed.txt" \
  'PASS sampler-native 4K quality performance and repeated semantic 16K gates'
