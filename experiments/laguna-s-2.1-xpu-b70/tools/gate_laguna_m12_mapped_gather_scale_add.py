#!/usr/bin/env python3
"""Exact one-B70 gate for the default-unused Laguna M12 mapped MoE tail."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
from statistics import median


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def tensor_sha256(tensor, torch) -> str:
    value = tensor.detach().contiguous().cpu()
    if value.dtype == torch.bfloat16:
        value = value.view(torch.uint16)
    return hashlib.sha256(value.numpy().tobytes()).hexdigest()


def make_cpu_corpus(seed: int, remote_stride: int | None, torch) -> dict:
    generator = torch.Generator(device="cpu").manual_seed(seed)
    routes = (torch.randn((120, 3072), generator=generator) * 0.20).to(torch.bfloat16)
    shared = (torch.randn((12, 3072), generator=generator) * 0.10).to(torch.bfloat16)
    weights = torch.sigmoid(torch.randn((12, 10), generator=generator)).to(
        torch.float32
    )
    route_map = torch.randperm(120, generator=generator, dtype=torch.int64).to(
        torch.int32
    )
    if remote_stride is not None:
        route_map[::remote_stride] = -1
    return {
        "routes": routes,
        "shared": shared,
        "weights": weights,
        "route_map": route_map.view(12, 10),
    }


def input_hashes(item: dict, torch) -> dict[str, str]:
    return {name: tensor_sha256(value, torch) for name, value in item.items()}


def run_control(item: dict, routed, output, torch) -> None:
    torch.ops._moe_C.moe_gather(
        routed, item["routes"], item["weights"], item["route_map"], 64
    )
    torch.ops._C.laguna_m12_scale_add(output, item["shared"], routed)


def run_candidate(item: dict, output, torch) -> None:
    torch.ops._moe_C.laguna_m12_mapped_gather_scale_add(
        output,
        item["routes"],
        item["weights"],
        item["route_map"],
        item["shared"],
        64,
    )


def timed_ms(call, launches: int, torch) -> float:
    start = torch.xpu.Event(enable_timing=True)
    end = torch.xpu.Event(enable_timing=True)
    start.record()
    for _ in range(launches):
        call()
    end.record()
    end.synchronize()
    return float(start.elapsed_time(end)) / launches


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-package", required=True)
    parser.add_argument("--expected-moe-sha256", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--warmups", type=int, default=200)
    parser.add_argument("--samples", type=int, default=15)
    parser.add_argument("--launches", type=int, default=40)
    parser.add_argument("--speedup-threshold", type=float, default=1.10)
    parser.add_argument("--cycle-saving-threshold-ms", type=float, default=0.30)
    args = parser.parse_args()
    if min(args.warmups, args.samples, args.launches) <= 0:
        parser.error("warmups, samples, and launches must be positive")
    return args


def main() -> int:
    args = parse_args()
    package = Path(args.candidate_package).resolve()
    output_path = Path(args.output).resolve()
    if output_path.exists():
        raise RuntimeError(f"refusing existing output: {output_path}")
    if Path(os.environ.get("PYTHONPATH", "").split(":", 1)[0]).resolve() != package:
        raise RuntimeError("candidate package is not first on PYTHONPATH")

    import torch

    loaded: dict[str, dict[str, str]] = {}
    for name in ("vllm_xpu_kernels._C", "vllm_xpu_kernels._moe_C"):
        module = importlib.import_module(name)
        path = Path(module.__file__).resolve()
        loaded[name] = {"path": str(path), "sha256": sha256_file(path)}
    if loaded["vllm_xpu_kernels._moe_C"]["sha256"] != args.expected_moe_sha256:
        raise RuntimeError("loaded candidate _moe_C hash drift")
    if not hasattr(torch.ops._moe_C, "laguna_m12_mapped_gather_scale_add"):
        raise RuntimeError("candidate op is absent")
    if not hasattr(torch.ops._C, "laguna_m12_scale_add"):
        raise RuntimeError("control scale/add op is absent")
    if torch.xpu.device_count() != 1:
        raise RuntimeError("exactly one re-indexed XPU is required")

    cpu_corpus = [
        make_cpu_corpus(0x12A0, None, torch),
        make_cpu_corpus(0x12A1, 4, torch),
        make_cpu_corpus(0x12A2, 3, torch),
    ]
    corpus = [
        {name: value.to("xpu") for name, value in item.items()} for item in cpu_corpus
    ]
    buffers = {
        "routed": torch.empty((12, 3072), dtype=torch.bfloat16, device="xpu"),
        "control": torch.empty((12, 3072), dtype=torch.bfloat16, device="xpu"),
        "candidate": torch.empty((12, 3072), dtype=torch.bfloat16, device="xpu"),
    }
    hashes_before = [input_hashes(item, torch) for item in corpus]

    comparisons: list[dict] = []
    for epoch, item in enumerate(corpus):
        run_control(item, buffers["routed"], buffers["control"], torch)
        run_candidate(item, buffers["candidate"], torch)
        torch.xpu.synchronize()
        control_hash = tensor_sha256(buffers["control"], torch)
        candidate_hash = tensor_sha256(buffers["candidate"], torch)
        comparisons.append(
            {
                "epoch": epoch,
                "phase": "pre_timing",
                "control_sha256": control_hash,
                "candidate_sha256": candidate_hash,
                "raw_bf16_equal": control_hash == candidate_hash,
            }
        )

    timing_item = corpus[1]

    def control_call() -> None:
        run_control(timing_item, buffers["routed"], buffers["control"], torch)

    def candidate_call() -> None:
        run_candidate(timing_item, buffers["candidate"], torch)

    for _ in range(args.warmups):
        control_call()
        candidate_call()
    torch.xpu.synchronize()

    control_samples: list[float] = []
    candidate_samples: list[float] = []
    for sample in range(args.samples):
        order = (
            ("control", "candidate")
            if sample % 2 == 0
            else (
                "candidate",
                "control",
            )
        )
        for arm in order:
            value = timed_ms(
                control_call if arm == "control" else candidate_call,
                args.launches,
                torch,
            )
            (control_samples if arm == "control" else candidate_samples).append(value)

    for epoch, item in enumerate(corpus):
        run_control(item, buffers["routed"], buffers["control"], torch)
        run_candidate(item, buffers["candidate"], torch)
        torch.xpu.synchronize()
        control_hash = tensor_sha256(buffers["control"], torch)
        candidate_hash = tensor_sha256(buffers["candidate"], torch)
        comparisons.append(
            {
                "epoch": epoch,
                "phase": "post_timing",
                "control_sha256": control_hash,
                "candidate_sha256": candidate_hash,
                "raw_bf16_equal": control_hash == candidate_hash,
            }
        )

    hashes_after = [input_hashes(item, torch) for item in corpus]
    control_ms = median(control_samples)
    candidate_ms = median(candidate_samples)
    speedup = control_ms / candidate_ms
    cycle_saving_ms = (control_ms - candidate_ms) * 48
    exact = sum(item["raw_bf16_equal"] for item in comparisons)
    result = {
        "status": (
            "pass"
            if exact == len(comparisons)
            and hashes_before == hashes_after
            and speedup >= args.speedup_threshold
            and cycle_saving_ms >= args.cycle_saving_threshold_ms
            else "stop"
        ),
        "device": str(torch.xpu.get_device_properties(0).name),
        "ze_affinity_mask": os.environ.get("ZE_AFFINITY_MASK"),
        "loaded": loaded,
        "protocol": {
            "warmups_per_arm": args.warmups,
            "samples_per_arm": args.samples,
            "launches_per_sample": args.launches,
            "alternating_order": True,
        },
        "exact": exact,
        "total": len(comparisons),
        "inputs_immutable": hashes_before == hashes_after,
        "comparisons": comparisons,
        "control_samples_ms": control_samples,
        "candidate_samples_ms": candidate_samples,
        "control_median_ms": control_ms,
        "candidate_median_ms": candidate_ms,
        "speedup": speedup,
        "extrapolated_48_layer_saving_ms": cycle_saving_ms,
        "speedup_threshold": args.speedup_threshold,
        "cycle_saving_threshold_ms": args.cycle_saving_threshold_ms,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2) + "\n")
    print(
        f"PROBE_RESULT={'PASS' if exact == len(comparisons) else 'FAIL'} exact={exact}/{len(comparisons)}"
    )
    print(
        f"control_ms={control_ms:.9f} candidate_ms={candidate_ms:.9f} "
        f"speedup={speedup:.6f} cycle_saving_ms={cycle_saving_ms:.6f} "
        f"PERFORMANCE_GATE={'PASS' if result['status'] == 'pass' else 'STOP'}"
    )
    return 0 if exact == len(comparisons) and hashes_before == hashes_after else 1


if __name__ == "__main__":
    raise SystemExit(main())
