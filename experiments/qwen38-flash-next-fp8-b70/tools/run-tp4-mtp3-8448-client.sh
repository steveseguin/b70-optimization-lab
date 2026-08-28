#!/usr/bin/env bash
set -Eeuo pipefail

repo=/home/steve/llm-optimizations
supervisor="${repo}/experiments/qwen38-flash-next-fp8-b70/tools/supervise-tp4-mtp3-8448.sh"
state=/tmp/q38-mtp3-8448-supervisor
run_dir=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-eager-mtp3-8448-r1-attempt1
harness="${repo}/scripts/bench-openai-token-depth-suite.py"
fixture="${repo}/data/qwen27-exact-depth/qwen38-flash-next-bcd9f01-exact-depth-v1.json"
reference=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-eager-mtp0-8448-r1-attempt1/exact-depth-8k-o128.json
mtp2_comparator=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-eager-mtp2-8448-r1-attempt2/exact-depth-8k-o128.json
python=/home/steve/.venvs/vllm-xpu/bin/python
base_url=http://127.0.0.1:19669
model=qwen38-flash-next-fp8-tp4
output="${run_dir}/exact-depth-8k-o128.json"
expected_harness=8f162c1ab9fde7e0daffed2c4f0d6ff061ad6076c5de716e36f3d883ab4a1067
expected_fixture=c44fccbaf600cc506d8ed0cc7357161057b86abc44469b611be71db97558061d
expected_reference=2a8bfbb133ae4cf1b54ee31fd1c632ea8f843b7109fa72baff5b69d357e453aa
expected_reference_output=0efd150b868d63f11cb4327bec07b02c7778d137142495924139e5221b4cebd3
expected_mtp2_comparator=409e4e58259085a8bb7253a23951b0e396f52d09555e5146a1c157d97e54a324
expected_mtp2_output=d3ce0631eb382e39168ee6bbbf177b0d49fbb27bc6c6466bcf215f16db8d0220
expected_mtp2_text=68c50214e241e6613efdd0b0bbbfea36995d917448b1db527f3dc3fb03cd8b70
expected_prompt=6baa17bea14f0ecad7e4edf54a05256eafaef1d447a447569fd303371c671741
expected_payload=d2c65090ce71e4db33b834b3de55a82a8c4c2f9485baaf94adb156ee686a0e1b
expected_supervisor=94292d12f8de643cbe62c114dcf2f906450e7e04c75ffa914ddb18df3cc48ef1

write_url() {
  local url=$1 path=$2 tmp
  tmp="${path}.tmp.$$"
  curl --connect-timeout 5 --max-time 20 -fsS "$url" >"$tmp"
  mv "$tmp" "$path"
}

[[ $# == 0 ]] || { printf 'FAIL: client takes no arguments\n' >&2; exit 2; }
[[ -d "$run_dir" ]] || { printf 'FAIL: run directory missing\n' >&2; exit 1; }
[[ "$(sha256sum "$harness" | cut -d' ' -f1)" == "$expected_harness" ]] || { printf 'FAIL: harness hash mismatch\n' >&2; exit 1; }
[[ "$(sha256sum "$fixture" | cut -d' ' -f1)" == "$expected_fixture" ]] || { printf 'FAIL: fixture hash mismatch\n' >&2; exit 1; }
[[ "$(sha256sum "$reference" | cut -d' ' -f1)" == "$expected_reference" ]] || { printf 'FAIL: MTP0 reference hash mismatch\n' >&2; exit 1; }
[[ "$(sha256sum "$mtp2_comparator" | cut -d' ' -f1)" == "$expected_mtp2_comparator" ]] || { printf 'FAIL: MTP2 comparator hash mismatch\n' >&2; exit 1; }
[[ "$(sha256sum "$supervisor" | cut -d' ' -f1)" == "$expected_supervisor" ]] || { printf 'FAIL: supervisor hash mismatch\n' >&2; exit 1; }
supervisor_pid=$(cat "${state}.pid" 2>/dev/null || true)
server_pid=$(cat "${run_dir}/server.pid" 2>/dev/null || true)
recorded_server_pid=$(cat "${state}.server.pid" 2>/dev/null || true)
[[ "$supervisor_pid" =~ ^[1-9][0-9]*$ && -e "/proc/${supervisor_pid}" ]] || { printf 'FAIL: live supervisor is absent\n' >&2; exit 1; }
[[ "$server_pid" =~ ^[1-9][0-9]*$ && "$server_pid" == "$recorded_server_pid" && -e "/proc/${server_pid}" ]] || { printf 'FAIL: owned live server is absent\n' >&2; exit 1; }
supervisor_command=$(tr '\0' ' ' <"/proc/${supervisor_pid}/cmdline")
server_command=$(tr '\0' ' ' <"/proc/${server_pid}/cmdline")
[[ "$supervisor_command" == *"${supervisor}"* ]] || { printf 'FAIL: supervisor command identity mismatch\n' >&2; exit 1; }
[[ "$server_command" == *"vllm serve /mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8"* && \
   "$server_command" == *"--port 19669"* ]] || { printf 'FAIL: server command identity mismatch\n' >&2; exit 1; }
for artifact in health-before-request.json models-before-request.json \
  metrics-before-request.prom exact-depth-8k-o128.json client-request.log \
  client-request.rc metrics-after-request.prom request1-adjudication.json \
  request1-classified.txt; do
  [[ ! -e "${run_dir}/${artifact}" ]] || { printf 'FAIL: refusing to overwrite %s\n' "$artifact" >&2; exit 1; }
done

write_url "${base_url}/health" "${run_dir}/health-before-request.json"
write_url "${base_url}/v1/models" "${run_dir}/models-before-request.json"
jq -e --arg model "$model" '.data | any(.id == $model)' \
  "${run_dir}/models-before-request.json" >/dev/null
write_url "${base_url}/metrics" "${run_dir}/metrics-before-request.prom"

"$python" - "${run_dir}/metrics-before-request.prom" "${run_dir}/server.log" <<'PY'
import pathlib
import re
import sys

metrics = pathlib.Path(sys.argv[1]).read_text()
server_log = pathlib.Path(sys.argv[2]).read_text(errors="replace")
line = next((line for line in metrics.splitlines() if line.startswith("vllm:cache_config_info{")), None)
if line is None:
    raise RuntimeError("cache_config_info is absent")
labels = dict(re.findall(r'(\w+)="([^"]*)"', line))
required = {
    "kv_cache_memory_bytes": "376569856",
    "num_gpu_blocks": "32",
    "enable_prefix_caching": "False",
}
for key, expected in required.items():
    if labels.get(key) != expected:
        raise RuntimeError(f"{key}={labels.get(key)!r}, expected {expected!r}")
capacity = int(labels.get("kv_cache_size_tokens", "0"))
if capacity < 8320:
    raise RuntimeError(f"reported cache capacity {capacity} is below 8320")
if server_log.count("Total CPU offloaded parameters: 12.22") != 4:
    raise RuntimeError("exact four-rank 12.22-GiB offload receipt is absent")
PY

set +e
timeout --signal=TERM --kill-after=10s 910s \
  "$python" "$harness" --execute --fixture "$fixture" --depth 8192 \
  --context-capacity 8448 --base-url "$base_url" --model "$model" \
  --response-adapter vllm --timeout 900 --out "$output" \
  >"${run_dir}/client-request.log" 2>&1
rc=$?
set -e
tmp="${run_dir}/client-request.rc.tmp.$$"
printf '%s\n' "$rc" >"$tmp"
mv "$tmp" "${run_dir}/client-request.rc"
(( rc == 0 )) || exit "$rc"

write_url "${base_url}/metrics" "${run_dir}/metrics-after-request.prom"
"$python" - "$output" "$reference" "$mtp2_comparator" "${run_dir}/metrics-before-request.prom" \
  "${run_dir}/metrics-after-request.prom" "${run_dir}/request1-adjudication.json" \
  "$expected_reference_output" "$expected_mtp2_output" "$expected_mtp2_text" \
  "$expected_prompt" "$expected_payload" <<'PY'
import json
import os
import pathlib
import re
import sys

(
    candidate_path, reference_path, mtp2_path, before_path, after_path,
    output_path, expected_reference_hash, expected_mtp2_hash,
    expected_mtp2_text, expected_prompt_hash, expected_payload_hash,
) = sys.argv[1:]
candidate = json.loads(pathlib.Path(candidate_path).read_text())
reference = json.loads(pathlib.Path(reference_path).read_text())
mtp2 = json.loads(pathlib.Path(mtp2_path).read_text())

def metric(path, name, position=None):
    text = pathlib.Path(path).read_text()
    for line in text.splitlines():
        if not line.startswith(name + "{"):
            continue
        if position is not None and f'position="{position}"' not in line:
            continue
        return float(line.rsplit(" ", 1)[1])
    raise RuntimeError(f"metric missing: {name} position={position}")

if candidate.get("status") != "passed" or candidate.get("gate", {}).get("passed") is not True:
    raise RuntimeError("generic exact-depth gate did not pass")
if candidate.get("request", {}).get("prompt_token_ids_sha256") != expected_prompt_hash:
    raise RuntimeError("frozen request prompt hash changed")
if candidate.get("request", {}).get("request_payload_sha256") != expected_payload_hash:
    raise RuntimeError("frozen request payload hash changed")
response = candidate["response"]
usage = response["usage"]
if usage.get("prompt_tokens") != 8192 or usage.get("completion_tokens") != 128 or usage.get("total_tokens") != 8320:
    raise RuntimeError(f"unexpected usage: {usage!r}")
if usage.get("prompt_tokens_details", {}).get("cached_tokens") != 0:
    raise RuntimeError("cache reuse is nonzero")
if response.get("finish_reasons") != ["length"] or len(response.get("token_ids", [])) != 128:
    raise RuntimeError("output length/finish gate failed")

names = {
    "drafts": "vllm:spec_decode_num_drafts_total",
    "draft_tokens": "vllm:spec_decode_num_draft_tokens_total",
    "accepted_tokens": "vllm:spec_decode_num_accepted_tokens_total",
}
deltas = {key: metric(after_path, name) - metric(before_path, name) for key, name in names.items()}
positions = [
    metric(after_path, "vllm:spec_decode_num_accepted_tokens_per_pos_total", position) -
    metric(before_path, "vllm:spec_decode_num_accepted_tokens_per_pos_total", position)
    for position in ("0", "1", "2")
]
if not all(value > 0 for value in (*deltas.values(), *positions)):
    raise RuntimeError(f"MTP3 counter deltas are not all positive: {deltas!r}, {positions!r}")
if sum(positions) != deltas["accepted_tokens"]:
    raise RuntimeError(f"MTP3 position sum does not equal accepted tokens: {positions!r}, {deltas!r}")

reference_hash = reference["response"]["output_token_ids_sha256"]
candidate_hash = response["output_token_ids_sha256"]
if reference_hash != expected_reference_hash:
    raise RuntimeError("frozen authority output-token hash changed")
mtp2_hash = mtp2["response"]["output_token_ids_sha256"]
mtp2_text = mtp2["response"]["text_sha256"]
if mtp2_hash != expected_mtp2_hash or mtp2_text != expected_mtp2_text:
    raise RuntimeError("frozen descriptive MTP2 comparator changed")
parity = candidate_hash == reference_hash
candidate_ids = response["token_ids"]
reference_ids = reference["response"]["token_ids"]
if len(candidate_ids) != 128 or len(reference_ids) != 128:
    raise RuntimeError("candidate or frozen authority does not contain exactly 128 token IDs")
first_divergence = next((index for index, pair in enumerate(zip(candidate_ids, reference_ids)) if pair[0] != pair[1]), None)
adjudication = {
    "status": "passed" if parity else "quarantined-cross-runtime-parity",
    "generic_exact_depth_gate": "passed",
    "prompt_tokens": 8192,
    "completion_tokens": 128,
    "cached_tokens": 0,
    "candidate_output_token_ids_sha256": candidate_hash,
    "frozen_mtp0_output_token_ids_sha256": reference_hash,
    "target_parity": parity,
    "first_divergent_generated_token_index_zero_based": first_divergence,
    "mtp_counter_deltas": {**deltas, "accepted_tokens_per_position": positions},
    "descriptive_mtp2_comparator": {
        "output_token_ids_sha256": mtp2_hash,
        "text_sha256": mtp2_text,
        "candidate_output_parity": candidate_hash == mtp2_hash,
        "gating": False,
    },
    "diagnostic_rate_tok_s": candidate["metric_window"]["conventional_99_interval_tok_s"],
    "diagnostic_ttft_s": candidate["metric_window"]["time_to_first_token_s"],
    "speed_credit": False,
    "quality_credit": False,
    "interpretation": "A mismatch is scoped to the frozen cross-runtime/cache authority and does not isolate MTP3 as the cause.",
}
destination = pathlib.Path(output_path)
temporary = destination.with_name(f"{destination.name}.tmp.{os.getpid()}")
temporary.write_text(json.dumps(adjudication, indent=2) + "\n")
os.replace(temporary, destination)
PY

status=$(jq -r '.status' "${run_dir}/request1-adjudication.json")
tmp="${run_dir}/request1-classified.txt.tmp.$$"
if [[ "$status" == passed ]]; then
  printf '%s\n' 'PASS generic exact-8K MTP3 counters cache-zero and frozen MTP0 parity' >"$tmp"
elif [[ "$status" == quarantined-cross-runtime-parity ]]; then
  printf '%s\n' 'QUARANTINE generic exact-8K and MTP3 counters pass; frozen cross-runtime parity differs' >"$tmp"
else
  printf 'FAIL: unknown adjudication status %s\n' "$status" >&2
  exit 1
fi
mv "$tmp" "${run_dir}/request1-classified.txt"
