#!/usr/bin/env python3
"""Pair F.linear and Xe2 grouped GEMM within one XPU process."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import secrets
import statistics

import torch
import torch.nn.functional as F


CORE_SHA256 = "8b0486685e4167a3d9b4970d40635dd75b031792ef27ade71e27a5ae285af3b0"
PAIR_DRIVER_SHA256 = "650efd1e807845f9125150a7390b5c7cf6222d18a136e68d7d2c83f17d8008e7"
EXPECTED_STAGE = Path(
    "/mnt/usb-models/qwen38-build/hc-grouped-stage-eeee7d6-sycl8/vllm_xpu_kernels"
)
EXPECTED_MANIFEST_SHA256 = (
    "71e263f19ccc1313bbdc21604b4de5171891454fb7e8e35877af083505522951"
)
EXPECTED_RUNTIME_MANIFEST = {
    "_xpu_C.abi3.so": "07cba22dbfef80914784767a556320df87215b2ebc1226716da9d775a3c66dc3",
    "libgrouped_gemm_xe_2.so": (
        "4493c3030b1a53b756953c15e390b740023ee68f16ca8783cb0a5213600f1ac8"
    ),
}
EXPECTED_AUTHORITIES = {
    0: "225c696ac86d169e2e76f0feaa3426f5a1c007bc46b1523c86973eb68db53a8b",
    47: "01559c05e24107d635e6282eed7def49fcf32a2ff63478592bd67ba45df66100",
}
EVIDENCE_BASE = Path("/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70")
LOCK_PATHS = (
    Path("/tmp/q38-hc-m1-grouped-gemm-alternating.lock"),
    Path("/tmp/q38-hc-m1-grouped-gemm-pair.lock"),
    Path("/tmp/q38-hc-m1-grouped-gemm.lock"),
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def import_local(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import frozen helper: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[round((len(ordered) - 1) * fraction)]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-stage", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--model-revision", required=True)
    parser.add_argument("--repeat", choices=("r1", "r2"), required=True)
    parser.add_argument("--layer", type=int, choices=(0, 47), required=True)
    parser.add_argument("--seed", type=int, default=20260830)
    parser.add_argument("--warmups", type=int, default=100)
    parser.add_argument("--cycles", type=int, default=31)
    parser.add_argument("--iterations-per-cycle", type=int, default=100)
    parser.add_argument("--hash-repeats", type=int, default=100)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    frozen_protocol = {
        "seed": 20260830,
        "warmups": 100,
        "cycles": 31,
        "iterations_per_cycle": 100,
        "hash_repeats": 100,
    }
    actual_protocol = {
        "seed": args.seed,
        "warmups": args.warmups,
        "cycles": args.cycles,
        "iterations_per_cycle": args.iterations_per_cycle,
        "hash_repeats": args.hash_repeats,
    }
    if actual_protocol != frozen_protocol:
        raise RuntimeError(f"alternating protocol drift: {actual_protocol}")

    script = Path(__file__).resolve()
    script_sha256 = sha256(script)
    core_path = script.with_name("benchmark-hc-m1-grouped-gemm.py")
    pair_driver_path = script.with_name("run-hc-m1-grouped-gemm-pair.py")
    if sha256(core_path) != CORE_SHA256:
        raise RuntimeError("frozen HC component helper has drifted")
    if sha256(pair_driver_path) != PAIR_DRIVER_SHA256:
        raise RuntimeError("frozen HC pair driver has drifted")
    core = import_local(core_path, "q38_hc_grouped_core")
    pair_driver = import_local(pair_driver_path, "q38_hc_grouped_pair_driver")
    if args.model_revision != core.EXPECTED_MODEL_REVISION:
        raise RuntimeError("model revision does not match the frozen component lane")
    if os.environ.get("ONEAPI_DEVICE_SELECTOR") != "level_zero:0":
        raise RuntimeError("ONEAPI_DEVICE_SELECTOR must be exactly level_zero:0")
    if (
        os.environ.get("PYTHONNOUSERSITE") != "1"
        or os.environ.get("PYTHONSAFEPATH") != "1"
    ):
        raise RuntimeError("isolated Python environment is required")
    output_path = args.output.resolve()
    expected_output_path = (
        EVIDENCE_BASE
        / f"hc-m1-grouped-up-alternating-{args.repeat}-seed20260830"
        / f"layer-{args.layer}-up.json"
    ).resolve()
    if output_path != expected_output_path:
        raise RuntimeError(f"unexpected evidence path: {output_path}")
    if output_path.exists():
        raise RuntimeError(f"refusing to overwrite evidence: {output_path}")
    stat_tail = Path("/proc/self/stat").read_text(encoding="utf-8").rpartition(") ")[2]
    process_identity = {
        "repeat": args.repeat,
        "boot_id": Path("/proc/sys/kernel/random/boot_id")
        .read_text(encoding="utf-8")
        .strip(),
        "pid": os.getpid(),
        "process_start_ticks": int(stat_tail.split()[19]),
        "nonce": secrets.token_hex(32),
    }

    locks = []
    for lock_path in LOCK_PATHS:
        lock = lock_path.open("w", encoding="utf-8")
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError(f"component lock is held: {lock_path}") from error
        locks.append(lock)
    core.refuse_active_server()
    stage = args.runtime_stage.resolve()
    if stage != EXPECTED_STAGE.resolve():
        raise RuntimeError(f"unexpected runtime stage: {stage}")
    library, runtime_manifest = core.verify_runtime_stage(stage)
    if runtime_manifest != EXPECTED_RUNTIME_MANIFEST:
        raise RuntimeError(f"runtime manifest entries drifted: {runtime_manifest}")
    manifest_path = stage / "SHA256SUMS"
    manifest_sha256 = core.file_sha256(manifest_path)
    if manifest_sha256 != EXPECTED_MANIFEST_SHA256:
        raise RuntimeError(f"runtime manifest digest drift: {manifest_sha256}")
    loader_closure, sycl_identity = pair_driver.verify_loader_closure(
        stage, os.environ.copy(), runtime_manifest
    )
    runpath_evidence = pair_driver.verify_runpaths(stage, runtime_manifest)
    library_sha256 = core.file_sha256(library)
    core.load_extension(library)
    if not hasattr(torch.ops._xpu_C, "cutlass_grouped_gemm_interface"):
        raise RuntimeError("runtime extension lacks grouped GEMM")
    if not torch.xpu.is_available() or torch.xpu.device_count() != 1:
        raise RuntimeError("selector must expose exactly one XPU")
    device_name = torch.xpu.get_device_name(0)
    if "Arc(TM) Pro B70" not in device_name and "Arc Pro B70" not in device_name:
        raise RuntimeError(f"selected XPU is not an Arc Pro B70: {device_name}")

    model = args.model.resolve()
    index_path = model / "model.safetensors.index.json"
    config_path = model / "config.json"
    index_sha256 = core.file_sha256(index_path)
    config_sha256 = core.file_sha256(config_path)
    if index_sha256 != core.EXPECTED_MODEL_INDEX_SHA256:
        raise RuntimeError("model index digest drift")
    if config_sha256 != core.EXPECTED_CONFIG_SHA256:
        raise RuntimeError("model config digest drift")
    linear_cpu, logical_linear, shard, names = core.load_weight(
        model, args.layer, "up", "linear"
    )
    grouped_cpu, logical_grouped, grouped_shard, grouped_names = core.load_weight(
        model, args.layer, "up", "grouped"
    )
    if shard != grouped_shard or names != grouped_names:
        raise RuntimeError("provider checkpoint identity mismatch")
    shard_sha256 = core.file_sha256(shard)
    if shard_sha256 != core.EXPECTED_SHARD_SHA256.get(shard.name):
        raise RuntimeError("model shard digest drift")
    if core.tensor_sha256(logical_linear) != core.tensor_sha256(logical_grouped):
        raise RuntimeError("provider logical weights differ")
    if linear_cpu.shape != (10240, 320) or grouped_cpu.shape != (10240, 320):
        raise RuntimeError("unexpected up-projection physical shape")

    generator = torch.Generator(device="cpu").manual_seed(args.seed)
    x_cpu = torch.randn((1, 320), dtype=torch.bfloat16, generator=generator) * 0.01
    x = x_cpu.to("xpu")
    linear_weight = linear_cpu.to("xpu")
    grouped_weight = grouped_cpu.to("xpu")
    packed = grouped_weight.t().contiguous().unsqueeze(0)
    grouped_output = torch.empty((1, 10240), dtype=torch.bfloat16, device="xpu")
    rows_per_expert = torch.ones((1,), dtype=torch.int32, device="xpu")
    input_sha256 = core.tensor_sha256(x_cpu)
    linear_weight_sha256 = core.tensor_sha256(linear_cpu)
    grouped_weight_sha256 = core.tensor_sha256(grouped_cpu)
    packed_sha256 = core.tensor_sha256(packed)
    rows_per_expert_sha256 = core.tensor_sha256(rows_per_expert)

    def linear() -> torch.Tensor:
        return F.linear(x, linear_weight)

    def grouped() -> torch.Tensor:
        torch.ops._xpu_C.cutlass_grouped_gemm_interface(
            x,
            packed,
            None,
            None,
            grouped_output,
            rows_per_expert,
            10240,
            320,
            1,
            False,
            False,
        )
        return grouped_output

    def validated_output(output: torch.Tensor, label: str) -> str:
        value = output.detach().cpu()
        if value.shape != (1, 10240) or value.dtype != torch.bfloat16:
            raise RuntimeError(
                f"{label} returned unexpected shape/dtype: {value.shape} {value.dtype}"
            )
        if not torch.isfinite(value.float()).all().item():
            raise RuntimeError(f"{label} returned non-finite output")
        return core.tensor_sha256(value)

    def verify_device_state(label: str) -> None:
        if core.tensor_sha256(x) != input_sha256:
            raise RuntimeError(f"input changed {label}")
        if core.tensor_sha256(linear_weight) != linear_weight_sha256:
            raise RuntimeError(f"linear weight changed {label}")
        if core.tensor_sha256(grouped_weight) != grouped_weight_sha256:
            raise RuntimeError(f"grouped weight changed {label}")
        if core.tensor_sha256(packed) != packed_sha256:
            raise RuntimeError(f"packed weight changed {label}")
        if core.tensor_sha256(rows_per_expert) != rows_per_expert_sha256:
            raise RuntimeError(f"row metadata changed {label}")

    # Freeze the production authority before the first candidate invocation.
    linear_output = linear()
    torch.xpu.synchronize()
    authority_sha256 = validated_output(linear_output, "pre-candidate linear")
    if authority_sha256 != EXPECTED_AUTHORITIES[args.layer]:
        raise RuntimeError(f"pre-candidate authority drift: {authority_sha256}")
    verify_device_state("before first candidate")
    grouped_result = grouped()
    torch.xpu.synchronize()
    if validated_output(grouped_result, "first grouped") != authority_sha256:
        raise RuntimeError("first grouped output does not match production authority")
    verify_device_state("after first candidate")
    for index in range(args.warmups):
        if index % 2 == 0:
            linear_output = linear()
            grouped_result = grouped()
        else:
            grouped_result = grouped()
            linear_output = linear()
    torch.xpu.synchronize()
    verify_device_state("after warmup")
    linear_output = linear()
    grouped_result = grouped()
    torch.xpu.synchronize()
    if validated_output(linear_output, "post-warmup linear") != authority_sha256:
        raise RuntimeError("post-warmup linear output changed from authority")
    if validated_output(grouped_result, "post-warmup grouped") != authority_sha256:
        raise RuntimeError("post-warmup grouped output changed from authority")

    def timed(invoke) -> tuple[float, torch.Tensor]:
        start = torch.xpu.Event(enable_timing=True)
        end = torch.xpu.Event(enable_timing=True)
        start.record()
        result = None
        for _ in range(args.iterations_per_cycle):
            result = invoke()
        end.record()
        end.synchronize()
        assert result is not None
        elapsed_us = start.elapsed_time(end) * 1000.0 / args.iterations_per_cycle
        if not math.isfinite(elapsed_us) or elapsed_us <= 0.0:
            raise RuntimeError(f"invalid component timing: {elapsed_us}")
        return elapsed_us, result

    cycles: list[dict[str, object]] = []
    output_hashes: set[str] = {authority_sha256}
    for cycle in range(args.cycles):
        if cycle % 2 == 0:
            order = "linear_grouped"
            linear_us, linear_output = timed(linear)
            grouped_us, grouped_result = timed(grouped)
        else:
            order = "grouped_linear"
            grouped_us, grouped_result = timed(grouped)
            linear_us, linear_output = timed(linear)
        linear_hash = validated_output(linear_output, f"cycle {cycle} linear")
        grouped_hash = validated_output(grouped_result, f"cycle {cycle} grouped")
        if linear_hash != authority_sha256 or grouped_hash != authority_sha256:
            raise RuntimeError(f"cycle {cycle} output does not match authority")
        output_hashes.add(linear_hash)
        cycles.append(
            {
                "cycle": cycle,
                "order": order,
                "linear_us": linear_us,
                "grouped_us": grouped_us,
                "latency_reduction_percent": (1.0 - grouped_us / linear_us) * 100.0,
                "output_sha256": linear_hash,
            }
        )

    for repeat in range(args.hash_repeats):
        if repeat % 2 == 0:
            linear_output = linear()
            grouped_result = grouped()
        else:
            grouped_result = grouped()
            linear_output = linear()
        torch.xpu.synchronize()
        linear_hash = validated_output(linear_output, f"repeat {repeat} linear")
        grouped_hash = validated_output(grouped_result, f"repeat {repeat} grouped")
        if linear_hash != authority_sha256 or grouped_hash != authority_sha256:
            raise RuntimeError(f"hash repeat {repeat} does not match authority")
        output_hashes.add(linear_hash)
    if len(output_hashes) != 1:
        raise RuntimeError(f"alternating outputs were not repeatable: {output_hashes}")
    verify_device_state("after all candidate calls")

    reductions = [float(cycle["latency_reduction_percent"]) for cycle in cycles]
    linear_times = [float(cycle["linear_us"]) for cycle in cycles]
    grouped_times = [float(cycle["grouped_us"]) for cycle in cycles]
    linear_first = [
        float(cycle["latency_reduction_percent"])
        for cycle in cycles
        if cycle["order"] == "linear_grouped"
    ]
    grouped_first = [
        float(cycle["latency_reduction_percent"])
        for cycle in cycles
        if cycle["order"] == "grouped_linear"
    ]
    order_bias_points = abs(
        statistics.median(linear_first) - statistics.median(grouped_first)
    )
    median_reduction = statistics.median(reductions)
    minimum_reduction = min(reductions)
    passed = (
        median_reduction >= 50.0
        and minimum_reduction >= 20.0
        and order_bias_points <= 10.0
    )
    result = {
        "schema_version": 1,
        "status": "alternating_gate_passed" if passed else "alternating_gate_failed",
        "classification": "same_process_hot_weight_component_discriminator",
        "model": str(model),
        "model_revision": args.model_revision,
        "model_index_sha256": index_sha256,
        "model_config_sha256": config_sha256,
        "model_shard": shard.name,
        "model_shard_sha256": shard_sha256,
        "layer": args.layer,
        "projection": "up",
        "repeat": args.repeat,
        "evidence_path": str(output_path),
        "process_identity": process_identity,
        "seed": args.seed,
        "input_sha256": input_sha256,
        "logical_weight_sha256": core.tensor_sha256(logical_linear),
        "physical_weight_sha256": core.tensor_sha256(linear_cpu),
        "shape": {"m": 1, "n": 10240, "k": 320},
        "dtypes": {
            "input": str(x.dtype),
            "weight": str(linear_weight.dtype),
            "output": "torch.bfloat16",
        },
        "layouts": {
            "input": list(x.shape),
            "weight_nk": list(linear_weight.shape),
            "packed_ekn": list(packed.shape),
            "output": [1, 10240],
        },
        "device": {
            "selector": os.environ["ONEAPI_DEVICE_SELECTOR"],
            "count": torch.xpu.device_count(),
            "name": device_name,
            "torch": torch.__version__,
        },
        "runtime_stage": str(stage),
        "runtime_manifest": runtime_manifest,
        "runtime_manifest_sha256": manifest_sha256,
        "library_sha256": library_sha256,
        "sycl_identity": sycl_identity,
        "loader_closure": loader_closure.splitlines(),
        "runpath_evidence": runpath_evidence,
        "tool_sha256": script_sha256,
        "core_sha256": sha256(core_path),
        "pair_driver_sha256": sha256(pair_driver_path),
        "repeats": {
            "warmups": args.warmups,
            "cycles": args.cycles,
            "iterations_per_cycle": args.iterations_per_cycle,
            "hash": args.hash_repeats,
        },
        "unique_output_sha256": len(output_hashes),
        "output_sha256_values": sorted(output_hashes),
        "pre_candidate_authority_sha256": authority_sha256,
        "all_outputs_finite": True,
        "linear_us": {
            "median": statistics.median(linear_times),
            "p10": percentile(linear_times, 0.10),
            "p90": percentile(linear_times, 0.90),
        },
        "grouped_us": {
            "median": statistics.median(grouped_times),
            "p10": percentile(grouped_times, 0.10),
            "p90": percentile(grouped_times, 0.90),
        },
        "latency_reduction_percent": {
            "median": median_reduction,
            "minimum": minimum_reduction,
            "p10": percentile(reductions, 0.10),
            "p90": percentile(reductions, 0.90),
        },
        "order_bias_points": order_bias_points,
        "gate": {
            "median_reduction_minimum_percent": 50.0,
            "every_cycle_reduction_minimum_percent": 20.0,
            "order_bias_maximum_points": 10.0,
            "passed": passed,
        },
        "cycles": cycles,
        "alternating_process_gate_passed": passed,
        "round_robin_component_screen_authorized": False,
        "endpoint_claim_authorized": False,
    }
    if sha256(script) != script_sha256:
        raise RuntimeError("alternating tool changed during execution")
    if (
        sha256(core_path) != CORE_SHA256
        or sha256(pair_driver_path) != PAIR_DRIVER_SHA256
    ):
        raise RuntimeError("frozen helper changed during execution")
    if core.file_sha256(manifest_path) != manifest_sha256:
        raise RuntimeError("runtime manifest changed during execution")
    final_library, final_runtime_manifest = core.verify_runtime_stage(stage)
    if final_library != library or final_runtime_manifest != runtime_manifest:
        raise RuntimeError("runtime stage identity changed during execution")
    if core.file_sha256(final_library) != library_sha256:
        raise RuntimeError("loaded extension file changed during execution")
    final_loader_closure, final_sycl_identity = pair_driver.verify_loader_closure(
        stage, os.environ.copy(), final_runtime_manifest
    )
    final_runpath_evidence = pair_driver.verify_runpaths(stage, final_runtime_manifest)
    if final_sycl_identity != sycl_identity:
        raise RuntimeError("SYCL provider changed during execution")
    if final_runpath_evidence != runpath_evidence:
        raise RuntimeError("runtime RUNPATH evidence changed during execution")
    if not final_loader_closure or not loader_closure:
        raise RuntimeError("runtime loader closure is empty")
    if core.file_sha256(index_path) != index_sha256:
        raise RuntimeError("model index changed during execution")
    if core.file_sha256(config_path) != config_sha256:
        raise RuntimeError("model config changed during execution")
    if core.file_sha256(shard) != shard_sha256:
        raise RuntimeError("model shard changed during execution")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, sort_keys=True)
        handle.write("\n")
    print(json.dumps(result, sort_keys=True))
    if not passed:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
