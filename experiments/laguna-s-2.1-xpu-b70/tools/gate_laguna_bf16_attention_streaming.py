#!/usr/bin/env python3
"""Stream the real Laguna target BF16 QKV/O layer weight families.

Unlike the repeated-weight component, each timed pass cycles all 48 physical
layer weights.  The roughly 0.6--0.8 GiB family working sets are intentionally
far larger than cache, matching the record's layer-to-layer weight turnover.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import time
from pathlib import Path
from typing import Callable

import torch


LAYER_TYPES = ("full", "sliding", "sliding", "sliding") * 12
QKV_SHAPES = {"full": (3072, 2048), "sliding": (3072, 2816)}
O_SHAPES = {"full": (1536, 3072), "sliding": (2304, 3072)}


def tensor_hash(tensor: torch.Tensor) -> str:
    raw = tensor.cpu().contiguous().view(torch.uint8).numpy().tobytes()
    return hashlib.sha256(raw).hexdigest()


def stride_zero_bmm(rows: torch.Tensor, weight: torch.Tensor) -> torch.Tensor:
    weight_t = weight.t().unsqueeze(0).expand(rows.shape[0], -1, -1)
    return torch.bmm(rows.unsqueeze(1), weight_t).squeeze(1)


def native_mm(rows: torch.Tensor, weight: torch.Tensor) -> torch.Tensor:
    return torch.mm(rows, weight.t())


def make_family(
    shapes: dict[str, tuple[int, int]], rows: int, seed: int
) -> list[tuple[torch.Tensor, torch.Tensor]]:
    family = []
    for layer, layer_type in enumerate(LAYER_TYPES):
        k_dim, n_dim = shapes[layer_type]
        torch.manual_seed(seed + layer)
        activations = torch.randn((rows, k_dim), dtype=torch.bfloat16, device="xpu")
        weight = torch.randn((n_dim, k_dim), dtype=torch.bfloat16, device="xpu")
        family.append((activations, weight))
    torch.xpu.synchronize()
    return family


def family_bytes(family: list[tuple[torch.Tensor, torch.Tensor]]) -> int:
    return sum(
        tensor.numel() * tensor.element_size() for pair in family for tensor in pair
    )


def run_family(
    family: list[tuple[torch.Tensor, torch.Tensor]],
    operation: Callable[[torch.Tensor, torch.Tensor], torch.Tensor],
) -> torch.Tensor:
    output = None
    for rows, weight in family:
        output = operation(rows, weight)
    assert output is not None
    return output


def timed_sample_ms(
    family: list[tuple[torch.Tensor, torch.Tensor]],
    operation: Callable[[torch.Tensor, torch.Tensor], torch.Tensor],
    passes: int,
) -> float:
    torch.xpu.synchronize()
    started = time.perf_counter()
    output = None
    for _ in range(passes):
        output = run_family(family, operation)
    torch.xpu.synchronize()
    assert output is not None
    return (time.perf_counter() - started) * 1000.0 / passes


def screen_family(
    name: str,
    family: list[tuple[torch.Tensor, torch.Tensor]],
    samples: int,
    passes: int,
) -> dict[str, object]:
    exact = 0
    hashes = []
    for layer, (rows, weight) in enumerate(family):
        control = stride_zero_bmm(rows, weight)
        candidate = native_mm(rows, weight)
        if not torch.equal(control, candidate):
            raise AssertionError(f"{name} layer {layer} is not raw-BF16 exact")
        exact += 1
        hashes.append(tensor_hash(candidate))

    # Warm both alternatives over the entire family. Each pass is still a
    # streamed-weight pass because the family exceeds cache by construction.
    run_family(family, stride_zero_bmm)
    run_family(family, native_mm)
    torch.xpu.synchronize()

    control_samples = []
    candidate_samples = []
    for sample in range(samples):
        order = (
            (stride_zero_bmm, control_samples, native_mm, candidate_samples)
            if sample % 2 == 0
            else (native_mm, candidate_samples, stride_zero_bmm, control_samples)
        )
        first_op, first_samples, second_op, second_samples = order
        first_samples.append(timed_sample_ms(family, first_op, passes))
        second_samples.append(timed_sample_ms(family, second_op, passes))

    control_median = statistics.median(control_samples)
    candidate_median = statistics.median(candidate_samples)
    return {
        "layers": len(family),
        "working_set_bytes": family_bytes(family),
        "raw_bf16_exact": f"{exact}/{len(family)}",
        "output_hash_sha256": hashlib.sha256("".join(hashes).encode()).hexdigest(),
        "passes_per_sample": passes,
        "control_ms_samples": control_samples,
        "candidate_ms_samples": candidate_samples,
        "control_median_ms": control_median,
        "candidate_median_ms": candidate_median,
        "speedup": control_median / candidate_median,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=12, choices=range(1, 17))
    parser.add_argument("--samples", type=int, default=10)
    parser.add_argument("--passes-per-sample", type=int, default=4)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.samples < 4 or args.passes_per_sample < 1:
        raise SystemExit("samples must be >=4 and passes-per-sample must be >=1")

    torch.xpu.set_device(0)
    qkv = make_family(QKV_SHAPES, args.rows, 73100)
    o_proj = make_family(O_SHAPES, args.rows, 74100)
    payload = {
        "schema": "laguna-bf16-attention-streaming-v1",
        "device": torch.xpu.get_device_name(0),
        "rows": args.rows,
        "layer_types": list(LAYER_TYPES),
        "qkv": screen_family("qkv", qkv, args.samples, args.passes_per_sample),
        "o_proj": screen_family("o_proj", o_proj, args.samples, args.passes_per_sample),
    }
    payload["passed"] = bool(
        payload["qkv"]["speedup"] > 1.0 and payload["o_proj"]["speedup"] > 1.0
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
