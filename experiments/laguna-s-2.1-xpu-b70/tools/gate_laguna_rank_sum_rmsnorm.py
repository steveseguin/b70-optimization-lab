#!/usr/bin/env python3
"""Exactness and timing gate for Laguna's TP4 sum + add-RMSNorm fusion."""

from __future__ import annotations

import argparse
import gc
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time
from typing import Any, Callable


M = 12
H = 3072
WARMUPS = 200
SAMPLES = 16
LAUNCHES = 100
MINIMUM_SAVING_MS = 0.010


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def tensor_sha256(tensor: Any) -> str:
    import torch

    raw = tensor.detach().cpu().contiguous().view(torch.uint8).numpy()
    return hashlib.sha256(raw).hexdigest()


def mapped_extensions() -> list[str]:
    paths: set[str] = set()
    for line in Path("/proc/self/maps").read_text().splitlines():
        if "_C.abi3.so" not in line:
            continue
        candidate = line.split()[-1]
        if candidate.startswith("/"):
            paths.add(str(Path(candidate).resolve()))
    return sorted(paths)


def load_candidate(candidate_so: Path) -> Any:
    name = "vllm_xpu_kernels._C"
    spec = importlib.util.spec_from_file_location(name, candidate_so)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot create import spec for {candidate_so}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def time_arm(
    launch: Callable[[], Any], residual: Any, residual_seed: Any
) -> float:
    import torch

    residual.copy_(residual_seed)
    torch.xpu.synchronize()
    start = time.perf_counter_ns()
    output = None
    for _ in range(LAUNCHES):
        output = launch()
    torch.xpu.synchronize()
    if output is None:
        raise RuntimeError("timing arm did not produce output")
    return (time.perf_counter_ns() - start) / LAUNCHES / 1_000_000.0


def main(args: argparse.Namespace) -> int:
    import torch
    import vllm_xpu_kernels._xpu_C as xpu_extension

    if torch.xpu.device_count() != 1:
        raise RuntimeError(
            f"gate requires exactly one visible XPU, got {torch.xpu.device_count()}"
        )
    if os.environ.get("ZE_AFFINITY_MASK") != str(args.rank):
        raise RuntimeError("ZE_AFFINITY_MASK drift")
    if os.environ.get("ONEAPI_DEVICE_SELECTOR") != "level_zero:0":
        raise RuntimeError("ONEAPI_DEVICE_SELECTOR drift")

    candidate_so = Path(args.candidate_so).resolve()
    candidate_tree = Path(args.candidate_tree).resolve()
    output_dir = Path(args.output_dir).resolve()
    if not candidate_so.is_file():
        raise RuntimeError(f"missing candidate DSO: {candidate_so}")
    if sha256_file(candidate_so) != args.expected_sha256:
        raise RuntimeError("candidate DSO SHA-256 drift")
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=candidate_tree,
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()
    if head != args.expected_head:
        raise RuntimeError(f"candidate source HEAD drift: {head}")
    if output_dir.exists():
        raise RuntimeError(f"refusing existing output directory: {output_dir}")
    output_dir.mkdir(parents=True)

    candidate_extension = load_candidate(candidate_so)
    if not hasattr(torch.ops._C, "laguna_tp4_bf16_sum_fused_add_rms_norm"):
        raise RuntimeError("candidate fused operator is not registered")
    mapped = mapped_extensions()
    if str(candidate_so) not in mapped:
        raise RuntimeError(f"candidate DSO is not mapped: {mapped}")
    incumbent_xpu = str(Path(xpu_extension.__file__).resolve())
    if incumbent_xpu not in mapped:
        raise RuntimeError(f"incumbent XPU extension is not mapped: {mapped}")

    exact_cases: list[dict[str, Any]] = []
    for case in range(5):
        generator = torch.Generator(device="cpu")
        generator.manual_seed(831_000 + case)
        gathered_cpu = torch.randn(
            (4, M, H), dtype=torch.bfloat16, generator=generator
        )
        residual_cpu = torch.randn(
            (M, H), dtype=torch.bfloat16, generator=generator
        )
        weight_cpu = torch.randn((H,), dtype=torch.bfloat16, generator=generator)
        identity = {
            "gathered": tensor_sha256(gathered_cpu),
            "residual": tensor_sha256(residual_cpu),
            "weight": tensor_sha256(weight_cpu),
        }
        gathered = gathered_cpu.to("xpu")
        residual_seed = residual_cpu.to("xpu")
        weight = weight_cpu.to("xpu")
        residual_control = residual_seed.clone()
        residual_candidate = residual_seed.clone()

        control = torch.ops._xpu_C.rank_order_bf16_sum(gathered)
        torch.ops._C.fused_add_rms_norm(
            control, residual_control, weight, args.epsilon
        )
        candidate = torch.ops._C.laguna_tp4_bf16_sum_fused_add_rms_norm(
            gathered, residual_candidate, weight, args.epsilon
        )
        torch.xpu.synchronize()
        output_equal = torch.equal(control, candidate)
        residual_equal = torch.equal(residual_control, residual_candidate)
        exact_cases.append(
            {
                "case": case,
                "identity": identity,
                "control_output": tensor_sha256(control),
                "candidate_output": tensor_sha256(candidate),
                "control_residual": tensor_sha256(residual_control),
                "candidate_residual": tensor_sha256(residual_candidate),
                "output_equal": output_equal,
                "residual_equal": residual_equal,
            }
        )
        if not output_equal or not residual_equal:
            raise RuntimeError(f"raw BF16 mismatch in changed-input case {case}")

    generator = torch.Generator(device="cpu")
    generator.manual_seed(832_000)
    gathered = torch.randn(
        (4, M, H), dtype=torch.bfloat16, generator=generator
    ).to("xpu")
    residual_seed = torch.randn(
        (M, H), dtype=torch.bfloat16, generator=generator
    ).to("xpu")
    weight = torch.randn((H,), dtype=torch.bfloat16, generator=generator).to("xpu")
    residual_control = residual_seed.clone()
    residual_candidate = residual_seed.clone()

    def control_launch() -> Any:
        output = torch.ops._xpu_C.rank_order_bf16_sum(gathered)
        torch.ops._C.fused_add_rms_norm(
            output, residual_control, weight, args.epsilon
        )
        return output

    def candidate_launch() -> Any:
        return torch.ops._C.laguna_tp4_bf16_sum_fused_add_rms_norm(
            gathered, residual_candidate, weight, args.epsilon
        )

    for _ in range(WARMUPS):
        control_launch()
        candidate_launch()
    torch.xpu.synchronize()
    gc.disable()
    timings: dict[str, list[float]] = {"control": [], "candidate": []}
    orders: list[list[str]] = []
    arms = {"control": control_launch, "candidate": candidate_launch}
    residuals = {"control": residual_control, "candidate": residual_candidate}
    for sample in range(SAMPLES):
        order = (
            ["control", "candidate"]
            if sample % 2 == 0
            else ["candidate", "control"]
        )
        orders.append(order)
        for name in order:
            timings[name].append(time_arm(arms[name], residuals[name], residual_seed))
    gc.enable()

    control_median = statistics.median(timings["control"])
    candidate_median = statistics.median(timings["candidate"])
    saving_ms = control_median - candidate_median
    speedup = control_median / candidate_median
    performance_passed = saving_ms >= MINIMUM_SAVING_MS
    payload = {
        "status": "pass" if performance_passed else "stop",
        "exact": len(exact_cases) * 2,
        "total": len(exact_cases) * 2,
        "exact_cases": exact_cases,
        "candidate_source_head": head,
        "candidate_so": str(candidate_so),
        "candidate_sha256": args.expected_sha256,
        "candidate_extension": str(Path(candidate_extension.__file__).resolve()),
        "incumbent_xpu_extension": incumbent_xpu,
        "mapped_extensions": mapped,
        "environment": {
            "ZE_AFFINITY_MASK": os.environ.get("ZE_AFFINITY_MASK"),
            "ONEAPI_DEVICE_SELECTOR": os.environ.get("ONEAPI_DEVICE_SELECTOR"),
        },
        "shape": {"gathered": [4, M, H], "residual": [M, H]},
        "epsilon": args.epsilon,
        "protocol": {
            "warmups_per_arm": WARMUPS,
            "samples_per_arm": SAMPLES,
            "launches_per_sample": LAUNCHES,
            "balanced_orders": orders,
        },
        "timing_ms_per_call": timings,
        "control_median_ms": control_median,
        "candidate_median_ms": candidate_median,
        "saving_ms": saving_ms,
        "speedup": speedup,
        "minimum_saving_ms": MINIMUM_SAVING_MS,
        "performance_passed": performance_passed,
    }
    (output_dir / "summary.json").write_text(json.dumps(payload, indent=2) + "\n")
    print(f"PROBE_RESULT=PASS exact={payload['exact']}/{payload['total']}")
    print(
        f"control_ms={control_median:.6f} candidate_ms={candidate_median:.6f} "
        f"saving_ms={saving_ms:.6f} speedup={speedup:.6f}"
    )
    print(f"PERFORMANCE_GATE={'PASS' if performance_passed else 'STOP'}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-so", required=True)
    parser.add_argument("--candidate-tree", required=True)
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--rank", type=int, default=1)
    parser.add_argument("--epsilon", type=float, default=1e-6)
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(main(parse_args()))
