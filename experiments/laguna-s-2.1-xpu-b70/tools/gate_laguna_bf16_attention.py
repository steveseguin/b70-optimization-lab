#!/usr/bin/env python3
"""Changing-input exactness/timing gate for Laguna BF16 attention GEMMs."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import torch


CASES = {
    "full-qkv": (3072, 2048, (1536, 256, 256)),
    "sliding-qkv": (3072, 2816, (2304, 256, 256)),
    "full-o": (1536, 3072, None),
    "sliding-o": (2304, 3072, None),
    # Logical-shape diagnostics only. Q/K/V are fused on the record path.
    "full-q-diagnostic": (3072, 1536, None),
    "sliding-q-diagnostic": (3072, 2304, None),
    "k-diagnostic": (3072, 256, None),
    "v-diagnostic": (3072, 256, None),
}


def tensor_hash(tensor: torch.Tensor) -> str:
    raw = tensor.cpu().contiguous().view(torch.uint8).numpy().tobytes()
    return hashlib.sha256(raw).hexdigest()


def record_bmm(rows: torch.Tensor, weight: torch.Tensor) -> torch.Tensor:
    weight_t = weight.t().unsqueeze(0).expand(rows.shape[0], -1, -1)
    return torch.bmm(rows.unsqueeze(1), weight_t).squeeze(1)


def candidate_mm(rows: torch.Tensor, weight: torch.Tensor) -> torch.Tensor:
    return torch.mm(rows, weight.t())


def timed_ms(call, iterations: int) -> float:
    for _ in range(5):
        call()
    torch.xpu.synchronize()
    started = time.perf_counter()
    for _ in range(iterations):
        call()
    torch.xpu.synchronize()
    return (time.perf_counter() - started) * 1000.0 / iterations


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rank", type=int, required=True, choices=range(4))
    parser.add_argument("--rows", type=int, default=8, choices=range(1, 17))
    parser.add_argument("--epochs", type=int, default=16)
    parser.add_argument("--timing-iterations", type=int, default=100)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--counter-only", choices=sorted(CASES))
    parser.add_argument("--counter-repeats", type=int, default=4)
    parser.add_argument("--candidate", action="store_true")
    args = parser.parse_args()

    torch.xpu.set_device(0)
    selected = (
        {args.counter_only: CASES[args.counter_only]}
        if args.counter_only
        else CASES
    )
    results: dict[str, object] = {}
    exact = 0
    checks = 0

    for case_index, (name, (k_dim, n_dim, splits)) in enumerate(selected.items()):
        torch.manual_seed(72100 + args.rank * 1000 + case_index)
        rows = torch.randn(
            (args.rows, k_dim), dtype=torch.bfloat16, device="xpu"
        )
        weight = torch.randn((n_dim, k_dim), dtype=torch.bfloat16, device="xpu")

        if args.counter_only:
            # Evict the projection weight so ComputeBasic observes streamed
            # weights instead of an L3-hot repeated microbenchmark.
            junk = torch.randn((67_108_864,), dtype=torch.float32, device="xpu")
            for _ in range(args.counter_repeats):
                junk.add_(1)
                output = (
                    candidate_mm(rows, weight)
                    if args.candidate
                    else record_bmm(rows, weight)
                )
                torch.xpu.synchronize()
            results[name] = {"output_hash": tensor_hash(output)}
            continue

        case_checks = 0
        case_exact = 0
        hashes = []
        for epoch in range(args.epochs):
            torch.manual_seed(
                72100 + args.rank * 1000 + case_index * 100 + epoch
            )
            rows = torch.randn(
                (args.rows, k_dim), dtype=torch.bfloat16, device="xpu"
            )
            weight = torch.randn((n_dim, k_dim), dtype=torch.bfloat16, device="xpu")
            baseline = record_bmm(rows, weight)
            candidate = candidate_mm(rows, weight)
            torch.xpu.synchronize()
            equal = torch.equal(baseline, candidate)
            case_checks += 1
            case_exact += int(equal)
            checks += 1
            exact += int(equal)
            if not equal:
                raise AssertionError(f"{name} epoch {epoch} is not bitwise exact")
            if splits is not None:
                split_pairs = zip(
                    baseline.split(splits, dim=-1),
                    candidate.split(splits, dim=-1),
                )
                for part, (base_part, cand_part) in enumerate(split_pairs):
                    part_equal = torch.equal(base_part, cand_part)
                    case_checks += 1
                    case_exact += int(part_equal)
                    checks += 1
                    exact += int(part_equal)
                    if not part_equal:
                        raise AssertionError(
                            f"{name} epoch {epoch} slice {part} is not exact"
                        )
            hashes.append(tensor_hash(candidate))

        results[name] = {
            "k": k_dim,
            "n": n_dim,
            "exact": f"{case_exact}/{case_checks}",
            "record_bmm_ms": timed_ms(
                lambda: record_bmm(rows, weight), args.timing_iterations
            ),
            "candidate_mm_ms": timed_ms(
                lambda: candidate_mm(rows, weight), args.timing_iterations
            ),
            "last_output_hash": hashes[-1],
        }

    payload = {
        "rank": args.rank,
        "device": torch.xpu.get_device_name(0),
        "rows": args.rows,
        "epochs": 0 if args.counter_only else args.epochs,
        "passed": exact == checks if not args.counter_only else True,
        "exact": f"{exact}/{checks}",
        "cases": results,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
