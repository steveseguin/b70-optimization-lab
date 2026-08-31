#!/usr/bin/env bash
set -Eeuo pipefail

repo=/home/steve/llm-optimizations
run_dir=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-eager-mtp0-4352-ple-only-r1-attempt28
profile_dir=/mnt/fast-ai/q38-profiles/attempt28
base_url=http://127.0.0.1:19700
model=qwen38-flash-next-fp8-tp4
python=/home/steve/.venvs/vllm-xpu/bin/python
depth_harness="${repo}/scripts/bench-openai-token-depth-suite.py"
fixture="${repo}/data/qwen27-exact-depth/qwen38-flash-next-bcd9f01-exact-depth-v1.json"
summarizer="${repo}/experiments/qwen38-flash-next-fp8-b70/tools/summarize-tp4-target-decode-kineto.py"
expected_summarizer=53620dc6bf658a9bda63b4077a00bfc9710b6856e428116c3ff8237f1abc60a8
profiler_active=0

stop_profiler() {
  local stop_rc
  (( profiler_active == 1 )) || return 0
  set +e
  curl --connect-timeout 5 --max-time 120 -fsS \
    -D "${run_dir}/profile-stop.headers" -o "${run_dir}/profile-stop.body" \
    -X POST "${base_url}/stop_profile"
  stop_rc=$?
  set -e
  printf '%s\n' "$stop_rc" >"${run_dir}/profile-stop.rc"
  profiler_active=0
  (( stop_rc == 0 )) || return "$stop_rc"
  grep -Eq '^HTTP/[0-9.]+ 200' "${run_dir}/profile-stop.headers"
}

[[ $# == 0 ]] || { printf 'FAIL: A28 profile window takes no arguments\n' >&2; exit 2; }
[[ -d "$run_dir" && -d "$profile_dir" ]] || { printf 'FAIL: A28 profile paths are absent\n' >&2; exit 1; }
[[ "$(sha256sum "$depth_harness" | cut -d' ' -f1)" == 8f162c1ab9fde7e0daffed2c4f0d6ff061ad6076c5de716e36f3d883ab4a1067 ]]
[[ "$(sha256sum "$fixture" | cut -d' ' -f1)" == c44fccbaf600cc506d8ed0cc7357161057b86abc44469b611be71db97558061d ]]
[[ "$(sha256sum "$summarizer" | cut -d' ' -f1)" == "$expected_summarizer" ]]
[[ -z "$(find "$profile_dir" -mindepth 1 -print -quit)" ]] || { printf 'FAIL: A28 profile directory is not empty\n' >&2; exit 1; }
for artifact in profile-start.headers profile-start.body profile-start.rc \
  profile-stop.headers profile-stop.body profile-stop.rc profile-exact-depth-4k.json \
  profile-exact-depth-4k.log profile-exact-depth-4k.rc profile-summary.json \
  profile-trace-manifest.json; do
  [[ ! -e "${run_dir}/${artifact}" ]] || { printf 'FAIL: refusing to overwrite %s\n' "$artifact" >&2; exit 1; }
done

set +e
curl --connect-timeout 5 --max-time 30 -fsS -D "${run_dir}/profile-start.headers" \
  -o "${run_dir}/profile-start.body" -X POST "${base_url}/start_profile"
start_rc=$?
set -e
printf '%s\n' "$start_rc" >"${run_dir}/profile-start.rc"
(( start_rc == 0 )) || exit "$start_rc"
profiler_active=1
trap 'stop_profiler || true' EXIT
grep -Eq '^HTTP/[0-9.]+ 200' "${run_dir}/profile-start.headers"

set +e
timeout --signal=TERM --kill-after=10s 910s "$python" "$depth_harness" --execute \
  --fixture "$fixture" --depth 4096 --context-capacity 4352 \
  --base-url "$base_url" --model "$model" --response-adapter vllm --timeout 900 \
  --out "${run_dir}/profile-exact-depth-4k.json" \
  >"${run_dir}/profile-exact-depth-4k.log" 2>&1
request_rc=$?
set -e
printf '%s\n' "$request_rc" >"${run_dir}/profile-exact-depth-4k.rc"
(( request_rc == 0 )) || exit "$request_rc"

stop_profiler
trap - EXIT

for _ in $(seq 1 120); do
  trace_count=$(find "$profile_dir" -maxdepth 1 -type f -name '*.pt.trace.json.gz' | wc -l)
  table_count=$(find "$profile_dir" -maxdepth 1 -type f -name 'profiler_out_[0-3].txt' | wc -l)
  (( trace_count == 4 && table_count == 4 )) && break
  sleep 1
done
(( trace_count == 4 && table_count == 4 )) || {
  printf 'FAIL: expected four A28 traces and four profiler tables, got %s/%s\n' "$trace_count" "$table_count" >&2
  exit 1
}
while IFS= read -r trace; do
  [[ -s "$trace" ]]
  gzip -t -- "$trace"
done < <(find "$profile_dir" -maxdepth 1 -type f -name '*.pt.trace.json.gz' | sort)
for rank in 0 1 2 3; do
  [[ -s "${profile_dir}/profiler_out_${rank}.txt" ]]
done
"$python" "$summarizer" "$profile_dir" \
  --output "${run_dir}/profile-summary.json"

"$python" - "$run_dir" "$profile_dir" <<'PY'
import hashlib
import json
import os
import pathlib
import sys

run_dir = pathlib.Path(sys.argv[1])
profile_dir = pathlib.Path(sys.argv[2])
result = json.loads((run_dir / "profile-exact-depth-4k.json").read_text())
assert result["status"] == "passed" and result["gate"]["passed"] is True
usage = result["response"]["usage"]
assert (usage["prompt_tokens"], usage["completion_tokens"], usage["total_tokens"]) == (4096, 128, 4224)
details = usage["prompt_tokens_details"]
assert details.get("cached_tokens") == 0 and details.get("created_cache_tokens") == 0
assert result["response"]["finish_reasons"] == ["length"]
assert len(result["response"]["token_ids"]) == 128
files = []
for path in sorted(profile_dir.iterdir()):
    assert path.is_file(), path
    files.append({
        "name": path.name,
        "bytes": path.stat().st_size,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    })
trace_files = [item for item in files if item["name"].endswith(".pt.trace.json.gz")]
table_files = [item for item in files if item["name"].startswith("profiler_out_")]
assert len(trace_files) == 4 and len(table_files) == 4, (trace_files, table_files)
manifest = {
    "schema_version": 1,
    "status": "captured",
    "classification": "report_only_profile_throughput_invalid",
    "profile_dir": str(profile_dir),
    "config": {
        "activities": ["CPU", "XPU"],
        "delay_iterations": 65,
        "max_iterations": 4,
        "record_shapes": True,
        "with_stack": False,
        "with_memory": False,
        "ignore_frontend": True,
        "expected_context": "64 p4096 chunked-prefill iterations, then four pure decode iterations",
        "analysis_window": "discard first captured decode context; aggregate remaining three",
    },
    "request": {
        "prompt_tokens": 4096,
        "completion_tokens": 128,
        "cached_tokens": 0,
        "output_token_ids_sha256": result["response"]["output_token_ids_sha256"],
        "timing_is_permanently_ineligible_for_speed_credit": True,
    },
    "files": files,
    "offline_summary": {
        "path": str(run_dir / "profile-summary.json"),
        "sha256": hashlib.sha256((run_dir / "profile-summary.json").read_bytes()).hexdigest(),
    },
}
destination = run_dir / "profile-trace-manifest.json"
temporary = destination.with_name(destination.name + f".tmp.{os.getpid()}")
temporary.write_text(json.dumps(manifest, indent=2) + "\n")
os.replace(temporary, destination)
PY
