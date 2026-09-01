#!/usr/bin/env bash
set -Eeuo pipefail

repo=/home/steve/llm-optimizations
vllm=/home/steve/src/vllm-current-main
python=/home/steve/.venvs/vllm-xpu/bin/python3
stage_root=/mnt/usb-models/qwen38-build/runtime-core-moe-negidguard-b70
stage="${stage_root}/vllm_xpu_kernels"
model=/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8
tool="${repo}/experiments/qwen38-flash-next-fp8-b70/tools/fullshape-triton-fp8-moe-gate.py"
stage_manifest="${repo}/experiments/qwen38-flash-next-fp8-b70/data/runtime-stage-padding-guard-loadable.sha256"
result=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/components/20260901-moe-m1-w2-census-a1
loader_suffix=/home/steve/.venvs/vllm-xpu/lib:/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/lib:/opt/intel/oneapi/compiler/2025.3/lib:/opt/intel/oneapi/compiler/2025.3/opt/compiler/lib

expected_vllm=cbc3cb588a7cae8dcc489fb4dfc1a800d19980d9
expected_tool=d0485a8f3f40c3312a439d8970cd7ab47bbfa597ab537c932dfc2f6566ddd94a
expected_stage_manifest=9fa443fdb7a6d0042cf04f859cc6fd6a7bdc09943e16cafb4ea084573c892d2b
expected_shard2=6841fe21fa8a8a7a693c585efe65cd2732889095b696da88bda0cb287366910b
expected_shard3=974a2a2ab551f8f1405a4955ab32a8721c68c73dd85b382491d9f0e6a34ee752

fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
digest() { sha256sum "$1" | cut -d' ' -f1; }

[[ $# == 0 ]] || fail "this frozen census takes no arguments"
[[ "${Q38_MOE_CENSUS_VALIDATE_ONLY:-0}" =~ ^[01]$ ]] || fail "invalid validate-only selector"
[[ -x "$python" ]] || fail "vLLM XPU interpreter is missing"
[[ -f "$tool" && "$(digest "$tool")" == "$expected_tool" ]] || fail "component tool drifted"
[[ -f "$stage_manifest" && "$(digest "$stage_manifest")" == "$expected_stage_manifest" ]] || fail "runtime-stage manifest drifted"
(cd "$stage" && sha256sum -c "$stage_manifest") >/dev/null || fail "runtime-stage files drifted"
[[ "$(git -C "$vllm" rev-parse HEAD)" == "$expected_vllm" ]] || fail "vLLM head drifted"
[[ -z "$(git -C "$vllm" status --porcelain --untracked-files=no)" ]] || fail "vLLM tracked source is dirty"
[[ "$(digest "${model}/model-00002-of-00131.safetensors")" == "$expected_shard2" ]] || fail "checkpoint shard 2 drifted"
[[ "$(digest "${model}/model-00003-of-00131.safetensors")" == "$expected_shard3" ]] || fail "checkpoint shard 3 drifted"
read -r mount_source mount_type mount_target < <(findmnt -nro SOURCE,FSTYPE,TARGET --target /mnt/usb-models)
[[ "$mount_source" == /dev/sda2 && "$mount_type" == fuseblk && "$mount_target" == /mnt/usb-models ]] || fail "evidence drive is not mounted"
[[ ! -e "$result" ]] || fail "evidence root already exists"
[[ -z "$(pgrep -af 'vllm serve|VLLM::EngineCore|Worker_TP|fullshape-triton-fp8-moe-gate' || true)" ]] || fail "conflicting model/component process is active"

if [[ "${Q38_MOE_CENSUS_VALIDATE_ONLY:-0}" == 1 ]]; then
  printf 'PASS: M1 w2 phase census validates without GPU work\n'
  exit 0
fi

exec 9>/tmp/q38-moe-m1-w2-census.lock
flock -n 9 || fail "another M1 w2 census owns the lock"
mkdir -p "$result"
install -m 0644 "$0" "${result}/runner.sh"
xpu-smi discovery -j >"${result}/device-discovery.json"
jq -e '.device_list | length == 4 and all(.[]; .device_name == "Intel(R) Arc(TM) Pro B70 Graphics")' \
  "${result}/device-discovery.json" >/dev/null || fail "four-B70 discovery failed"

{
  printf 'boot_id=%s\n' "$(cat /proc/sys/kernel/random/boot_id)"
  printf 'vllm_head=%s\n' "$expected_vllm"
  printf 'runner_sha256=%s\n' "$(digest "$0")"
  printf 'tool_sha256=%s\n' "$expected_tool"
  printf 'runtime_stage_manifest_sha256=%s\n' "$expected_stage_manifest"
  printf 'model_revision=bcd9f01ddc9cff2316eb84281bebcd5b058bddce\n'
  printf 'scope=one-B70 real-weight layer0 EP-rank0 M1 modular w2 phase screen\n'
} >"${result}/identity.txt"

run_arm() {
  local label=$1 config=$2
  local log="${result}/${label}.jsonl" err="${result}/${label}.stderr"
  local -a command=(
    env -u ZE_AFFINITY_MASK
    ONEAPI_DEVICE_SELECTOR=level_zero:0
    VLLM_TARGET_DEVICE=xpu
    PYTHONNOUSERSITE=1
    PYTHONSAFEPATH=1
    PYTHONDONTWRITEBYTECODE=1
    "PYTHONPATH=${stage_root}:${vllm}"
    "LD_LIBRARY_PATH=${stage}:${loader_suffix}"
    "$python" "$tool"
    --tokens 1
    --ep-rank 0
    --path modular
    --weights layer0-checkpoint
    --routing balanced-global
    --repeats 3
    --warmups 5
    --timed-batches 9
    --iterations-per-batch 100
    --hidden-seed 20260827
    --hidden-scale 0.01
    --model-path "$model"
  )
  command+=(--candidate-config-json "$config")
  printf '%q ' timeout --signal=TERM --kill-after=20s 180s "${command[@]}" >>"${result}/commands.sh"
  printf '> %q 2> %q\n' "$log" "$err" >>"${result}/commands.sh"
  timeout --signal=TERM --kill-after=20s 180s "${command[@]}" >"$log" 2>"$err" || fail "$label failed"
  jq -e 'select(.status == "pass") | .finite == true and .unique_output_sha256 == 1 and (.timing_median_us | isfinite)' \
    < <(tail -1 "$log") >/dev/null || fail "$label result contract failed"
}

# The retained common warps-8 config is the control. Only w2 changes in the
# candidate arms; w13 and expert assignment remain byte-for-byte configured as
# the control.
run_arm control-before '{"num_warps":8}'
run_arm w2-warps4 '{"num_warps":8,"W2_CONFIG":{"num_warps":4}}'
run_arm w2-n32-warps8 '{"num_warps":8,"W2_CONFIG":{"BLOCK_SIZE_N":32,"num_warps":8}}'
run_arm w2-n32-warps4 '{"num_warps":8,"W2_CONFIG":{"BLOCK_SIZE_N":32,"num_warps":4}}'
run_arm w2-n128-warps8 '{"num_warps":8,"W2_CONFIG":{"BLOCK_SIZE_N":128,"num_warps":8}}'
run_arm w2-n128-warps4 '{"num_warps":8,"W2_CONFIG":{"BLOCK_SIZE_N":128,"num_warps":4}}'
run_arm w2-k64-warps8 '{"num_warps":8,"W2_CONFIG":{"BLOCK_SIZE_K":64,"num_warps":8}}'
run_arm control-after '{"num_warps":8}'

"$python" - "$result" <<'PY'
import json
import statistics
import sys
from pathlib import Path

root = Path(sys.argv[1])
rows = {}
for path in sorted(root.glob("*.jsonl")):
    value = json.loads(path.read_text().splitlines()[-1])
    rows[path.stem] = {
        "median_us": value["timing_median_us"],
        "p10_us": value["timing_p10_us"],
        "p90_us": value["timing_p90_us"],
        "output_sha256": value["output_sha256_first"],
        "resolved_config": value["identity"]["resolved_config"],
    }
control = statistics.mean(
    [rows["control-before"]["median_us"], rows["control-after"]["median_us"]]
)
authority = rows["control-before"]["output_sha256"]
if rows["control-after"]["output_sha256"] != authority:
    raise SystemExit("control output hash drifted")
for name, row in rows.items():
    row["exact"] = row["output_sha256"] == authority
    row["latency_reduction_percent"] = 100.0 * (1.0 - row["median_us"] / control)
candidates = {name: row for name, row in rows.items() if not name.startswith("control-")}
ranked = sorted(
    candidates,
    key=lambda name: (
        not candidates[name]["exact"],
        -candidates[name]["latency_reduction_percent"],
    ),
)
summary = {
    "schema_version": 1,
    "status": "complete",
    "classification": "modular_w2_component_screen_only",
    "control_bracket_mean_us": control,
    "authority_output_sha256": authority,
    "rows": rows,
    "ranked_lossless_candidates": [name for name in ranked if candidates[name]["exact"]],
    "confirmation_authorized": [
        name for name in ranked
        if candidates[name]["exact"] and candidates[name]["latency_reduction_percent"] >= 3.0
    ],
    "protected_results_changed": False,
}
(root / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
print(json.dumps(summary, indent=2, sort_keys=True))
PY

sha256sum "${result}/"* >"${result}/SHA256SUMS"
printf 'PASS: M1 w2 phase census complete: %s\n' "$result"
