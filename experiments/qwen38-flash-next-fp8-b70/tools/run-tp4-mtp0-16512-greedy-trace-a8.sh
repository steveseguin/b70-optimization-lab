#!/usr/bin/env bash
set -Eeuo pipefail

repo=/home/steve/llm-optimizations
run_dir=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-eager-mtp0-16512-greedy-trace-r1-attempt8
base_url=http://127.0.0.1:19680
model=qwen38-flash-next-fp8-tp4
python=/home/steve/.venvs/vllm-xpu/bin/python
depth_harness="${repo}/scripts/bench-openai-token-depth-suite.py"
depth_fixture="${repo}/data/qwen27-exact-depth/qwen38-flash-next-bcd9f01-exact-depth-v1.json"
trace_file="${run_dir}/greedy-trace/greedy-decisions-rank0.jsonl"

write_atomic() {
  local path=$1 value=$2 temporary
  temporary="${path}.tmp.$$"
  printf '%s\n' "$value" >"$temporary"
  mv "$temporary" "$path"
}

[[ $# == 0 ]] || { printf 'FAIL: client takes no arguments\n' >&2; exit 2; }
[[ -d "$run_dir" ]] || { printf 'FAIL: run directory is absent\n' >&2; exit 1; }
[[ "$(sha256sum "$depth_harness" | cut -d' ' -f1)" == 8f162c1ab9fde7e0daffed2c4f0d6ff061ad6076c5de716e36f3d883ab4a1067 ]]
[[ "$(sha256sum "$depth_fixture" | cut -d' ' -f1)" == c44fccbaf600cc506d8ed0cc7357161057b86abc44469b611be71db97558061d ]]
for artifact in exact-depth-4k-trace-r1.json exact-depth-4k-trace-r2.json \
  greedy-trace-analysis.json greedy-trace-client-gates-passed.txt; do
  [[ ! -e "${run_dir}/${artifact}" ]] || {
    printf 'FAIL: refusing to overwrite %s\n' "$artifact" >&2
    exit 1
  }
done
[[ ! -e "$trace_file" ]] || { printf 'FAIL: trace already has records\n' >&2; exit 1; }

server_pid=$(cat "${run_dir}/server.pid" 2>/dev/null || true)
[[ "$server_pid" =~ ^[1-9][0-9]*$ && -e "/proc/${server_pid}" ]]
server_command=$(tr '\0' ' ' <"/proc/${server_pid}/cmdline")
[[ "$server_command" == *"vllm serve /mnt/usb-models/llm-models/Qwen3.8-Flash-Next-FP8"* && \
   "$server_command" == *"--port 19680"* && "$server_command" == *"--max-model-len 16512"* ]]
for receipt in \
  'vllm_head=5d5081b2b1e145067bce6ec99492eac7ce042e23' \
  'kernels_head=ad25aa9f69a2171612b9c6b83dfa82c69559f9e4' \
  'runtime_stage_build_head=2f829747503c77d4814834dffd0840fb1dd9f75a' \
  'tp=4 ep=4 all2all=allgather_reducescatter' \
  'moe_backend=triton eager=1 mtp=0 max_model_len=16512 max_num_batched_tokens=64' \
  'kv_cache_memory_bytes=358465536' 'kv_cache_layout=BLHNC' \
  'xpu_sampler_kernel=1' 'reasoning_parser=absent' \
  'diagnostics=greedy-decision-trace-top8-max256'; do
  grep -Fxq "$receipt" "${run_dir}/identity.txt"
done
curl --connect-timeout 5 --max-time 20 -fsS "${base_url}/health" \
  >"${run_dir}/health-before-trace-client.json"
curl --connect-timeout 5 --max-time 20 -fsS "${base_url}/v1/models" \
  >"${run_dir}/models-before-trace-client.json"
jq -e --arg model "$model" '.data | any(.id == $model and .max_model_len == 16512)' \
  "${run_dir}/models-before-trace-client.json" >/dev/null

for row in 1 2; do
  timeout --signal=TERM --kill-after=10s 910s "$python" "$depth_harness" --execute \
    --fixture "$depth_fixture" --depth 4096 --context-capacity 16512 \
    --base-url "$base_url" --model "$model" --response-adapter vllm --timeout 900 \
    --out "${run_dir}/exact-depth-4k-trace-r${row}.json" \
    >"${run_dir}/exact-depth-4k-trace-r${row}.log" 2>&1
done

"$python" - "$run_dir" "$trace_file" <<'PY'
import json
import os
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
trace_path = pathlib.Path(sys.argv[2])
results = [
    json.loads((root / f"exact-depth-4k-trace-r{index}.json").read_text())
    for index in (1, 2)
]
for result in results:
    assert result["status"] == "passed" and result["gate"]["passed"] is True
    usage = result["response"]["usage"]
    assert (usage["prompt_tokens"], usage["completion_tokens"], usage["total_tokens"]) == (4096, 128, 4224)
    assert usage["prompt_tokens_details"]["cached_tokens"] == 0
    assert result["response"]["finish_reasons"] == ["length"]
    assert len(result["response"]["token_ids"]) == 128
    assert result["request"]["request_payload_sha256"] == "2d92a2857d5cf45c3dcbc9d856cba714e2a36003295159fb5fcf1a8effb930be"

trace_rows = [json.loads(line) for line in trace_path.read_text().splitlines()]
assert len(trace_rows) == 256
by_occurrence = {
    occurrence: [row for row in trace_rows if row["request_occurrence"] == occurrence]
    for occurrence in (1, 2)
}
for occurrence, rows in by_occurrence.items():
    assert len(rows) == 128
    assert [row["output_index_before_sample"] for row in rows] == list(range(128))
    assert all(row["sampled_equals_top1"] is True for row in rows)
    sampled = [row["sampled_token_id"] for row in rows]
    assert sampled == results[occurrence - 1]["response"]["token_ids"]

left, right = by_occurrence[1], by_occurrence[2]

def first_difference(key):
    return next((index for index in range(128) if left[index][key] != right[index][key]), None)

first_sampled = first_difference("sampled_token_id")
first_top_ids = first_difference("top_token_ids")
first_top_values = first_difference("top_logits_float_hex")
if first_sampled is None:
    classification = "repeat-stable-under-report-only-trace"
else:
    assert left[first_sampled]["top_token_ids"][0] != right[first_sampled]["top_token_ids"][0]
    classification = "raw-greedy-top1-divergence"

summary = {
    "schema": "neural.download.qwen38-flash-next.greedy-decision-trace.v1",
    "status": "evidence-complete",
    "classification": classification,
    "requests": 2,
    "records": len(trace_rows),
    "records_per_occurrence": [len(by_occurrence[1]), len(by_occurrence[2])],
    "request_payload_sha256": results[0]["request"]["request_payload_sha256"],
    "output_token_ids_sha256": [result["response"]["output_token_ids_sha256"] for result in results],
    "first_sampled_token_difference_index": first_sampled,
    "first_top8_id_difference_index": first_top_ids,
    "first_top8_value_difference_index": first_top_values,
    "first_sampled_difference_rows": None if first_sampled is None else [left[first_sampled], right[first_sampled]],
    "diagnostic_rates_tok_s": [result["metric_window"]["conventional_99_interval_tok_s"] for result in results],
    "performance_credit": False,
    "performance_note": "The report-only trace synchronizes every selected decision, so its rates are not comparable to protected measurements.",
    "protected_results_changed": False,
    "active_16k_requests": 0,
}
destination = root / "greedy-trace-analysis.json"
temporary = destination.with_name(destination.name + f".tmp.{os.getpid()}")
temporary.write_text(json.dumps(summary, indent=2) + "\n")
os.replace(temporary, destination)
PY

write_atomic "${run_dir}/greedy-trace-client-gates-passed.txt" \
  'PASS two exact-4K requests and complete bounded greedy-decision trace; no performance or deployment credit'
