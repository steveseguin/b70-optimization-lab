#!/usr/bin/env bash
set -Eeuo pipefail

repo=/home/steve/llm-optimizations
vllm=/home/steve/src/vllm-current-main
kernels=/home/steve/src/vllm-xpu-kernels
python=/home/steve/.venvs/vllm-xpu/bin/python3
stage_root=/mnt/usb-models/qwen38-build/runtime-core-moe-negidguard-b70
stage="${stage_root}/vllm_xpu_kernels"
model=/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8
tool="${repo}/experiments/qwen38-flash-next-fp8-b70/tools/fullshape-triton-fp8-moe-gate.py"
config_dir="${repo}/experiments/qwen38-flash-next-fp8-b70/configs/moe-warps8-m1"
result=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/components/20260831-ep4-partition-device-interaction-replicate-a2
loader_suffix=/home/steve/.venvs/vllm-xpu/lib:/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/lib:/opt/intel/oneapi/compiler/2025.3/lib:/opt/intel/oneapi/compiler/2025.3/opt/compiler/lib

expected_vllm=797769b34b6db5c934609b75dc04cc61ec66e5f9
expected_kernels=eeee7d671abfa964626baa18da2174bb92cac80a
expected_tool=bc01e4c51a8a389fc6af4d050bf490e1819fa92469fe9f6ae920c1e957a08e92
expected_config=91e5d8b692da3febbba7cb07ee4fdab319909da0c82c1fda95b92dc42d680464
expected_stage_manifest=9fa443fdb7a6d0042cf04f859cc6fd6a7bdc09943e16cafb4ea084573c892d2b
stage_manifest="${repo}/experiments/qwen38-flash-next-fp8-b70/data/runtime-stage-padding-guard-loadable.sha256"
expected_shard2=6841fe21fa8a8a7a693c585efe65cd2732889095b696da88bda0cb287366910b
expected_shard3=974a2a2ab551f8f1405a4955ab32a8721c68c73dd85b382491d9f0e6a34ee752
fixed_ids=10,60,109,148,189,251,265,408,475,482

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

digest() {
  sha256sum "$1" | cut -d' ' -f1
}

[[ $# == 0 ]] || fail "this frozen replicate takes no arguments"
[[ "${Q38_EP4_INTERACTION_VALIDATE_ONLY:-0}" =~ ^[01]$ ]] || fail "invalid validate-only selector"
[[ -x "$python" ]] || fail "vLLM XPU interpreter is missing"
[[ -f "$tool" && "$(digest "$tool")" == "$expected_tool" ]] || fail "component tool drifted"
[[ -f "$stage_manifest" && "$(digest "$stage_manifest")" == "$expected_stage_manifest" ]] || fail "runtime-stage manifest drifted"
(cd "$stage" && sha256sum -c "$stage_manifest") >/dev/null || fail "runtime-stage files drifted"
config_file="${config_dir}/E=128,N=640,device_name=Intel(R)_Arc(TM)_Pro_B70_Graphics,dtype=fp8_w8a8,block_shape=[128,128].json"
[[ -f "$config_file" && "$(digest "$config_file")" == "$expected_config" ]] || fail "M1 config drifted"
[[ "$(git -C "$vllm" rev-parse HEAD)" == "$expected_vllm" ]] || fail "vLLM head drifted"
[[ -z "$(git -C "$vllm" status --porcelain --untracked-files=no)" ]] || fail "vLLM tracked source is dirty"
[[ "$(git -C "$kernels" rev-parse HEAD)" == "$expected_kernels" ]] || fail "kernel head drifted"
[[ -z "$(git -C "$kernels" status --porcelain --untracked-files=no)" ]] || fail "kernel tracked source is dirty"
[[ "$(digest "${model}/model-00002-of-00131.safetensors")" == "$expected_shard2" ]] || fail "checkpoint shard 2 drifted"
[[ "$(digest "${model}/model-00003-of-00131.safetensors")" == "$expected_shard3" ]] || fail "checkpoint shard 3 drifted"
read -r mount_source mount_type mount_target < <(findmnt -nro SOURCE,FSTYPE,TARGET --target /mnt/usb-models)
[[ "$mount_source" == /dev/sda2 && "$mount_type" == fuseblk && "$mount_target" == /mnt/usb-models ]] || fail "evidence drive is not mounted"
[[ ! -e "$result" ]] || fail "evidence root already exists"
[[ -z "$(pgrep -af 'vllm serve|VLLM::EngineCore|Worker_TP' || true)" ]] || fail "a model server is active"

if [[ "${Q38_EP4_INTERACTION_VALIDATE_ONLY:-0}" == 1 ]]; then
  printf 'PASS: EP4 partition/device interaction replicate validates without GPU work\n'
  exit 0
fi

exec 9>/tmp/q38-ep4-partition-device-interaction-replicate.lock
flock -n 9 || fail "another interaction replicate owns the lock"
mkdir -p "$result"
install -m 0644 "$0" "${result}/runner.sh"
xpu-smi discovery -j >"${result}/device-discovery.json"
jq -e '
  .device_list == [
    {
      "device_function_type": "physical",
      "device_id": 0,
      "device_name": "Intel(R) Arc(TM) Pro B70 Graphics",
      "device_type": "GPU",
      "drm_device": "/dev/dri/card3",
      "pci_bdf_address": "0000:23:00.0",
      "pci_device_id": "0xe223",
      "uuid": "00000000-0000-0023-0000-0000e2238086",
      "vendor_name": "Intel(R) Corporation"
    },
    {
      "device_function_type": "physical",
      "device_id": 1,
      "device_name": "Intel(R) Arc(TM) Pro B70 Graphics",
      "device_type": "GPU",
      "drm_device": "/dev/dri/card4",
      "pci_bdf_address": "0000:27:00.0",
      "pci_device_id": "0xe223",
      "uuid": "00000000-0000-0027-0000-0000e2238086",
      "vendor_name": "Intel(R) Corporation"
    },
    {
      "device_function_type": "physical",
      "device_id": 2,
      "device_name": "Intel(R) Arc(TM) Pro B70 Graphics",
      "device_type": "GPU",
      "drm_device": "/dev/dri/card0",
      "pci_bdf_address": "0000:43:00.0",
      "pci_device_id": "0xe223",
      "uuid": "00000000-0000-0043-0000-0000e2238086",
      "vendor_name": "Intel(R) Corporation"
    },
    {
      "device_function_type": "physical",
      "device_id": 3,
      "device_name": "Intel(R) Arc(TM) Pro B70 Graphics",
      "device_type": "GPU",
      "drm_device": "/dev/dri/card2",
      "pci_bdf_address": "0000:47:00.0",
      "pci_device_id": "0xe223",
      "uuid": "00000000-0000-0047-0000-0000e2238086",
      "vendor_name": "Intel(R) Corporation"
    }
  ]
' "${result}/device-discovery.json" >/dev/null || fail "physical B70 identity or ordering drifted"
{
  printf 'boot_id=%s\n' "$(cat /proc/sys/kernel/random/boot_id)"
  printf 'vllm_head=%s\n' "$expected_vllm"
  printf 'kernel_head=%s\n' "$expected_kernels"
  printf 'runner_sha256=%s\n' "$(digest "$0")"
  printf 'tool_sha256=%s\n' "$expected_tool"
  printf 'config_sha256=%s\n' "$expected_config"
  printf 'runtime_stage_manifest_sha256=%s\n' "$expected_stage_manifest"
  printf 'model_path=%s\n' "$model"
  printf 'shard2_sha256=%s\n' "$expected_shard2"
  printf 'shard3_sha256=%s\n' "$expected_shard3"
  printf 'fixed_expert_ids=%s\n' "$fixed_ids"
  printf 'selector_contract=ONEAPI_DEVICE_SELECTOR=level_zero:<physical_device>;ZE_AFFINITY_MASK=unset;tool_device=xpu:0\n'
  printf 'schedule=cycle1:p1d1,p1d0,p0d1;cycle2:p1d0,p0d1,p1d1;cycle3:p0d1,p1d1,p1d0;cycle4:p1d1,p0d1,p1d0\n'
} >"${result}/identity.txt"

run_cell() {
  local cycle=$1 expert=$2 device=$3 label log err
  local -a command
  label="cycle${cycle}-expert${expert}-device${device}"
  log="${result}/${label}.jsonl"
  err="${result}/${label}.stderr"
  command=(
    env
    -u ZE_AFFINITY_MASK
    ONEAPI_DEVICE_SELECTOR="level_zero:${device}"
    VLLM_TARGET_DEVICE=xpu
    PYTHONNOUSERSITE=1
    PYTHONSAFEPATH=1
    PYTHONDONTWRITEBYTECODE=1
    VLLM_TUNED_CONFIG_FOLDER="$config_dir"
    "PYTHONPATH=${stage_root}:${vllm}"
    "LD_LIBRARY_PATH=${stage}:${loader_suffix}"
    "$python" "$tool"
    --tokens 1
    --ep-rank "$expert"
    --weights layer0-checkpoint
    --routing fixed-ids
    --fixed-topk-ids "$fixed_ids"
    --repeats 3
    --warmups 20
    --timed-batches 15
    --iterations-per-batch 200
    --hidden-seed 20260826
    --hidden-scale 1.0
    --model-path "$model"
  )
  printf '%q ' timeout --signal=TERM --kill-after=30s 600s "${command[@]}" >>"${result}/commands.sh"
  printf '> %q 2> %q\n' "$log" "$err" >>"${result}/commands.sh"
  timeout --signal=TERM --kill-after=30s 600s "${command[@]}" >"$log" 2>"$err" || fail "$label failed"
  jq -e --argjson expert "$expert" '
    select(.status == "pass")
    | .identity.ep_rank == $expert
    and .identity.local_valid_routes > 0
    and .identity.resolved_config.num_warps == 8
    and .identity.timed_batches == 15
    and .identity.iterations_per_batch == 200
    and .unique_output_sha256 == 1
    and .finite == true
    and (.timing_median_us | isfinite)
  ' < <(tail -1 "$log") >/dev/null || fail "$label result contract failed"
}

run_cell 1 1 1
run_cell 1 1 0
run_cell 1 0 1
run_cell 2 1 0
run_cell 2 0 1
run_cell 2 1 1
run_cell 3 0 1
run_cell 3 1 1
run_cell 3 1 0
run_cell 4 1 1
run_cell 4 0 1
run_cell 4 1 0

"$python" - "$result" <<'PY'
import json
import statistics
import sys
from pathlib import Path

root = Path(sys.argv[1])
cells = {}
for path in sorted(root.glob("cycle*-expert*-device*.jsonl")):
    result = json.loads(path.read_text().splitlines()[-1])
    label = path.stem
    fields = label.split("-")
    cycle = int(fields[0].removeprefix("cycle"))
    expert = int(fields[1].removeprefix("expert"))
    device = int(fields[2].removeprefix("device"))
    cells[label] = {
        "cycle": cycle,
        "expert_partition": expert,
        "physical_device": device,
        "median_us": result["timing_median_us"],
        "batches_us": result["timing_us_per_invoke"],
        "output_sha256": result["output_sha256_first"],
    }

groups = {}
for name, expert, device in (
    ("interaction_p1_d1", 1, 1),
    ("partition_control_p1_d0", 1, 0),
    ("device_control_p0_d1", 0, 1),
):
    values = [
        cell["median_us"]
        for cell in cells.values()
        if cell["expert_partition"] == expert and cell["physical_device"] == device
    ]
    groups[name] = {
        "values_us": values,
        "median_us": statistics.median(values),
        "minimum_us": min(values),
        "maximum_us": max(values),
    }

interaction = groups["interaction_p1_d1"]["values_us"]
pcontrol = groups["partition_control_p1_d0"]["values_us"]
dcontrol = groups["device_control_p0_d1"]["values_us"]
penalties = [
    100.0 * (interaction[index] / max(pcontrol[index], dcontrol[index]) - 1.0)
    for index in range(4)
]
hashes_by_partition = {}
for expert in (0, 1):
    hashes_by_partition[str(expert)] = sorted(
        {
            cell["output_sha256"]
            for cell in cells.values()
            if cell["expert_partition"] == expert
        }
    )
if any(len(hashes) != 1 for hashes in hashes_by_partition.values()):
    raise SystemExit(f"cross-cell partition output parity failed: {hashes_by_partition}")
summary = {
    "schema_version": 1,
    "status": "complete",
    "cells": cells,
    "groups": groups,
    "interaction_penalty_percent_by_cycle": penalties,
    "interaction_penalty_median_percent": statistics.median(penalties),
    "cycles_above_five_percent": sum(value > 5.0 for value in penalties),
    "output_hashes_by_partition": hashes_by_partition,
    "cross_cell_partition_output_parity": True,
    "stable_interaction_gate": {
        "rule": "p1/d1 exceeds the slower matched control by >5% in at least 3/4 cycles",
        "passed": sum(value > 5.0 for value in penalties) >= 3,
    },
}
(root / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
PY

(cd "$result" && find . -maxdepth 1 -type f ! -name SHA256SUMS -printf '%P\0' | sort -z | xargs -0 sha256sum >SHA256SUMS)
(cd "$result" && sha256sum -c SHA256SUMS) >/dev/null || fail "evidence manifest failed"
printf 'PASS: evidence=%s manifest=%s\n' "$result" "$(digest "${result}/SHA256SUMS")"
