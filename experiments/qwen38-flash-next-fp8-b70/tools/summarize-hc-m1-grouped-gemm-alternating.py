#!/usr/bin/env python3
"""Apply the frozen four-process HC alternating family gate."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import statistics


BASE = Path("/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70")
OUTPUT = BASE / "hc-m1-grouped-up-alternating-summary-seed20260830.json"
RUN_TOOL = Path(__file__).with_name("benchmark-hc-m1-grouped-gemm-alternating.py")
CORE_TOOL = Path(__file__).with_name("benchmark-hc-m1-grouped-gemm.py")
PAIR_DRIVER = Path(__file__).with_name("run-hc-m1-grouped-gemm-pair.py")
EXPECTED_TOOL_SHA256 = (
    "53f3991db81942bdca4a7562a385554e109c9c207d9086a8a946bd514c081d9c"
)
EXPECTED_CORE_SHA256 = (
    "8b0486685e4167a3d9b4970d40635dd75b031792ef27ade71e27a5ae285af3b0"
)
EXPECTED_PAIR_DRIVER_SHA256 = (
    "650efd1e807845f9125150a7390b5c7cf6222d18a136e68d7d2c83f17d8008e7"
)
EXPECTED_MODEL_REVISION = "bcd9f01ddc9cff2316eb84281bebcd5b058bddce"
EXPECTED_MODEL = "/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8"
EXPECTED_INDEX_SHA256 = (
    "0419e2c2dfbb925257d7409405433a793cf7ff7d96f3eba882a815ec6d9fe7a6"
)
EXPECTED_CONFIG_SHA256 = (
    "99c11efba4012d0f760f4e4831a8d6cafd845044e21d0aa9e6d9e70a15a90a8d"
)
EXPECTED_SHARDS = {
    0: (
        "model-00001-of-00131.safetensors",
        "774f0ceeadb40d165f2b3ff397d5f3840e6ca8fcb8f3d39d8acb4fea9e52c941",
    ),
    47: (
        "model-00118-of-00131.safetensors",
        "2d06ec9c1726f42bfc9ce0bbb47129917d8ab373c88eed4e758fb6940c92ad4a",
    ),
}
EXPECTED_STAGE = (
    "/mnt/usb-models/qwen38-build/hc-grouped-stage-eeee7d6-sycl8/vllm_xpu_kernels"
)
EXPECTED_MANIFEST_SHA256 = (
    "71e263f19ccc1313bbdc21604b4de5171891454fb7e8e35877af083505522951"
)
EXPECTED_LIBRARY_SHA256 = (
    "07cba22dbfef80914784767a556320df87215b2ebc1226716da9d775a3c66dc3"
)
EXPECTED_RUNTIME_MANIFEST = {
    "_xpu_C.abi3.so": EXPECTED_LIBRARY_SHA256,
    "libgrouped_gemm_xe_2.so": (
        "4493c3030b1a53b756953c15e390b740023ee68f16ca8783cb0a5213600f1ac8"
    ),
}
EXPECTED_SYCL_SHA256 = (
    "0336997fdfed9b2e6385e9f1cea2395eb5e130d3e5e9c943df5b0c10c1b5e57f"
)
EXPECTED_INPUT_SHA256 = (
    "e12c95b046be6035f345773172bf05c64207c30c0ca455b24e08aae31b6141d8"
)
EXPECTED_WEIGHTS = {
    0: "6e87eb16e95e4e24cb83f3852d4200bdff7da87d8e8989022fe8012b88c2f978",
    47: "b910a9626f2a671a614e42eb0c4ad6c6a6c62ad6b787693ff127d564303062ae",
}
EXPECTED_AUTHORITIES = {
    0: "225c696ac86d169e2e76f0feaa3426f5a1c007bc46b1523c86973eb68db53a8b",
    47: "01559c05e24107d635e6282eed7def49fcf32a2ff63478592bd67ba45df66100",
}
EXPECTED_REPEATS = {
    "warmups": 100,
    "cycles": 31,
    "iterations_per_cycle": 100,
    "hash": 100,
}
EXPECTED_GATE = {
    "median_reduction_minimum_percent": 50.0,
    "every_cycle_reduction_minimum_percent": 20.0,
    "order_bias_maximum_points": 10.0,
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def close(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=1e-12, abs_tol=1e-12)


def validate_run(path: Path, repeat: str, layer: int) -> dict[str, object]:
    raw_bytes = path.read_bytes()
    raw = json.loads(raw_bytes)
    expected = {
        "schema_version": 1,
        "classification": "same_process_hot_weight_component_discriminator",
        "model": EXPECTED_MODEL,
        "model_revision": EXPECTED_MODEL_REVISION,
        "model_index_sha256": EXPECTED_INDEX_SHA256,
        "model_config_sha256": EXPECTED_CONFIG_SHA256,
        "model_shard": EXPECTED_SHARDS[layer][0],
        "model_shard_sha256": EXPECTED_SHARDS[layer][1],
        "layer": layer,
        "projection": "up",
        "repeat": repeat,
        "evidence_path": str(path),
        "seed": 20260830,
        "input_sha256": EXPECTED_INPUT_SHA256,
        "logical_weight_sha256": EXPECTED_WEIGHTS[layer],
        "physical_weight_sha256": EXPECTED_WEIGHTS[layer],
        "shape": {"m": 1, "n": 10240, "k": 320},
        "dtypes": {
            "input": "torch.bfloat16",
            "weight": "torch.bfloat16",
            "output": "torch.bfloat16",
        },
        "layouts": {
            "input": [1, 320],
            "weight_nk": [10240, 320],
            "packed_ekn": [1, 320, 10240],
            "output": [1, 10240],
        },
        "runtime_stage": EXPECTED_STAGE,
        "runtime_manifest": EXPECTED_RUNTIME_MANIFEST,
        "runtime_manifest_sha256": EXPECTED_MANIFEST_SHA256,
        "library_sha256": EXPECTED_LIBRARY_SHA256,
        "tool_sha256": EXPECTED_TOOL_SHA256,
        "core_sha256": EXPECTED_CORE_SHA256,
        "pair_driver_sha256": EXPECTED_PAIR_DRIVER_SHA256,
        "repeats": EXPECTED_REPEATS,
        "unique_output_sha256": 1,
        "all_outputs_finite": True,
        "round_robin_component_screen_authorized": False,
        "endpoint_claim_authorized": False,
    }
    for field, value in expected.items():
        if raw.get(field) != value:
            raise RuntimeError(f"{path}: identity mismatch for {field}")
    if raw.get("sycl_identity", {}).get("sha256") != EXPECTED_SYCL_SHA256:
        raise RuntimeError(f"{path}: SYCL identity mismatch")
    device = raw.get("device", {})
    if (
        device.get("selector") != "level_zero:0"
        or device.get("count") != 1
        or "Arc" not in str(device.get("name"))
        or "B70" not in str(device.get("name"))
    ):
        raise RuntimeError(f"{path}: device identity mismatch")
    authority = raw.get("pre_candidate_authority_sha256")
    if authority != EXPECTED_AUTHORITIES[layer]:
        raise RuntimeError(f"{path}: production authority mismatch")
    process_identity = raw.get("process_identity")
    if not isinstance(process_identity, dict):
        raise RuntimeError(f"{path}: process identity missing")
    if (
        process_identity.get("repeat") != repeat
        or not isinstance(process_identity.get("boot_id"), str)
        or len(process_identity["boot_id"]) != 36
        or not isinstance(process_identity.get("pid"), int)
        or process_identity["pid"] <= 0
        or not isinstance(process_identity.get("process_start_ticks"), int)
        or process_identity["process_start_ticks"] <= 0
        or not isinstance(process_identity.get("nonce"), str)
        or len(process_identity["nonce"]) != 64
    ):
        raise RuntimeError(f"{path}: invalid process identity")
    if raw.get("output_sha256_values") != [authority]:
        raise RuntimeError(f"{path}: output does not bind the authority")
    cycles = raw.get("cycles")
    if not isinstance(cycles, list) or len(cycles) != 31:
        raise RuntimeError(f"{path}: cycle count mismatch")
    reductions: list[float] = []
    linear_first: list[float] = []
    grouped_first: list[float] = []
    for index, cycle in enumerate(cycles):
        expected_order = "linear_grouped" if index % 2 == 0 else "grouped_linear"
        if cycle.get("cycle") != index or cycle.get("order") != expected_order:
            raise RuntimeError(f"{path}: cycle order mismatch at {index}")
        if cycle.get("output_sha256") != authority:
            raise RuntimeError(f"{path}: cycle authority mismatch at {index}")
        linear_us = float(cycle["linear_us"])
        grouped_us = float(cycle["grouped_us"])
        reduction = float(cycle["latency_reduction_percent"])
        if any(
            not math.isfinite(value) or value <= 0.0
            for value in (linear_us, grouped_us)
        ):
            raise RuntimeError(f"{path}: invalid timing at cycle {index}")
        recomputed = (1.0 - grouped_us / linear_us) * 100.0
        if not close(reduction, recomputed):
            raise RuntimeError(f"{path}: reduction mismatch at cycle {index}")
        reductions.append(reduction)
        (linear_first if expected_order == "linear_grouped" else grouped_first).append(
            reduction
        )
    median_reduction = statistics.median(reductions)
    minimum_reduction = min(reductions)
    order_bias = abs(statistics.median(linear_first) - statistics.median(grouped_first))
    if not close(float(raw["latency_reduction_percent"]["median"]), median_reduction):
        raise RuntimeError(f"{path}: median reduction mismatch")
    if not close(float(raw["latency_reduction_percent"]["minimum"]), minimum_reduction):
        raise RuntimeError(f"{path}: minimum reduction mismatch")
    if not close(float(raw["order_bias_points"]), order_bias):
        raise RuntimeError(f"{path}: order-bias mismatch")
    gate = raw.get("gate")
    for field, value in EXPECTED_GATE.items():
        if gate.get(field) != value:
            raise RuntimeError(f"{path}: gate threshold drift for {field}")
    recomputed_pass = (
        median_reduction >= 50.0 and minimum_reduction >= 20.0 and order_bias <= 10.0
    )
    if gate.get("passed") is not recomputed_pass:
        raise RuntimeError(f"{path}: process gate decision mismatch")
    if raw.get("alternating_process_gate_passed") is not recomputed_pass:
        raise RuntimeError(f"{path}: process status mismatch")
    expected_status = (
        "alternating_gate_passed" if recomputed_pass else "alternating_gate_failed"
    )
    if raw.get("status") != expected_status:
        raise RuntimeError(f"{path}: status mismatch")
    return {
        "repeat": repeat,
        "layer": layer,
        "path": str(path),
        "sha256": hashlib.sha256(raw_bytes).hexdigest(),
        "process_identity": process_identity,
        "passed": recomputed_pass,
        "median_reduction_percent": median_reduction,
        "minimum_reduction_percent": minimum_reduction,
        "order_bias_points": order_bias,
        "authority_sha256": authority,
    }


def main() -> None:
    aggregate_tool = Path(__file__).resolve()
    aggregate_tool_sha256 = sha256(aggregate_tool)
    if OUTPUT.exists():
        raise RuntimeError(f"refusing to overwrite aggregate evidence: {OUTPUT}")
    expected_tools = {
        RUN_TOOL: EXPECTED_TOOL_SHA256,
        CORE_TOOL: EXPECTED_CORE_SHA256,
        PAIR_DRIVER: EXPECTED_PAIR_DRIVER_SHA256,
    }
    for path, expected in expected_tools.items():
        if sha256(path) != expected:
            raise RuntimeError(f"tool identity drift: {path}")
    runs = []
    for repeat in ("r1", "r2"):
        root = BASE / f"hc-m1-grouped-up-alternating-{repeat}-seed20260830"
        for layer in (0, 47):
            runs.append(validate_run(root / f"layer-{layer}-up.json", repeat, layer))
    process_instances = {
        (
            run["process_identity"]["boot_id"],
            run["process_identity"]["pid"],
            run["process_identity"]["process_start_ticks"],
        )
        for run in runs
    }
    if len(process_instances) != 4:
        raise RuntimeError("the four inputs do not prove four distinct processes")
    nonces = {run["process_identity"]["nonce"] for run in runs}
    if len(nonces) != 4:
        raise RuntimeError("the four inputs do not contain four distinct invocations")
    for layer in (0, 47):
        layer_authorities = {
            run["authority_sha256"] for run in runs if run["layer"] == layer
        }
        if layer_authorities != {EXPECTED_AUTHORITIES[layer]}:
            raise RuntimeError(f"layer {layer} authority differs across repeats")
    passed = all(bool(run["passed"]) for run in runs)
    result = {
        "schema_version": 1,
        "status": "family_gate_passed" if passed else "family_gate_failed",
        "classification": "four_process_alternating_component_gate",
        "runs": runs,
        "all_four_processes_passed": passed,
        "round_robin_component_screen_authorized": passed,
        "endpoint_claim_authorized": False,
        "tool_sha256": EXPECTED_TOOL_SHA256,
        "core_sha256": EXPECTED_CORE_SHA256,
        "pair_driver_sha256": EXPECTED_PAIR_DRIVER_SHA256,
        "aggregate_tool_sha256": aggregate_tool_sha256,
    }
    for path, expected in expected_tools.items():
        if sha256(path) != expected:
            raise RuntimeError(f"tool changed before aggregate write: {path}")
    if sha256(aggregate_tool) != aggregate_tool_sha256:
        raise RuntimeError("aggregate checker changed before output write")
    for run in runs:
        if sha256(Path(str(run["path"]))) != run["sha256"]:
            raise RuntimeError(f"validated evidence changed: {run['path']}")
    with OUTPUT.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, sort_keys=True)
        handle.write("\n")
    print(json.dumps(result, sort_keys=True))
    if not passed:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
